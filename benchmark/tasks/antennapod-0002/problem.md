# Uppercase SubscribeOnAndroid link crashes the app instead of subscribing

### App version

3.12.2

### Steps to reproduce

1. Open a SubscribeOnAndroid link whose host is written in capitals with AntennaPod, e.g.
   `https://SUBSCRIBEONANDROID.COM/example.com/feed` (some podcast websites print their
   subscribe links that way).
2. AntennaPod opens to show the podcast.

### Expected behaviour

The link is handled exactly like `https://subscribeonandroid.com/example.com/feed`: AntennaPod
shows the podcast at `https://example.com/feed` so I can subscribe. The capitalisation of the
host name should not matter.

### Current behaviour

With the lowercase link everything works. With the uppercase host the app never shows the
podcast; it hangs and then crashes (stack overflow).
