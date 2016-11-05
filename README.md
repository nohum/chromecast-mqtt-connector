# Chromecast MQTT connector

Provides status information and control capabilities of your Chromecast devices via MQTT.

## Installation requirements

* Python 3
* pychromecast
* paho-mqtt

## Discovery and control

Using MQTT you can find the following topics. `UUID` is a device-unique identifier for
each Chromecast.

```
# - read only
chromecast.UUID.friendly_name
chromecast.UUID.address
chromecast.UUID.connection_status
chromecast.UUID.is_stand_by
chromecast.UUID.currently_running_app

# - r/w
chromecast.UUID.volume_level
chromecast.UUID.volume_mute
chromecast.UUID.player_state
chromecast.UUID.player_position
chromecast.UUID.player_duration

# - read only
chromecast.UUID.media.title
chromecast.UUID.media.album_name
chromecast.UUID.media.artist
chromecast.UUID.media.album_artist
chromecast.UUID.media.track
chromecast.UUID.media.images
chromecast.UUID.media.content_type
chromecast.UUID.media.content_url
```
