# Recognize trailers and bonus episodes (`itunes:episodeType`)

### Checklist

- [X] I have used the search function for **OPEN** issues to see if someone else has already submitted the same feature request.
- [X] I have **also** used the search function for **CLOSED** issues to see if the feature was already implemented and is just waiting to be released, or if the feature was rejected.
- [X] I will describe the problem with as much detail as possible.
- [X] This request contains only one single feature, **not** a list of multiple (related) features.

### App version

3.12.3

### Feature or improvement you want

Lots of podcasts now tag their episodes with `<itunes:episodeType>` as described in Apple's podcast
RSS spec: `full` for a regular episode, `trailer` for the show trailer, and `bonus` for extra
material that is not part of the main run. AntennaPod ignores this tag right now, so the trailer
that a show published before its first episode looks exactly like a normal episode, and there is
nothing in the app that knows the difference.

AntennaPod should read the episode type from the feed, remember it for each episode, and keep it
up to date when the podcaster changes it later.

### Why should this be added?

Trailers and bonus episodes are very common in newer shows (several of my subscriptions start
with a trailer and drop "bonus" episodes in between). Knowing which episode is which is the
prerequisite for treating them differently in any way.

### Screenshots / Drawings / Technical details

Example item from one of my feeds:

```xml
<item>
    <title>Welcome to the show</title>
    <guid>https://example.com/episodes/trailer</guid>
    <itunes:episodeType>trailer</itunes:episodeType>
    <enclosure url="https://example.com/trailer.mp3" length="1234567" type="audio/mpeg"/>
</item>
```

I have also seen feeds that write the value in other casing or with whitespace around it, e.g.
`<itunes:episodeType> Bonus </itunes:episodeType>`.

---

**Maintainer comment:** Sounds reasonable. Let's do the data part first; how (and whether) we
show or filter trailers is a separate discussion, so no UI changes in this one.

Please add an enum `FeedItem.EpisodeType` with the values `FULL`, `TRAILER` and `BONUS`, and
`FeedItem.getEpisodeType()` / `FeedItem.setEpisodeType(EpisodeType)`:

- Every episode is `FULL` unless the feed says otherwise; a newly created `FeedItem` returns `FULL`.
- When parsing an RSS `<item>`, read `<itunes:episodeType>`: `full` → `FULL`, `trailer` → `TRAILER`,
  `bonus` → `BONUS`. Compare case-insensitively and ignore surrounding whitespace. A missing tag,
  an empty one or any other value (e.g. `teaser`) means `FULL`.
- Store the type with the episode in the database, so that it is still there when the episode is
  loaded again (with a database upgrade for existing installs; existing episodes become `FULL`).
- On feed refresh the stored episode must follow the feed: `FeedItem.updateFromOther(FeedItem)`
  takes over the episode type of the other item like it does for the other feed-provided fields,
  and the updated type is saved. If a podcaster turns a trailer into a bonus episode, the episode
  in the database is a bonus episode after the next refresh.
