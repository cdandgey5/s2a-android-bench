# Podcast artwork missing for feeds using the legacy iTunes namespace URI

### App version

3.12.1

### Android version

Android 12 (API 31)

### Device model

Samsung SM-N976N

### First occurred

Present in current releases; the affected feed has never shown artwork.

### Steps to reproduce

1. Subscribe to `https://minicast.imbc.com/PodCast/pod.aspx?code=1000671100000100000` (MBC "손에 잡히는 경제").
2. Open the subscription.

### Expected behaviour

The podcast artwork declared by the feed is displayed.

### Current behaviour

No artwork is shown; the subscription falls back to a placeholder.

The feed declares the iTunes namespace with the capitalisation Apple used in its original DTD:

```xml
<rss xmlns:itunes="http://www.itunes.com/DTDs/Podcast-1.0.dtd" version="2.0">
```

This feed provides its artwork only through `<itunes:image>` and has no standard RSS
`<image>` element, so the cover is lost entirely. Other iTunes-only metadata in such feeds
is dropped for the same reason.

Both spellings appear in the wild, since Apple's own documentation has used each of them
over time.

### Crash logs

No crash — the artwork is silently omitted.
