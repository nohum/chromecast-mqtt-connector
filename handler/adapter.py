import logging
from pychromecast import get_chromecasts, ChromecastConnectionError, IDLE_APP_ID
from pychromecast.controllers.media import MEDIA_PLAYER_STATE_IDLE
from pychromecast.socket_client import CONNECTION_STATUS_CONNECTED, CONNECTION_STATUS_FAILED, \
    CONNECTION_STATUS_DISCONNECTED
from handler.properties import MqttPropertyHandler, MqttChangesCallback
from collections import namedtuple
from queue import Queue
from threading import Thread

CONNECTION_STATUS_WAITING_FOR_DEVICE = "WAITING"
CONNECTION_STATUS_ERROR = "ERROR"
CONNECTION_STATUS_NOT_FOUND = "NOT_FOUND"

CreateConnectionCommand = namedtuple("CreateConnectionCommand", ["device_name"])
DisconnectCommand = namedtuple("DisconnectCommand", [])
VolumeMuteCommand = namedtuple("VolumeMuteCommand", ["muted"])
VolumeLevelRelativeCommand = namedtuple("VolumeLevelRelativeCommand", ["value"])
VolumeLevelAbsoluteCommand = namedtuple("VolumeLevelAbsoluteCommand", ["value"])
PlayerPositionCommand = namedtuple("PlayerPositionCommand", ["position"])
PlayerPlayStreamCommand = namedtuple("PlayerPlayStreamCommand", ["content_url", "content_type"])
PlayerPauseCommand = namedtuple("PlayerPauseCommand", [])
PlayerResumeCommand = namedtuple("PlayerResumeCommand", [])
PlayerStopCommand = namedtuple("PlayerStopCommand", [])
PlayerSkipCommand = namedtuple("PlayerSkipCommand", [])
PlayerRewindCommand = namedtuple("PlayerRewindCommand", [])

CastReceivedStatus = namedtuple("CastReceivedStatus", ["status"])
CastConnectionStatus = namedtuple("CastConnectionStatus", ["status"])
CastMediaStatus = namedtuple("CastMediaStatus", ["status"])


class ChromecastConnectionCallback:

    def on_connection_failed(self, chromecast_connection, device_name):
        pass

    def on_connection_dead(self, chromecast_connection, device_name):
        pass


class ConnectionUnavailableException(Exception):
    """
    Exception if connection to Chromecast is not available but required
    """
    pass


class ChromecastConnection(MqttChangesCallback):

    def __init__(self, device_name, mqtt_connection, connection_callback):
        """
        Called if a new Chromecast device has been found.
        """

        self.logger = logging.getLogger("chromecast")
        self.device_name = device_name
        self.connection_callback = connection_callback
        self.connection_failure_count = 0
        self.device_connected = False

        self.mqtt_properties = MqttPropertyHandler(mqtt_connection, device_name, self)
        self.processing_queue = Queue(maxsize=100)

        self.processing_worker = Thread(target=self._worker)
        self.processing_worker.daemon = True
        self.processing_worker.start()

        self.processing_queue.put(CreateConnectionCommand(device_name))

    def is_connected(self):
        # TODO thread sync
        return self.device_connected

    def unregister_device(self):
        """
        Called if this Chromecast device has disappeared and resources should be cleaned up.
        """

        self.processing_queue.put(DisconnectCommand())

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

        self.processing_queue.put(CastReceivedStatus(status))

    def new_launch_error(self, launch_failure):
        """
        PyChromecast error callback.
        """

        self.logger.error("received error from chromecast %s: %s" % (self.device_name, launch_failure))

    def new_connection_status(self, status):
        """
        PyChromecast connection status callback.
        """

        self.processing_queue.put(CastConnectionStatus(status))

    def new_media_status(self, status):
        """
        PyChromecast media status callback.
        """

        self.processing_queue.put(CastMediaStatus(status))

    def on_volume_mute_requested(self, is_muted):
        self.processing_queue.put(VolumeMuteCommand(is_muted))

    def on_volume_level_relative_requested(self, relative_value):
        self.processing_queue.put(VolumeLevelRelativeCommand(relative_value))

    def on_volume_level_absolute_requested(self, absolute_value):
        self.processing_queue.put(VolumeLevelAbsoluteCommand(absolute_value))

    def on_player_position_requested(self, position):
        self.processing_queue.put(PlayerPositionCommand(position))

    def on_player_play_stream_requested(self, content_url, content_type):
        self.processing_queue.put(PlayerPlayStreamCommand(content_url, content_type))

    def on_player_pause_requested(self):
        self.processing_queue.put(PlayerPauseCommand())

    def on_player_resume_requested(self):
        self.processing_queue.put(PlayerResumeCommand())

    def on_player_stop_requested(self):
        self.processing_queue.put(PlayerStopCommand())

    def on_player_skip_requested(self):
        self.processing_queue.put(PlayerSkipCommand())

    def on_player_rewind_requested(self):
        self.processing_queue.put(PlayerRewindCommand())

    def _worker(self):
        while True:
            # TODO we should actually only get commands from the command queue if we are connected
            item = self.processing_queue.get()

            # noinspection PyBroadException
            try:
                requires_connection = not isinstance(item, CreateConnectionCommand) \
                                      and not isinstance(item, DisconnectCommand) \
                                      and not isinstance(item, CastReceivedStatus) \
                                      and not isinstance(item, CastConnectionStatus) \
                                      and not isinstance(item, CastMediaStatus)

                if requires_connection and not self.device_connected:
                    self.logger.info("no connection found but connection is required")
                    self._internal_create_connection(self.device_name)

                    if not self.device_connected:
                        self.logger.error("was not able to connect to device for command %s" % (item,))
                        raise ConnectionUnavailableException()

                if isinstance(item, CreateConnectionCommand):
                    self._worker_create_connection(item.device_name)
                elif isinstance(item, DisconnectCommand):
                    self._worker_disconnect()
                elif isinstance(item, VolumeMuteCommand):
                    self._worker_volume_muted(item.muted)
                elif isinstance(item, VolumeLevelRelativeCommand):
                    self._worker_volume_level_relative(item.value)
                elif isinstance(item, VolumeLevelAbsoluteCommand):
                    self._worker_volume_level_absolute(item.value)
                elif isinstance(item, PlayerPositionCommand):
                    self._worker_player_position(item.position)
                elif isinstance(item, PlayerPlayStreamCommand):
                    self._worker_player_play_stream(item.content_url, item.content_type)
                elif isinstance(item, PlayerPauseCommand):
                    self._worker_player_pause()
                elif isinstance(item, PlayerResumeCommand):
                    self._worker_player_resume()
                elif isinstance(item, PlayerStopCommand):
                    self._worker_player_stop()
                elif isinstance(item, PlayerSkipCommand):
                    self._worker_player_skip()
                elif isinstance(item, PlayerRewindCommand):
                    self._worker_player_rewind()
                elif isinstance(item, CastReceivedStatus):
                    self._worker_cast_received_status(item.status)
                elif isinstance(item, CastConnectionStatus):
                    self._worker_cast_connection_status(item.status)
                elif isinstance(item, CastMediaStatus):
                    self._worker_cast_media_status(item.status)
            except Exception as error:
                self.logger.exception("command %s failed" % (item,))

                if isinstance(error, ConnectionUnavailableException):
                    self.mqtt_properties.write_connection_status(CONNECTION_STATUS_NOT_FOUND)
                else:
                    self.mqtt_properties.write_connection_status(CONNECTION_STATUS_ERROR)

                # e.g. AttributeError: 'NoneType' object has no attribute 'media_controller'
                # at least something indicating that the connection is really dead for sure
                if isinstance(error, AttributeError):
                    self.connection_callback.on_connection_dead(self, self.device_name)
                else:
                    self.connection_callback.on_connection_failed(self, self.device_name)
            finally:
                self.logger.debug("command %s finished" % (item,))
                self.processing_queue.task_done()

    def _internal_create_connection(self, device_name):
        try:
            self.mqtt_properties.write_connection_status(CONNECTION_STATUS_WAITING_FOR_DEVICE)
            devices = get_chromecasts(tries=5)  # TODO not the best way to do this, change with #3

            for device in devices:
                if device.device.friendly_name == device_name:
                    self.device = device
                    break

            if self.device is None:
                self.logger.error("was not able to find chromecast %s" % self.device_name)
                raise ConnectionUnavailableException()

            self.device.register_status_listener(self)
            self.device.media_controller.register_status_listener(self)
            self.device.register_launch_error_listener(self)
            self.device.register_connection_listener(self)

            self.device_connected = True  # alibi action
        except ChromecastConnectionError:
            self.logger.exception("had connection error while finding chromecast %s" % self.device_name)

            self.device_connected = False

    def _worker_create_connection(self, device_name):
        # uncaught exceptions bubble to the try-except handler of the worker thread
        self._internal_create_connection(device_name)

        if not self.device_connected:
            self.mqtt_properties.write_connection_status(CONNECTION_STATUS_ERROR)

    def _worker_disconnect(self):
        self.logger.info("disconnecting chromecast %s" % self.device_name)

        self.device_connected = False

        if self.device is not None:
            self.device.disconnect()
            self.device = None
        else:
            self.logger.warning("device is not available (at disconnection)")

        self.mqtt_properties.write_connection_status(CONNECTION_STATUS_DISCONNECTED)

    def _worker_volume_muted(self, is_muted):
        self.logger.info("volume mute request, is muted = %s" % is_muted)

        self.device.set_volume_muted(is_muted)

    def _worker_volume_level_relative(self, relative_value):
        self.logger.info("volume change relative request, value = %d" % relative_value)

        new_level = self.device.status.volume_level + (relative_value / 100)
        if new_level > 100:
            self.logger.warning("received relative volume level that was too high")
            new_level = 100
        elif new_level < 0:
            self.logger.warning("received relative volume level that was too low")
            new_level = 0

        self.device.set_volume(new_level)

    def _worker_volume_level_absolute(self, absolute_value):
        self.logger.info("volume change absolute request, value = %d" % absolute_value)

        new_level = absolute_value / 100
        if new_level > 100:
            self.logger.warning("received absolute volume level that was too high")
            new_level = 100
        elif new_level < 0:
            self.logger.warning("received absolute volume level that was too low")
            new_level = 0

        self.device.set_volume(new_level)

    def _worker_player_position(self, position):
        self.logger.info("volume change position request, position = %d" % position)

        self.device.media_controller.seek(position)

    def _worker_player_play_stream(self, content_url, content_type):
        self.logger.info("play stream request, url = %s, type = %s" % (content_url, content_type))

        self.device.media_controller.play_media(content_url, content_type, autoplay=True)

    def _worker_player_pause(self):
        self.logger.info("pause request")

        self.device.media_controller.pause()

    def _worker_player_resume(self):
        self.logger.info("resume request")

        self.device.media_controller.play()

    def _worker_player_stop(self):
        self.logger.info("stop request")

        self.device.media_controller.stop()

    def _worker_player_skip(self):
        self.logger.info("skip request")

        self.device.media_controller.seek(int(self.device.media_controller.status.duration) - 1)

    def _worker_player_rewind(self):
        self.logger.info("rewind request")

        self.device.media_controller.rewind()

    # ##################################################################################

    def _worker_cast_received_status(self, status):
        # CastStatus(is_active_input=None, is_stand_by=None, volume_level=0.3499999940395355, volume_muted=False,
        # app_id='CC1AD845', display_name='Default Media Receiver', namespaces=['urn:x-cast:com.google.cast.media'],
        # session_id='xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxx', transport_id='web-0', status_text='Now Casting')
        self.logger.info("received new cast status from chromecast %s" % self.device_name)

        if status is None:
            self.logger.warning("received empty status")
            return

        self.mqtt_properties.write_cast_status(status.display_name, status.volume_level, status.volume_muted)
        # dummy write as connection status callback does not work at the moment
        self.mqtt_properties.write_connection_status(CONNECTION_STATUS_CONNECTED)
        self.connection_failure_count = 0

        # reset player state if necessary
        if status.app_id is None or status.app_id == IDLE_APP_ID:  # no app active = idle
            self.mqtt_properties.write_player_status(MEDIA_PLAYER_STATE_IDLE, None, None)

    def _worker_cast_connection_status(self, status):
        self.logger.info("received new connection status from chromecast %s: %s" % (self.device_name, status.status))
        self.mqtt_properties.write_connection_status(status.status)

        self.device_connected = status.status == CONNECTION_STATUS_CONNECTED

        if status.status == CONNECTION_STATUS_CONNECTED:
            self.connection_failure_count = 0

            self.mqtt_properties.write_cast_data(self.device.cast_type, self.device.name)
        elif status.status == CONNECTION_STATUS_FAILED:
            self.connection_failure_count += 1
            self.logger.warning("received failure from connection, current failure counter: %d" %
                                self.connection_failure_count)

            if self.connection_failure_count > 7:
                self.logger.warning("failure counter too high, treating chromecast as dead")
                self.connection_callback.on_connection_dead(self, self.device_name)

    def _worker_cast_media_status(self, status):
        #  <MediaStatus {'media_metadata': {}, 'content_id': 'http://some.url.com/', 'player_state': 'PLAYING',
        # 'episode': None, 'media_custom_data': {}, 'supports_stream_mute': True, 'track': None,
        # 'supports_stream_volume': True, 'volume_level': 1, 'album_name': None, 'idle_reason': None,
        # 'album_artist': None, 'media_session_id': 4, 'content_type': 'audio/mpeg', 'metadata_type': None,
        # 'volume_muted': False, 'supports_pause': True, 'artist': None, 'title': None, 'subtitle_tracks': {},
        # 'supports_skip_backward': False, 'stream_type': 'BUFFERED', 'playback_rate': 1,
        # 'supports_skip_forward': False, 'season': None, 'duration': None, 'images': [], 'series_title': None,
        # 'supports_seek': True, 'current_time': 13938.854693, 'supported_media_commands': 15}>
        self.logger.info("received new media status from chromecast %s" % self.device_name)

        images = status.media_metadata.get('images', [])
        image_filtered = None

        for image in images:
            if "url" in image:
                image_filtered = image["url"]
                break  # only take the first image

        self.mqtt_properties.write_player_status(status.player_state, status.current_time, status.duration)
        self.mqtt_properties.write_media_status(status.title, status.album_name, status.artist, status.album_artist,
                                                status.track, image_filtered, status.content_type, status.content_id)
