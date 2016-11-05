
# only used for publishing
import json

TOPIC_FRIENDLY_NAME = "chromecast/%s/friendly_name"
TOPIC_CONNECTION_STATUS = "chromecast/%s/connection_status"
TOPIC_CAST_TYPE = "chromecast/%s/cast_type"
TOPIC_CURRENT_APP = "chromecast/%s/current_app"
TOPIC_MEDIA_TITLE = "chromecast/%s/media/title"
TOPIC_MEDIA_ALBUM_NAME = "chromecast/%s/media/album_name"
TOPIC_MEDIA_ARTIST = "chromecast/%s/media/artist"
TOPIC_MEDIA_ALBUM_ARTIST = "chromecast/%s/media/album_artist"
TOPIC_MEDIA_TRACK = "chromecast/%s/media/track"
TOPIC_MEDIA_IMAGES = "chromecast/%s/media/images"
TOPIC_MEDIA_CONTENT_TYPE = "chromecast/%s/media/content_type"
TOPIC_MEDIA_CONTENT_URL = "chromecast/%s/media/content_url"
TOPIC_PLAYER_STATE = "chromecast/%s/player_state"

# publish + subscribe
TOPIC_VOLUME_LEVEL = "chromecast/%s/volume_level"
TOPIC_VOLUME_MUTED = "chromecast/%s/volume_muted"
TOPIC_PLAYER_POSITION = "chromecast/%s/player_position"
TOPIC_PLAYER_DURATION = "chromecast/%s/player_duration"
TOPIC_PLAYER_COMMAND = "chromecast/%s/player_command"


class MqttPropertyHandler:

    def __init__(self, mqtt_connection, mqtt_topic_filter):
        self.mqtt = mqtt_connection
        self.topic_filter = mqtt_topic_filter
        self.written_values = {}
        
        self._initialize_topics()

    def is_topic_filter_matching(self, topic):
        """
        Check if a topic (e.g.: chromecast/192.168.0.1/player_state) matches our filter (the ip address part).
        """
        try:
            return topic.split("/")[1] == self.topic_filter
        except IndexError:
            return False

    def _initialize_topics(self):
        self.mqtt.subscribe(TOPIC_VOLUME_LEVEL % self.topic_filter)
        self.mqtt.subscribe(TOPIC_VOLUME_MUTED % self.topic_filter)
        self.mqtt.subscribe(TOPIC_PLAYER_POSITION % self.topic_filter)
        self.mqtt.subscribe(TOPIC_PLAYER_DURATION % self.topic_filter)
        self.mqtt.subscribe(TOPIC_PLAYER_COMMAND % self.topic_filter)

    def _bool_to_val(self, val):
        if val:
            return "1"

        return "0"

    def _write(self, topic, value):
        if isinstance(value, float):
            value = str(round(value, 2))
        elif isinstance(value, bool):
            value = self._bool_to_val(value)

        formatted_topic = topic % self.topic_filter
        # very easy filter to prevent writing the same value twice
        if formatted_topic in self.written_values and self.written_values[formatted_topic] == value:
            return

        self.written_values[formatted_topic] = value
        self.mqtt.send_message(formatted_topic, value)

    def write_cast_status(self, app_name, volume_level, is_volume_muted, cast_type, friendly_name):
        self._write(TOPIC_CURRENT_APP, app_name)
        self._write(TOPIC_VOLUME_LEVEL, volume_level)
        self._write(TOPIC_VOLUME_MUTED, is_volume_muted)
        self._write(TOPIC_CAST_TYPE, cast_type)
        self._write(TOPIC_FRIENDLY_NAME, friendly_name)

    def write_player_status(self, state, current_time, duration):
        self._write(TOPIC_PLAYER_STATE, state)
        self._write(TOPIC_PLAYER_POSITION, current_time)
        self._write(TOPIC_PLAYER_DURATION, duration)

    def write_media_status(self, title, album_name, artist, album_artist, track, images, content_type, content_id):
        self._write(TOPIC_MEDIA_TITLE, title)
        self._write(TOPIC_MEDIA_ALBUM_NAME, album_name)
        self._write(TOPIC_MEDIA_ARTIST, artist)
        self._write(TOPIC_MEDIA_ALBUM_ARTIST, album_artist)
        self._write(TOPIC_MEDIA_TRACK, track)
        self._write(TOPIC_MEDIA_IMAGES, json.dumps(images))
        self._write(TOPIC_MEDIA_CONTENT_TYPE, content_type)
        self._write(TOPIC_MEDIA_CONTENT_URL, content_id)

    def write_connection_status(self, status):
        self._write(TOPIC_CONNECTION_STATUS, status)
