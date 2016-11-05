import logging
from pychromecast import get_chromecast
from pychromecast.socket_client import CONNECTION_STATUS_CONNECTED
from handler.properties import MqttPropertyHandler


class ChromecastConnectionCallback:
    pass


class ChromecastConnection():

    def __init__(self, ip_address, mqtt_connection, connection_callback):
        """
        Called if a new Chromecast device has been found.
        """

        self.logger = logging.getLogger("chromecast")
        self.ip_address = ip_address
        self.device = get_chromecast(ip=ip_address)
        self.mqtt_properties = MqttPropertyHandler(mqtt_connection, ip_address)
        self.connection_callback = connection_callback

        self.device.register_status_listener(self)
        self.device.media_controller.register_status_listener(self)
        self.device.register_launch_error_listener(self)
        self.device.register_connection_listener(self)

    def unregister_device(self):
        """
        Called if this Chromecast device has disappeared and resources should be cleaned up.
        """

        pass

    def is_interesting_message(self, topic):
        """
        Called to determine if the current device is interested in handling a MQTT topic. If true is
        returned, handle_message(topic, payload) is called next to handle the message.
        """
        return self.mqtt_properties.is_topic_filter_matching(topic)

    def handle_message(self, topic, payload):
        """
        Handle an incoming mqtt message.
        """

        pass

    def new_cast_status(self, status):
        """
        PyChromecast cast status callback.
        """

        # CastStatus(is_active_input=None, is_stand_by=None, volume_level=0.3499999940395355, volume_muted=False,
        # app_id='CC1AD845', display_name='Default Media Receiver', namespaces=['urn:x-cast:com.google.cast.media'],
        # session_id='xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxx', transport_id='web-0', status_text='Now Casting')
        self.logger.info("received new cast status from chromecast %s" % self.ip_address)
        self.mqtt_properties.write_cast_status(status.display_name, status.volume_level, status.volume_muted,
                                               self.device.cast_type, self.device.name)
        # dummy write as connection status callback does not work at the moment
        self.mqtt_properties.write_connection_status(CONNECTION_STATUS_CONNECTED)

    def new_launch_error(self, launch_failure):
        """
        PyChromecast error callback.
        """

        self.logger.error("received error from chromecast %s: %s" % (self.ip_address, launch_failure))

    def new_connection_status(self, status):
        """
        PyChromecast connection status callback.
        """

        self.logger.info("received new connection status from chromecast %s: %s" % (self.ip_address, status))
        self.mqtt_properties.write_connection_status(status.status)

    def new_media_status(self, status):
        """
        PyChromecast media status callback.
        """

        #  <MediaStatus {'media_metadata': {}, 'content_id': 'http://some.url.com/', 'player_state': 'PLAYING',
        # 'episode': None, 'media_custom_data': {}, 'supports_stream_mute': True, 'track': None,
        # 'supports_stream_volume': True, 'volume_level': 1, 'album_name': None, 'idle_reason': None,
        # 'album_artist': None, 'media_session_id': 4, 'content_type': 'audio/mpeg', 'metadata_type': None,
        # 'volume_muted': False, 'supports_pause': True, 'artist': None, 'title': None, 'subtitle_tracks': {},
        # 'supports_skip_backward': False, 'stream_type': 'BUFFERED', 'playback_rate': 1,
        # 'supports_skip_forward': False, 'season': None, 'duration': None, 'images': [], 'series_title': None,
        # 'supports_seek': True, 'current_time': 13938.854693, 'supported_media_commands': 15}>
        self.logger.info("received new media status from chromecast %s" % self.ip_address)

        self.mqtt_properties.write_player_status(status.player_state, status.current_time, status.duration)
        self.mqtt_properties.write_media_status(status.title, status.album_name, status.artist, status.album_artist,
                                                status.track, status.images, status.content_type, status.content_id)
