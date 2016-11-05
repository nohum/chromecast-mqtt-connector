#!/usr/bin/env python3
import logging

from handler.event import EventHandler
from helper.config import Config
from helper.discovery import ChromecastDiscovery
from time import sleep
from helper.mqtt import MqttConnection

logging.basicConfig(level=logging.DEBUG)
# logging.getLogger("pika").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

logger.debug("~ reading config")
config = Config('config.ini')

event_handler = EventHandler()

logger.debug("~ connecting to mqtt")
mqtt = MqttConnection(config.get_mqtt_broker_address(), config.get_mqtt_broker_port(), event_handler)
if not mqtt.start_connection():
    exit(1)

logger.debug("~ starting chromecast discovery")
discovery = ChromecastDiscovery(event_handler)
discovery.start_discovery()

logger.debug("~ initialization finished")

is_running = True
while is_running:
    try:
        sleep(1)
    except KeyboardInterrupt:
        is_running = False

logger.debug("~ stop signal received, shutting down")

discovery.stop_discovery()
mqtt.stop_connection()

logger.debug("~ shutdown completed")
