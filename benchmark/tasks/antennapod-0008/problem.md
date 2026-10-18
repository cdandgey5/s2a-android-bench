# Auto-download check blocks database access for seconds, even loads all new episodes even when disabled

### App version

`3.12.0` (`develop` | `980b2ff32d`)

### Android version

`16`

### Device model

Pixel 9a

### First occurred

long-standing, as far as I can tell

### Steps to reproduce

1. Use a library with many episodes marked as "new" (mine: ~`33,000`); my Sqlite database export is around `~220 MB` 
2. Disable automatic download globally (`Settings -> Downloads -> Automatic download`), but the problem also occurs with it enabled
3. Trigger the auto-download check. Any of these is enough:
   - start a manual download (if `Enqueue downloaded` is on, this adds to the queue)
   - add/remove an episode in the queue
   - refresh feeds (automatic refresh alone makes this very frequent)
   - connect/disconnect the charger
   - change connectivity
4. While the download service performs its auto-download check, load the Queue screen or anything else that reads the database

### Expected behaviour

The auto-download check should only query episodes that are actually eligible (per-feed setting enabled, not yet downloaded, ...), 
and should cost almost nothing when automatic download is disabled

### Current behaviour

`AutomaticDownloadAlgorithm.autoDownloadUndownloadedItems()` calls
`DBReader.getEpisodes(0, Integer.MAX_VALUE, FeedItemFilter.NEW, DATE_NEW_OLD)`  which loads **all** new episodes into memory before applying feed/episode eligibility filters in Java. 

The global "disabled" setting is only consulted after everything is loaded, so in my case it loads ~`33,000` rows just to discard them all.

Because `DBReader`'s methods are **synchronized**, all other database access (e.g. queue loading) waits behind this scan. 

Measured on my device: queue load blocked for `~2.28 s` whenever the auto-download check ran (feed refresh, queue changes, charger/connectivity events, download starts); with eligibility filtering done in the SQL query instead, the same operation takes `~31 ms` (zero-row result, since no feed is individually set to `Enabled` while global auto-download is off).

Users see this as multi-second UI freezes / ANR risk every time the auto-download check runs (feed refreshes, queue changes, charger/connectivity events, download starts), scaling with library size.

---

**Maintainer comment:** Thanks for the measurements. Let's add
`DBReader.getAutoDownloadCandidates(boolean globalAutoDownloadEnabled, boolean includeQueue)` that
does the eligibility filtering in SQL and returns the candidates newest first (with their feed
set), and use it for the auto-download check. An episode is a candidate if it has media that is
not downloaded yet, its own auto-download flag is not turned off, its feed is not a local
folder, and either it is *new* in a subscribed feed whose auto-download setting allows it —
"Enabled" when the global setting is off, anything but "Disabled" when it is on — or it is in
the queue and `includeQueue` is true. The per-feed episode filter keeps being applied afterwards
as today.
