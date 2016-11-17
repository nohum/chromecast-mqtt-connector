#!/usr/bin/env python3
import logging
import os

from handler.event import EventHandler
from helper.config import Config
from helper.discovery import ChromecastDiscovery
from time import sleep
from helper.mqtt import MqttConnection

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

logger.debug("~ reading config")
config = Config(os.getcwd() + '/config.ini')

event_handler = EventHandler()

logger.debug("~ connecting to mqtt")
username = None
password = None
if config.get_mqtt_broker_use_auth():
    logger.debug("~ using username and password to connect to mqtt")
    username = config.get_mqtt_broker_username()
    password = config.get_mqtt_broker_password()

mqtt = MqttConnection(config.get_mqtt_broker_address(), config.get_mqtt_broker_port(), username, password,
                      event_handler)
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
