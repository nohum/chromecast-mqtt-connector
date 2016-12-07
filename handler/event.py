from handler.adapter import ChromecastConnection, ChromecastConnectionCallback
from helper.discovery import DiscoveryCallback
from helper.mqtt import MqttConnectionCallback
import logging


class EventHandler(DiscoveryCallback, MqttConnectionCallback, ChromecastConnectionCallback):
    """
    Class that ties MQTT, discovery and Chromecast events together.
    """

    def __init__(self):
        self.logger = logging.getLogger("event")

        self.mqtt_client = None
        self.known_devices = {}

    def on_mqtt_message_received(self, topic, payload):
        for ip in self.known_devices:
            device = self.known_devices[ip]
            if device.is_interesting_message(topic):
                device.handle_message(topic, payload)
                return

        self.logger.warn("received change for topic %s, but was not handled" % topic)

    def on_mqtt_connected(self, client):
        self.logger.debug("mqtt connected callback has been invoked")
        self.mqtt_client = client

    def on_chromecast_appeared(self, device_name, model_name, ip_address, port):
        if ip_address in self.known_devices:
            self.logger.warn("device %s already known" % ip_address)
            return

        self.known_devices[ip_address] = ChromecastConnection(ip_address, self.mqtt_client, self)
        self.logger.info("added device %s" % ip_address)

    def on_chromecast_disappeared(self, ip_address):
        if ip_address not in self.known_devices:
            self.logger.warn("device %s not known" % ip_address)
            return

        self.logger.debug("unregistering device %s" % ip_address)

        device = self.known_devices.pop(ip_address)
        device.unregister_device()

    def on_connection_failed(self, chromecast_connection, ip_address):
        self.logger.debug("connection to device %s failed to often, creating new device" % ip_address)

        device = self.known_devices.pop(ip_address)
        if device is not None:
            device.unregister_device()

        self.known_devices[ip_address] = ChromecastConnection(ip_address, self.mqtt_client, self)
