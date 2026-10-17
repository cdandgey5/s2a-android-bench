# Episode length missing for feeds that use a decimal comma in the duration

**Describe the bug**

I subscribe to a podcast whose feed writes episode durations with a decimal comma instead of a
decimal point, e.g. `<itunes:duration>00:52:17,5</itunes:duration>` or
`<itunes:duration>3137,5</itunes:duration>`. AntennaPod shows no length for any of its episodes
until I start playing one. Other apps show the length (52:17). Feeds that write
`00:52:17.5` work fine in AntennaPod.

**Steps to reproduce**

1. Subscribe to a feed whose `itunes:duration` values use a comma before the fractional seconds
   (both the `hh:mm:ss,f` form and the plain-seconds form `ssss,f`).
2. Open the podcast's episode list.

**Expected behaviour**

The episode length is shown, the same as for `00:52:17.5` (the fraction counts as part of a
second: `00:01:05,5` is one minute and five and a half seconds).

**Actual behaviour**

No length is shown for those episodes.

**Environment**

AntennaPod built from the current `develop` branch.
