import configparser
import logging
import os


class Config:

    def __init__(self, filename):
        self.config = configparser.ConfigParser()
        self.logger = logging.getLogger("config")

        self.logger.info("config file path: %s" % filename)

        if os.path.isfile(filename):
            self.logger.info("config file has been found")
            self.config.read(filename)
        else:
            self.logger.warn("config file has not been found")

    def get_mqtt_broker_address(self):
        return self.config.get('mqtt', 'broker_address', fallback="127.0.0.1")

    def get_mqtt_broker_port(self):
        return self.config.getint('mqtt', 'broker_port', fallback=1883)

    def get_mqtt_broker_use_auth(self):
        return self.config.getboolean('mqtt', 'use_auth', fallback=False)

    def get_mqtt_broker_username(self):
        return self.config.get('mqtt', 'username', fallback=None)

    def get_mqtt_broker_password(self):
        return self.config.get('mqtt', 'password', fallback=None)
