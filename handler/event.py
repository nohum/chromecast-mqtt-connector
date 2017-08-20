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
DeviceAppeared = namedtuple("DeviceAppeared", ["device_name"])
DeviceDisappeared = namedtuple("DeviceDisappeared", ["device_name"])
DeviceConnectionFailure = namedtuple("DeviceConnectionFailure", ["device_name", "connection"])
DeviceConnectionDead = namedtuple("DeviceConnectionDead", ["device_name", "connection"])


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

    def on_mqtt_init_done(self, client):
        self.logger.debug("mqtt object is available")
        self.mqtt_client = client

    def on_mqtt_connected(self):
        self.logger.debug("mqtt connected callback has been invoked")

        # insert + as identifier so that every command to every identifier (= friendly names) will be recognized
        self.mqtt_client.subscribe(TOPIC_COMMAND_VOLUME_LEVEL % "+")
        self.mqtt_client.subscribe(TOPIC_COMMAND_VOLUME_MUTED % "+")
        self.mqtt_client.subscribe(TOPIC_COMMAND_PLAYER_POSITION % "+")
        self.mqtt_client.subscribe(TOPIC_COMMAND_PLAYER_STATE % "+")

        self.logger.debug("mqtt topics have been subscribed")

    def on_mqtt_message_received(self, topic, payload):
        self.processing_queue.put(MqttMessage(topic, payload), 2)

    def on_chromecast_appeared(self, device_name, model_name, ip_address, port):
        self.processing_queue.put(DeviceAppeared(device_name), 0)

    def on_chromecast_disappeared(self, device_name):
        self.processing_queue.put(DeviceDisappeared(device_name), 0)

    def on_connection_failed(self, chromecast_connection, device_name):
        self.processing_queue.put(DeviceConnectionFailure(device_name, chromecast_connection), 2)

    def on_connection_dead(self, chromecast_connection, device_name):
        self.processing_queue.put(DeviceConnectionDead(device_name, chromecast_connection), 0)

    def _worker(self):
        while True:
            item = self.processing_queue.get()

            try:
                if isinstance(item, MqttMessage):
                    self._worker_mqtt_message_received(item.topic, item.payload)
                elif isinstance(item, DeviceAppeared):
                    self._worker_chromecast_appeared(item.device_name)
                elif isinstance(item, DeviceDisappeared):
                    self._worker_chromecast_disappeared(item.device_name)
                elif isinstance(item, DeviceConnectionFailure):
                    self._worker_chromecast_connection_failed(item.device_name, item.connection)
                elif isinstance(item, DeviceConnectionDead):
                    self._worker_chromecast_connection_dead(item.device_name, item.connection)
            except:
                self.logger.exception("event %s failed" % (item,))
            finally:
                self.processing_queue.task_done()

    def _worker_mqtt_message_received(self, topic, payload):
        for ip in self.known_devices:
            device = self.known_devices[ip]
            if device.is_interesting_message(topic):
                self.logger.debug("found device to handle mqtt message")

                device.handle_message(topic, payload)
                return

        self.logger.warning("received change for topic %s, but was not handled - creating new device" % topic)

        # topic is e.g. "chromecast/%s/command/volume_level"
        parts = topic.split("/")
        if len(parts) > 2:
            device_name = parts[1]
            device = ChromecastConnection(device_name, self.mqtt_client, self)

            self.known_devices[device_name] = device
            self.logger.info("added device %s after receiving topic addressing it" % device_name)

            device.handle_message(topic, payload)

    def _worker_chromecast_appeared(self, device_name):
        if device_name in self.known_devices:
            self.logger.warning("device %s already known" % device_name)
            return

        self.known_devices[device_name] = ChromecastConnection(device_name, self.mqtt_client, self)
        self.logger.info("added device %s" % device_name)

    def _worker_chromecast_disappeared(self, device_name):
        if device_name not in self.known_devices:
            self.logger.warning("device %s not known" % device_name)
            return

        device = self.known_devices[device_name]

        if device.is_connected():
            self.logger.warning("device %s is still connected and not removed" % device_name)
        else:
            self.logger.debug("de-registering device %s" % device_name)

            self.known_devices.pop(device_name)  # ignore result, we already have the device
            device.unregister_device()

    def _worker_chromecast_connection_failed(self, device_name, connection):
        self.logger.warning("connection to device %s failed too often" % device_name)
        # TODO if the connection fails to often, treat it as dead

    def _worker_chromecast_connection_dead(self, device_name, connection):
        self.logger.error("connection to device %s is dead, removing" % device_name)
        self.known_devices.pop(device_name)
