from handler.adapter import ChromecastConnection, ChromecastConnectionCallback
from handler.properties import TOPIC_COMMAND_VOLUME_LEVEL, TOPIC_COMMAND_VOLUME_MUTED, TOPIC_COMMAND_PLAYER_POSITION, \
    TOPIC_COMMAND_PLAYER_STATE
from helper.discovery import DiscoveryCallback
from helper.mqtt import MqttConnectionCallback
import logging
from collections import namedtuple
from queue import PriorityQueue
from threading import Thread

MqttMessage = namedtuple("MqttMessage", ["topic", "payload"])
DeviceAppeared = namedtuple("DeviceAppeared", ["ip_address"])
DeviceDisappeared = namedtuple("DeviceDisappeared", ["ip_address"])
DeviceConnectionFailure = namedtuple("DeviceConnectionFailure", ["ip_address", "connection"])
DeviceConnectionDead = namedtuple("DeviceConnectionDead", ["ip_address", "connection"])


class SortedPriorityQueue(PriorityQueue):
    """
    See: http://stackoverflow.com/a/9289760
    """

    def __init__(self):
        PriorityQueue.__init__(self)
        self.counter = 0

    def put(self, item, priority):
        PriorityQueue.put(self, (priority, self.counter, item))
        self.counter += 1

    def get(self, *args, **kwargs):
        _, _, item = PriorityQueue.get(self, *args, **kwargs)
        return item


class EventHandler(DiscoveryCallback, MqttConnectionCallback, ChromecastConnectionCallback):
    """
    Class that ties MQTT, discovery and Chromecast events together.
    """

    def __init__(self):
        self.logger = logging.getLogger("event")

        self.mqtt_client = None
        self.known_devices = {}

        # processing queue used to add and remove devices
        self.processing_queue = SortedPriorityQueue()

        self.processing_worker = Thread(target=self._worker)
        self.processing_worker.daemon = True
        self.processing_worker.start()

    def on_mqtt_connected(self, client):
        self.logger.debug("mqtt connected callback has been invoked")
        self.mqtt_client = client
        # insert + as identifier so that every command to every identifier (= ip address) will be recognized
        self.mqtt_client.subscribe(TOPIC_COMMAND_VOLUME_LEVEL % "+")
        self.mqtt_client.subscribe(TOPIC_COMMAND_VOLUME_MUTED % "+")
        self.mqtt_client.subscribe(TOPIC_COMMAND_PLAYER_POSITION % "+")
        self.mqtt_client.subscribe(TOPIC_COMMAND_PLAYER_STATE % "+")

        self.logger.debug("mqtt topics have been subscribed")

    def on_mqtt_message_received(self, topic, payload):
        self.processing_queue.put(MqttMessage(topic, payload), 2)

    def on_chromecast_appeared(self, device_name, model_name, ip_address, port):
        self.processing_queue.put(DeviceAppeared(ip_address), 0)

    def on_chromecast_disappeared(self, ip_address):
        self.processing_queue.put(DeviceDisappeared(ip_address), 0)

    def on_connection_failed(self, chromecast_connection, ip_address):
        self.processing_queue.put(DeviceConnectionFailure(ip_address, chromecast_connection), 2)

    def on_connection_dead(self, chromecast_connection, ip_address):
        self.processing_queue.put(DeviceConnectionDead(ip_address, chromecast_connection), 0)

    def _worker(self):
        while True:
            item = self.processing_queue.get()

            try:
                if isinstance(item, MqttMessage):
                    self._worker_mqtt_message_received(item.topic, item.payload)
                elif isinstance(item, DeviceAppeared):
                    self._worker_chromecast_appeared(item.ip_address)
                elif isinstance(item, DeviceDisappeared):
                    self._worker_chromecast_disappeared(item.ip_address)
                elif isinstance(item, DeviceConnectionFailure):
                    self._worker_chromecast_connection_failed(item.ip_address, item.connection)
                elif isinstance(item, DeviceConnectionDead):
                    self._worker_chromecast_connection_dead(item.ip_address, item.connection)
            finally:
                self.processing_queue.task_done()

    def _worker_mqtt_message_received(self, topic, payload):
        for ip in self.known_devices:
            device = self.known_devices[ip]
            if device.is_interesting_message(topic):
                device.handle_message(topic, payload)
                return

        self.logger.warning("received change for topic %s, but was not handled - creating new device" % topic)

        # topic is e.g. "chromecast/%s/command/volume_level"
        parts = topic.split("/")
        if len(parts) > 2:
            ip_address = parts[1]
            device = ChromecastConnection(ip_address, self.mqtt_client, self)

            self.known_devices[ip_address] = device
            self.logger.info("added device %s after receiving topic addressing it" % ip_address)

            device.handle_message(topic, payload)

    def _worker_chromecast_appeared(self, ip_address):
        if ip_address in self.known_devices:
            self.logger.warn("device %s already known" % ip_address)
            return

        self.known_devices[ip_address] = ChromecastConnection(ip_address, self.mqtt_client, self)
        self.logger.info("added device %s" % ip_address)

    def _worker_chromecast_disappeared(self, ip_address):
        if ip_address not in self.known_devices:
            self.logger.warn("device %s not known" % ip_address)
            return

        self.logger.debug("de-registering device %s" % ip_address)

        device = self.known_devices.pop(ip_address)
        device.unregister_device()

    def _worker_chromecast_connection_failed(self, ip_address, connection):
        self.logger.warning("connection to device %s failed too often" % ip_address)

    def _worker_chromecast_connection_dead(self, ip_address, connection):
        self.logger.error("connection to device %s is dead, removing" % ip_address)
        self.known_devices.pop(ip_address)
