# Chromecast MQTT connector

Provides status information and control capabilities of your Chromecast devices via MQTT.

## Installation requirements

* Python 3.6+
* pychromecast
* paho-mqtt

You can install the requirements in their correct versions using `pip3 install -r requirements.txt`.

## Discovery and control

Using MQTT you can find the following topics. `friendly_name` is the name used to connect
to each Chromecast.

```
# - read only
chromecast/friendly_name/friendly_name
chromecast/friendly_name/connection_status
chromecast/friendly_name/cast_type
chromecast/friendly_name/current_app
chromecast/friendly_name/player_duration
chromecast/friendly_name/player_position
chromecast/friendly_name/player_state
chromecast/friendly_name/volume_level
chromecast/friendly_name/volume_muted
chromecast/friendly_name/media/title
chromecast/friendly_name/media/album_name
chromecast/friendly_name/media/artist
chromecast/friendly_name/media/album_artist
chromecast/friendly_name/media/track
chromecast/friendly_name/media/images
chromecast/friendly_name/media/content_type
chromecast/friendly_name/media/content_url

# - writable
chromecast/friendly_name/command/volume_level
chromecast/friendly_name/command/volume_muted
chromecast/friendly_name/command/player_position
chromecast/friendly_name/command/player_state
```

Control the player by publishing values to the four topics above.


Change volume using values from `0` to `100`:

* Absolute: publish e.g. `55` to `chromecast/friendly_name/command/volume_level`
* Relative: publish e.g. `+5` or `-5` to `chromecast/friendly_name/command/volume_level`


Change mute state: publish `0` or `1` to `chromecast/friendly_name/command/volume_muted`.


Play something: Publish a json array with two elements (content url and content type) to
`chromecast/friendly_name/command/player_state`, e.g. `["http://your.stream.url.here", "audio/mpeg"]`.
You can also just publish a URL to `player_state` (just as string, not as json array, e.g.
`http://your.stream.url.here`), the application then tries to guess the required MIME type.

For other player controls, simply publish e.g. `RESUME`, `PAUSE`, `STOP`, `SKIP` or `REWIND` to
`chromecast/friendly_name/command/player_state`. Attention: This is case-sensitive!
