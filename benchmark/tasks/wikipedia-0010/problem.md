# Consolidate talk page title handling into a single helper (`TalkPageTitleHelper`)

**Type:** Technical debt · **Tags:** Android app, Talk pages · **Priority:** Low

### Background

Two small pieces of talk page title logic have been copied around the talk feature and are slowly drifting apart:

1. **Going from a talk page to the page it is about** (`Talk:Earth` → `Earth`, `User talk:Foo` → `User:Foo`). This is currently `getNonTalkPageTitle()`, a companion function of the talk topics screen, and is called from the talk topics list, the reply / new topic screen, the saved messages (talk templates) screen, the archived talk pages screen and the thread header. Other screens should not have to reach into an Activity's companion for this.

2. **The linked page title shown at the top of talk screens** (`Talk: Earth`, where `Earth` is a link). The markup for it is built by hand in four places, each a slightly different copy:
   - talk topics list toolbar: HTML stripped from the display title, link target `#`;
   - reply / new topic toolbar (new topic, or opened from a diff): display title used as-is, link target `#`;
   - saved messages (talk templates) toolbar: display title used as-is, link target `#`;
   - page title in a topic's thread header: HTML stripped from the display title, link target is the URL of the subject page.

### Proposal

Add an `object TalkPageTitleHelper` in the `org.wikipedia.talk` package with these two functions, and switch every place listed above to use them:

**`fun subjectPageTitle(talkPageTitle: PageTitle): PageTitle`**

Returns the subject page of a talk page, with exactly the semantics of today's `getNonTalkPageTitle()`:

- a Talk page (`Talk:Earth` on enwiki) → the same title in the main namespace (`Earth`);
- a User talk page → the same title in the *localized* User namespace of the title's wiki (`User_talk:Foo` → `User:Foo` on enwiki, `Benutzer_Diskussion:Foo` → `Benutzer:Foo` on dewiki);
- any other title, e.g. a mainspace article → returned unchanged (an equal title);
- the `PageTitle` that is passed in must not be modified.

**`fun linkedTitleHtml(pageTitle: PageTitle, stripHtml: Boolean, href: String = "#"): String`**

Returns the same HTML markup the screens build today (callers keep passing it through `StringUtil.fromHtml()` themselves):

```
<namespace>: <a href='<href>'><title></a>
```

- `<namespace>` is `pageTitle.namespace` as it is, or, when the title has no namespace (e.g. we were handed the article itself), the localized name of the Talk namespace for the title's wiki (e.g. `Talk` on enwiki, `Diskussion` on dewiki);
- `<title>` is `pageTitle.displayText` with its namespace prefix (everything up to and including the first `:`) removed. With `stripHtml = true` any HTML markup in the display title (e.g. the `<i>` of an italic DISPLAYTITLE) is removed first; with `stripHtml = false` the markup is kept;
- `<href>` is inserted exactly as given, `#` by default.

For example, on enwiki `Talk:Earth` gives `Talk: <a href='#'>Earth</a>` in either mode, and a display title of `Talk:<i>Star Wars</i>` gives `Talk: <a href='#'><i>Star Wars</i></a>` without stripping and `Talk: <a href='#'>Star Wars</a>` with stripping.

### Acceptance criteria

- [ ] `TalkPageTitleHelper.subjectPageTitle()` and `TalkPageTitleHelper.linkedTitleHtml()` exist as described above.
- [ ] All four title variants listed in the background use `linkedTitleHtml()` with the matching `stripHtml` / `href` arguments; no hand-built copies of the markup remain.
- [ ] Every caller of `getNonTalkPageTitle()` uses `subjectPageTitle()` instead, and there is no second implementation of that logic left behind.
- [ ] **No behaviour change**: every screen shows exactly the same title text, link and link target as before, on every wiki language.
