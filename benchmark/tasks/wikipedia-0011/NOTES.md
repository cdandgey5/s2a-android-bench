# Provenance notes (not shown to agents)

- Source: authored for this benchmark (drafted by the building agent with claude-opus-5-5 at base 0c7ee9b4682512217e01d829fb0b6d068d268724).

# wikipedia-0011 — reviewer notes

**Category:** feature. **Base:** upstream `0c7ee9b4682512217e01d829fb0b6d068d268724`.

## What the task checks and why it is realistic

The app checks collection (reading list) names in two places, and the two checks disagree. The
create/rename dialog trims the input and then calls `otherTitles.contains(it)`, which is exact and
case-sensitive. The "Save collection" dialog for shared and recommended lists calls
`currentReadingLists.any { it.title == listTitle }` on the untrimmed text. As a result a user can create `Road trip` and
`road TRIP`, save a shared list as `Road trip ` with a trailing space, and create `Café` twice when
one copy is decomposed (`Cafe` + U+0301). No length limit exists either. The task asks for a
single pure-Kotlin validator, `ReadingListTitleValidator.validate(title, existingTitles)`. It
returns a sealed `Result` (`Valid(title)` / `Empty` / `Duplicate` / `TooLong`) and uses
`MAX_LENGTH = 255`. The rules are: trim; blank → `Empty`; length is checked on the trimmed title;
duplicates are matched case-insensitively (locale-independent) after NFC normalisation, against
trimmed existing titles. Both dialogs must use it. This is the kind of consistency or
data-hygiene ticket the Wikipedia Android team files in Phabricator. The sync code already
NFC-normalises remote list names (`SyncedReadingLists.RemoteReadingList.name()`) and compares
with `StringUtil.normalizedEquals`, so NFC matches the existing convention. The value 255 is the
size of the list-name column in the MediaWiki ReadingLists extension (`rl_name`, 255; recalled,
not re-verified offline, see Risks). The app keeps similar server-mirrored limits in `Constants`:
`MAX_READING_LISTS_LIMIT = 100` and `MAX_READING_LIST_ARTICLE_LIMIT = 5000`.

## Production files changed

- `app/src/main/java/org/wikipedia/readinglist/ReadingListTitleValidator.kt` (new): the
  validator object, `MAX_LENGTH`, and the sealed `Result`.
- `app/src/main/java/org/wikipedia/readinglist/ReadingListTitleDialog.kt`: `onTextChanged` now
  branches on the validator result (`Empty` / `Duplicate` / `TooLong` → button disabled,
  `Valid` → enabled). The error text and button wiring are unchanged.
- `app/src/main/java/org/wikipedia/readinglist/ReadingListPreviewSaveDialogView.kt`:
  `validateTitleAndList` branches on the validator result. On `Valid` it still requires at least
  one selected page and passes the trimmed title to `onSuccess`.
- `app/src/main/res/values/strings.xml`: new `reading_list_title_too_long` ("Collection name
  can't be longer than %d characters.").
- `app/src/main/res/values-qq/strings.xml`: qq documentation for `reading_list_title_too_long`,
  so that `TranslationTests` keeps passing.

## Hidden tests

New file `app/src/test/java/org/wikipedia/readinglist/ReadingListTitleValidatorTest.kt` (plain
JUnit4, no Robolectric). At base every test fails to compile, because `ReadingListTitleValidator`
does not exist.

| Test method | What it pins | Expected at base |
|---|---|---|
| `testBlankTitleIsEmpty` | `"  "` and `""` → `Empty` | compile error |
| `testValidTitleIsTrimmed` | `" Road trip "` → `Valid` with title `"Road trip"` | compile error |
| `testDuplicateIgnoresCase` | `"road TRIP"` vs `["Road trip"]` → `Duplicate` | compile error |
| `testDuplicateIgnoresCaseRegardlessOfDefaultLocale` | same as above with the default locale set to `tr-TR` (restored in `finally`) → `Duplicate` | compile error |
| `testDuplicateIgnoresUnicodeNormalization` | `"Cafe\u0301"` vs `["Café"]` and `"Café"` vs `["Cafe\u0301"]` → `Duplicate` | compile error |
| `testDuplicateIgnoresWhitespaceAroundExistingTitle` | `"Road trip"` vs `[" Road trip "]` → `Duplicate` | compile error |
| `testTitleAtMaxLengthIsValid` | `"a" * MAX_LENGTH` → `Valid` with the same title | compile error |
| `testTitleAtMaxLengthAfterTrimmingIsValid` | `" " + "a" * MAX_LENGTH + " "` → `Valid` (the length is measured after trimming) | compile error |
| `testTitleOverMaxLengthIsTooLong` | `"a" * (MAX_LENGTH + 1)` → `TooLong` | compile error |

The tests use only `is` checks plus `Valid.title`. Subtypes can therefore be objects or classes,
and `Result` can be a sealed class or a sealed interface. It must be nested as
`ReadingListTitleValidator.Result`, which the ticket says. Two tests go beyond the brief's list,
and each pins a rule the ticket states explicitly: the Turkish-locale case and the
trim-before-length case. The reverse-direction NFC assertion also pins a stated rule ("both sides
NFC").

## Modules / Gradle tasks

- `:app:testDevDebugUnitTest`, specifically `org.wikipedia.readinglist.ReadingListTitleValidatorTest`
  (F2P).
- In the same task, `org.wikipedia.language.TranslationTests` must stay green (P2P), because a
  string and its qq entry were added.

## Risks

- **Not compiled or run by the author**, because the brief forbids builds. The code is short and
  uses only `java.text.Normalizer` and Kotlin's `lowercase()` (`Locale.ROOT`). `data object` is
  already used in the repo.
- **The 255 limit was taken from memory** of the ReadingLists extension schema
  (`rl_name VARBINARY(255)`, i.e. bytes) and was not verified offline. The tests reference
  `ReadingListTitleValidator.MAX_LENGTH` rather than a literal, and they use ASCII only. An
  implementation that counts UTF-16 units, code points or UTF-8 bytes therefore passes, and so
  does one that picks a different constant value, although the ticket says 255.
- The Turkish-locale test changes the JVM default locale. It restores it in `finally`, so other
  test classes in the same fork are unaffected.
- Precedence between `TooLong` and `Duplicate` is deliberately left unspecified and untested.
