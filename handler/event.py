from helper.discovery import DiscoveryCallback
from helper.mqtt import MqttConnectionCallback


class EventHandler(DiscoveryCallback, MqttConnectionCallback):

    def on_mqtt_message_received(self, topic, payload):
        pass

    def on_mqtt_connected(self):
        pass

    def on_chromecast_appeared(self, device_name, model_name, ip_address, port):
        pass

    def on_chromecast_disappeared(self, ip_address):
        pass
