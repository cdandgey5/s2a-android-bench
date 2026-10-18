# Description is empty when importing local opus file

### App version

3.11.0

### Android version

16

### Steps to reproduce

I export a youtube video to opus using yt-dlp and embed the metadata.
The video description ends up in the `synopsis` tag:
```
thomas@tiki /m/d/m/Perun> mediainfo 20260208_Perun_The_Greenland_Crisis_-_The_Arctic_Alliances_A_U.S._Strategic_Folly.opus
General
Complete name                            : 20260208_Perun_The_Greenland_Crisis_-_The_Arctic_Alliances_A_U.S._Strategic_Folly.opus
Format                                   : Ogg
File size                                : 52.5 MiB
Duration                                 : 1 h 0 min
Overall bit rate                         : 122 kb/s
Track name                               : 2026-02-08 — The Greenland Crisis - The Arctic, Alliances & A U.S. Strategic Folly
Performer                                : Perun
Genre                                    : News & Politics
Description                              : Sponsored by: Private Internet Access: https://www.piavpn.com/Perun
Recorded date                            : 20260208
Writing application                      : Lavf60.16.100
purl                                     : https://www.youtube.com/watch?v=Mx0W0FuKg18
synopsis                                 : Sponsored by: Private Internet Access: https://www.piavpn.com/Perun /  / If you had [description truncated]
Audio
ID                                       : 1454975173 (0x56B928C5)
Format                                   : Opus
Duration                                 : 1 h 0 min
Channel(s)                               : 2 channels
Channel layout                           : L R
Sampling rate                            : 48.0 kHz
Compression mode                         : Lossy
Writing library                          : Lavf60.16.100
Language                                 : English

Menu
00:00:00.000                             : Opening Words
00:01:15.000                             : What Am I Talking About?
00:03:50.000                             : Strategy and Greenland
00:10:49.000                             : the US & Greenland
00:23:41.000                             : How It Played Out
00:28:56.000                             : a Strategic Miscalculation
00:40:24.000                             : Soft Power & Strategy
00:54:49.000                             : Alternatives
00:56:13.000                             : Winners and Losers
00:59:06.000                             : Channel Update
```

In AntennaPod the episode description is empty.
