import logging
from threading import Thread, Condition

from zeroconf import ServiceBrowser, Zeroconf


GOOGLE_CAST_IDENTIFIER = "_googlecast._tcp.local."


class DiscoveryCallback:

    def on_chromecast_appeared(self, device_name, model_name, ip_address, port):
        pass

    def on_chromecast_disappeared(self, device_name):
        pass


class ChromecastDiscovery(Thread):
    """
    Original code borrowed from pychromecast discovery, adapted to run in background all the time.
    """

    def __init__(self, discovery_callback):
        super().__init__()

        self.logger = logging.getLogger("discovery")
        self.discovery_callback = discovery_callback
        self.run_condition = Condition()
        self.services = {}

    def start_discovery(self):
        self.logger.debug("starting discovery")
        self.start()

    def stop_discovery(self):
        self.logger.debug("stopping discovery")

        with self.run_condition:
            self.run_condition.notify_all()

    def run(self):
        zeroconf = Zeroconf()
        browser = ServiceBrowser(zeroconf, GOOGLE_CAST_IDENTIFIER, self)

        try:
            with self.run_condition:
                self.run_condition.wait()

            self.logger.debug("end of run-body (discovery)")

        finally:
            browser.cancel()
            zeroconf.close()

    def remove_service(self, zconf, typ, name):
        """ Remove a service from the collection. """

        # easy filtering
        if not name.endswith(GOOGLE_CAST_IDENTIFIER):
            return

        self.logger.info("removing chromecast with name \"%s\"" % name)

        if name in self.services:
            self.discovery_callback.on_chromecast_disappeared(self.services[name])
            self.services.pop(name, None)

    def add_service(self, zconf, typ, name):
        """ Add a service to the collection. """

        # easy filtering
        if not name.endswith(GOOGLE_CAST_IDENTIFIER):
            return

        self.logger.info("adding chromecast with name \"%s\"" % name)

        service = None
        tries = 0
        while service is None and tries < 4:
            try:
                service = zconf.get_service_info(typ, name)
            except IOError:
                # If the zeroconf fails to receive the necessary data we abort adding the service
                break
            tries += 1

        if not service:
            self.logger.warn("services not discovered for device")
            return

        ips = zconf.cache.entries_with_name(service.server.lower())
        host = repr(ips[0]) if ips else service.server

        def get_value(key):
            value = service.properties.get(key.encode('utf-8'))

            return value.decode('utf-8')

        model_name = get_value('md')
        device_name = get_value('fn')
        self.logger.info("chromecast device name \"%s\"" % device_name)

        self.services[name] = device_name
        self.discovery_callback.on_chromecast_appeared(device_name, model_name, host, service.port)
