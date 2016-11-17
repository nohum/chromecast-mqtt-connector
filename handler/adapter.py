import logging
from pychromecast import get_chromecast
from pychromecast.socket_client import CONNECTION_STATUS_CONNECTED, CONNECTION_STATUS_FAILED, \
    CONNECTION_STATUS_DISCONNECTED
from handler.properties import MqttPropertyHandler, MqttChangesCallback


class ChromecastConnectionCallback:

    def on_connection_failed(self, chromecast_connection, ip_address):
        pass


class ChromecastConnection(MqttChangesCallback):

    def __init__(self, ip_address, mqtt_connection, connection_callback):
        """
        Called if a new Chromecast device has been found.
        """

        self.logger = logging.getLogger("chromecast")
        self.ip_address = ip_address
        self.device = get_chromecast(ip=ip_address)
        self.mqtt_properties = MqttPropertyHandler(mqtt_connection, ip_address, self)
        self.connection_callback = connection_callback
        self.connection_failure_count = 0

        self.device.register_status_listener(self)
        self.device.media_controller.register_status_listener(self)
        self.device.register_launch_error_listener(self)
        self.device.register_connection_listener(self)

    def unregister_device(self):
        """
        Called if this Chromecast device has disappeared and resources should be cleaned up.
        """

        self.device.disconnect()
        self.mqtt_properties.write_connection_status(CONNECTION_STATUS_DISCONNECTED)
        self.mqtt_properties.unsubscribe()

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

        self.mqtt_properties.handle_message(topic, payload)

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
        self.connection_failure_count = 0

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

        if status.status == CONNECTION_STATUS_CONNECTED:
            self.connection_failure_count = 0
        elif status.status == CONNECTION_STATUS_FAILED:
            self.connection_failure_count += 1
            self.logger.warn("received failure from connection, current failure counter: %d"
                             % self.connection_failure_count)

            if self.connection_failure_count > 7:
                self.logger.warn("failure counter too high, treating chromecast as finally failed")
                self.connection_callback.on_connection_failed(self, self.ip_address)

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

        images = status.media_metadata.get('images', [])
        image_filtered = None

        for image in images:
            image_filtered = image["url"]
            break  # only take the first image

        self.mqtt_properties.write_player_status(status.player_state, status.current_time, status.duration)
        self.mqtt_properties.write_media_status(status.title, status.album_name, status.artist, status.album_artist,
                                                status.track, image_filtered, status.content_type, status.content_id)

    def on_volume_mute_requested(self, is_muted):
        self.logger.info("volume mute request, is muted = %s" % is_muted)

        self.device.wait(0.5)
        self.device.set_volume_muted(is_muted)

    def on_volume_level_relative_requested(self, relative_value):
        self.logger.info("volume change relative request, value = %d" % relative_value)

        self.device.wait(0.5)
        self.device.set_volume(self.device.status.volume_level + (relative_value / 100))

    def on_volume_level_absolute_requested(self, absolute_value):
        self.logger.info("volume change absolute request, value = %d" % absolute_value)

        self.device.wait(0.5)
        self.device.set_volume(absolute_value / 100)

    def on_player_position_requested(self, position):
        self.logger.info("volume change position request, position = %d" % position)

        self.device.wait(0.5)
        self.device.media_controller.seek(position)

    def on_player_play_stream_requested(self, content_url, content_type):
        self.logger.info("play stream request, url = %s, type = %s" % (content_url, content_type))

        self.device.wait(0.5)
        self.device.media_controller.play_media(content_url, content_type, autoplay=True)

    def on_player_pause_requested(self):
        self.logger.info("pause request")

        self.device.wait(0.5)
        self.device.media_controller.pause()

    def on_player_resume_requested(self):
        self.logger.info("resume request")

        self.device.wait(0.5)
        self.device.media_controller.play()

    def on_player_stop_requested(self):
        self.logger.info("stop request")

        self.device.wait(0.5)
        self.device.media_controller.stop()

    def on_player_skip_requested(self):
        self.logger.info("skip request")

        self.device.wait(0.5)
        self.device.media_controller.seek(int(self.device.media_controller.status.duration) - 1)

    def on_player_rewind_requested(self):
        self.logger.info("rewind request")

        self.device.wait(0.5)
        self.device.media_controller.rewind()
