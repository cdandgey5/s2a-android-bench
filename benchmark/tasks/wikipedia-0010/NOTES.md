# Provenance notes (not shown to agents)

- Source: authored for this benchmark (drafted by the building agent with claude-opus-5-5 at base 0c7ee9b4682512217e01d829fb0b6d068d268724).

# wikipedia-0010 — reviewer notes (not shown to agents)

**Category:** refactor. **Base:** upstream `0c7ee9b4682512217e01d829fb0b6d068d268724`.

## What the task checks and why it is realistic

Talk page title handling in the app is duplicated: the talk page → subject page conversion
(`getNonTalkPageTitle`) sits in the `TalkTopicsActivity` companion and is called from five files, and
the `"<ns>: <a href='…'>title</a>"` toolbar/header markup is copy-pasted in four places with three
variants (HTML kept, HTML stripped, stripped + href = subject page URI). The ticket asks for the kind of
small consolidation the Wikipedia Android team does routinely: one `object TalkPageTitleHelper` in
`org.wikipedia.talk` with `subjectPageTitle()` and `linkedTitleHtml()`, every call site switched, and
**no behaviour change**. The hidden tests pin the helper's contract, computed from the base code:
Talk → mainspace, User talk → localized User namespace (en and de), other titles unchanged, input not
mutated, the exact markup format, the localized Talk alias fallback for namespace-less titles
(`TalkAliasData` "de" = `Diskussion`), the strip / keep-markup variants and the custom href. A careless
refactor (hard-coding `"User"`, dropping the alias fallback, stripping in every variant, changing the
quote style or separator, mutating the caller's `PageTitle`) fails at least one test.

## Production files changed (reference fix)

- `app/src/main/java/org/wikipedia/talk/TalkPageTitleHelper.kt` (new)
- `app/src/main/java/org/wikipedia/talk/TalkTopicsActivity.kt` (toolbar title + goToPage use the helper; `getNonTalkPageTitle` removed from the companion; unused `TalkAliasData` import removed)
- `app/src/main/java/org/wikipedia/talk/TalkReplyActivity.kt`
- `app/src/main/java/org/wikipedia/talk/template/TalkTemplatesFragment.kt`
- `app/src/main/java/org/wikipedia/talk/TalkThreadHeaderView.kt`
- `app/src/main/java/org/wikipedia/talk/ArchivedTalkPagesActivity.kt` (subject page only; its own `talk_archived_title` markup is a different string and is left alone)

Every new call produces a string identical to the inline expression it replaces (same namespace fallback,
same `removeNamespace(removeHTMLTags(...))` order for the stripping variants, same `'` quoting).

## Hidden tests

New file `app/src/test/java/org/wikipedia/talk/TalkPageTitleHelperTest.kt` (Robolectric, mirrors
`PageTitleTest`). Every method references `TalkPageTitleHelper`, which does not exist at base, so the
whole class fails to compile there.

| Test method | Checks | Expected at base |
|---|---|---|
| `testSubjectPageTitleOfTalkPage` | `Talk:Earth` (en) → namespace `""`, `Namespace.MAIN`, prefixedText `Earth`, equals `PageTitle("Earth")`, uri `https://en.wikipedia.org/wiki/Earth`; input still `Talk:Earth` | compile error |
| `testSubjectPageTitleOfUserTalkPage` | `User_talk:Foo` (en) → namespace `User`, `Namespace.USER`, `User:Foo`, equals `PageTitle("User:Foo")`; input unchanged | compile error |
| `testSubjectPageTitleOfLocalizedUserTalkPage` | `Benutzer_Diskussion:Foo` (de) → namespace `Benutzer`, `Namespace.USER`, `Benutzer:Foo` | compile error |
| `testSubjectPageTitleOfMainspacePage` | `Earth` (en) → equal title, namespace `""`, `Earth` | compile error |
| `testLinkedTitleHtmlOfTalkPage` | `Talk:Earth` (en), both modes → `Talk: <a href='#'>Earth</a>` | compile error |
| `testLinkedTitleHtmlOfMainspacePageUsesLocalizedTalkNamespace` | `Erde` (de), both modes → `Diskussion: <a href='#'>Erde</a>` | compile error |
| `testLinkedTitleHtmlKeepsMarkupWithoutStripping` | display title `Talk:<i>Star Wars</i>`, `stripHtml=false` → `Talk: <a href='#'><i>Star Wars</i></a>` | compile error |
| `testLinkedTitleHtmlStripsMarkup` | same title, `stripHtml=true` → `Talk: <a href='#'>Star Wars</a>` | compile error |
| `testLinkedTitleHtmlWithHref` | `Talk:Earth`, `stripHtml=true`, href `https://en.wikipedia.org/wiki/Earth` → `Talk: <a href='https://en.wikipedia.org/wiki/Earth'>Earth</a>` | compile error |

All expected values were derived by hand from the base code (`PageTitle` parsing/`copy()`/namespace
setter, `Namespace.fromLegacyString`, `TalkAliasData`/`UserAliasData`/`UserTalkAliasData` for `en` and
`de`, `StringUtil.removeNamespace` = `substringAfter(':')`, `StringUtil.removeHTMLTags` =
`CustomHtmlParser.fromHtml(...).toString()`). Not compiled or run by the author (brief: no Gradle);
the harness must confirm pass-with-gold / fail-at-base.

**Module / Gradle task:** `:app` — `:app:testDevDebugUnitTest --tests org.wikipedia.talk.TalkPageTitleHelperTest`.

## Leniency / risk

- The tests call `linkedTitleHtml` with positional arguments, so they depend on the parameter order and
  the `href` default named in the ticket, not on the parameter names.
- The markup is compared as an exact string. The ticket states the format exactly (single quotes, `": "`
  separator) and gives worked examples, since "no behaviour change" is the requirement; an
  implementation using `"` quotes would be a behaviour change in the raw markup and fail by design.
- `subjectPageTitle` is checked by `PageTitle.equals` plus namespace/prefixedText/uri, so an
  implementation that builds a fresh `PageTitle` instead of `copy()` also passes; preservation of
  fragment/thumbnail/description and instance identity are not tested (ticket does not ask).
- The strip-then-remove-namespace order cannot be told apart by these inputs (both orders give the same
  result), so it is not pinned.
- Not tested (not in the ticket): underscores in a raw namespace (`User_talk: …` is what the base code
  renders and the reference keeps), other talk namespaces (`Wikipedia talk:` is `MAIN` per
  `Namespace.fromLegacyString` and is returned unchanged), removal vs delegation of
  `getNonTalkPageTitle`.
- `removeHTMLTags` runs through Robolectric's `android.text.Html`; `StringUtilTest` and
  `CustomHtmlParserTest` already rely on that under the same config (`sdk=24`, real `WikipediaApp`).
