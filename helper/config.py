import configparser
import logging
import os


class Config:

    def __init__(self, filename):
        self.config = configparser.ConfigParser()
        self.logger = logging.getLogger("config")

        if os.path.isfile(filename):
            self.logger.warn("log file not found: %s" % filename)
            self.config.read(filename)

    def get_mqtt_broker_address(self):
        return self.config.get('mqtt', 'broker_address', fallback="127.0.0.1")

    def get_mqtt_broker_port(self):
        return self.config.getint('mqtt', 'broker_port', fallback=1883)
