# Keep my folders when exporting/importing OPML

**Checklist**
- [x] I have used the search function for [**OPEN**](https://github.com/AntennaPod/AntennaPod/issues) issues to see if someone else has already submitted the same feature request.
- [x] I have **also** used the search function for [**CLOSED**](https://github.com/AntennaPod/AntennaPod/issues?q=is%3Aissue+is%3Aclosed) issues to find out if the feature was already implemented and is just waiting to be released, or if the feature was rejected.
- [x] I will describe the problem with as much detail as possible.

**App version:** 3.x (F-Droid)

**Is your feature request related to a problem? Please describe.**

I have about 60 subscriptions sorted into folders ("News", "Tech", "Kids", ...). When I move to a new
phone I export my subscriptions as OPML and import the file again. The podcasts come back, but every
folder is gone and I have to tag all 60 podcasts by hand again.

It also happens the other way round: the OPML file exported by my desktop feed reader has the
podcasts grouped in folders (nested `<outline>` elements), and AntennaPod ignores the grouping.

**Describe the solution you'd like**

The OPML export should write each folder as a folder outline containing its podcasts, and the OPML
import should understand such folders, so that an export → import round trip keeps my folders.

**Describe alternatives you've considered**

Using the full database export/import. That works between two AntennaPod installs, but not with
other apps, and I do not always want to move my whole history.

**Additional context**

The OPML format has no dedicated "folder" element. Everybody uses an `<outline>` without `xmlUrl`
that contains the feed outlines, for example:

```xml
<body>
  <outline text="News">
    <outline text="Daily News" title="Daily News" xmlUrl="https://example.com/daily.xml"/>
  </outline>
  <outline text="Some other podcast" title="Some other podcast" xmlUrl="https://example.com/other.xml"/>
</body>
```

---

**Comment from a maintainer:**

Thanks, makes sense. Our folders are tags, so let's map OPML folders to tags in both directions. Let's
do the OPML part first; actually applying the tags to the new subscriptions in the import screen can
be a follow-up PR.

**Import (reading an OPML file)**

- Please add `OpmlElement.getTags()`, returning a `Set<String>` with the folder names of the feed.
  It is an empty set (never `null`) for feeds at the top level of the file.
- A folder is an `<outline>` without `xmlUrl` that contains other outlines. Its name is taken
  like a feed's name (`title`, or `text` if there is no title).
- Our tags are flat, so with nested folders a feed gets **every** enclosing folder as a tag, not
  only the innermost one. A feed in `News` → `Local` gets `{News, Local}`; a feed directly in `News`
  gets `{News}`.
- If the same feed (same `xmlUrl`) appears more than once, for example in two folders, it must be
  returned only **once**, at the position of its first occurrence, with the tags of all its
  occurrences combined.
- Apart from that, files without folders must give the same result as today (all tags empty).

**Export (writing an OPML file)**

- As today, only subscribed feeds are exported, and each feed outline keeps its current attributes.
- A feed that has tags is written inside one folder per tag, `<outline text="TagName">`, placed
  directly in `<body>`. A feed with two tags appears in both folders.
- Ignore the internal root tag (`FeedPreferences.TAG_ROOT`, `#root`). It must never become a
  folder. A feed tagged `{#root, News}` only goes into the `News` folder.
- Feeds without tags (no tags at all, only `#root`, or no preferences loaded) stay at the top level
  of `<body>`, like today.
- Order: first the top-level feeds, in the order of the list that is passed in. Then the folders,
  sorted alphabetically **ignoring case** (like the navigation drawer). Inside a folder, the feeds
  keep the order of the list that is passed in.

With that, exporting a feed tagged `{#root, News}` and reading the file back gives one element with
tags `{News}`.
