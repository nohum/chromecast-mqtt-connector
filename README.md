# Chromecast MQTT connector

Provides status information and control capabilities of your Chromecast devices via MQTT.

## Installation requirements

* Python 3
* pychromecast
* paho-mqtt

## Discovery and control

Using MQTT you can find the following topics. `IP` is the ip address used to connect
to each Chromecast.

```
# - read only
chromecast/IP/friendly_name
chromecast/IP/connection_status
chromecast/IP/cast_type
chromecast/IP/current_app
chromecast/IP/player_duration

# - r/w
chromecast/IP/volume_level
chromecast/IP/volume_muted
chromecast/IP/player_position
chromecast/IP/player_state

# - read only
chromecast/IP/media/title
chromecast/IP/media/album_name
chromecast/IP/media/artist
chromecast/IP/media/album_artist
chromecast/IP/media/track
chromecast/IP/media/images
chromecast/IP/media/content_type
chromecast/IP/media/content_url
```
