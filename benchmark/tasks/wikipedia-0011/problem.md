**Collections: names that differ only in case, Unicode form or surrounding spaces are accepted as new collection names**

**Steps to replicate the issue** (include links if applicable):

1. In Saved, create a collection named `Road trip`.
2. Tap "Create new" again and type `road TRIP`.
3. Open a shared collection link (or a recommended reading list) and tap Save. In the "Save collection" dialog, change the suggested name to `Road trip ` (with a trailing space), or to `road trip`.
4. Have a collection named `Café` (precomposed é, e.g. synced from another device) and type `Cafe` followed by a combining acute accent (U+0301), as some keyboards produce.
5. Paste a very long name (a few hundred characters) into either dialog.

**What happens?**:

- Step 2: no error is shown and OK is enabled, so the user ends up with two collections that look the same in the list. The duplicate check only matches the exact, case-sensitive string.
- Step 3: the "Save collection" dialog does not trim the name at all, so `Road trip ` is not seen as a duplicate and is saved with the trailing space; `road trip` is accepted as well. The two dialogs don't agree on what a valid name is.
- Step 4: `Café` and `Cafe` + U+0301 render identically but are treated as different names.
- Step 5: any length is accepted, although the server-side Reading Lists storage caps list names at 255, so such a list can't be synced reliably. The app should cap names at 255 characters as well.

**What should have happened instead?**:

Both the create/rename collection dialog and the "Save collection" dialog should validate the name with the same rules, through one shared validator. Please add:

```kotlin
package org.wikipedia.readinglist

object ReadingListTitleValidator {
    const val MAX_LENGTH = 255

    fun validate(title: String, existingTitles: Collection<String>): Result

    sealed interface Result {          // a sealed class is fine too
        data class Valid(val title: String) : Result
        data object Empty : Result
        data object Duplicate : Result
        data object TooLong : Result
    }
}
```

(i.e. `ReadingListTitleValidator.Result.Valid`, `.Empty`, `.Duplicate`, `.TooLong`.)

Rules for `validate(title, existingTitles)`:

- Surrounding whitespace is trimmed from `title` before anything else.
- If nothing is left after trimming, the result is `Empty`.
- If the trimmed title is longer than `MAX_LENGTH` (255) characters, the result is `TooLong`. A name of exactly 255 characters is allowed; leading/trailing spaces don't count towards the limit.
- If the trimmed title matches any of `existingTitles`, the result is `Duplicate`. When comparing:
  - the existing titles are trimmed too (an existing ` Road trip ` blocks `Road trip`);
  - case is ignored, using a locale-independent case conversion, so the outcome doesn't depend on the device language (`road TRIP` matches `Road trip`, also on a device set to Turkish);
  - both sides are compared in Unicode NFC form, so `Cafe` + U+0301 matches `Café` and vice versa.
- Otherwise the result is `Valid`, carrying the trimmed title (` Road trip ` → `Valid("Road trip")`).

In the dialogs, keep the current behaviour per outcome:

- `Empty`: no error, positive button disabled.
- `Duplicate`: the existing "Collection "%s" already exists." error, positive button disabled.
- `TooLong`: an error telling the user the name is too long (mention the limit), positive button disabled. New messages need their qq documentation as usual.
- `Valid`: no error, positive button enabled (the "Save collection" dialog still also requires at least one article to be selected), and the trimmed name is the one that gets saved.

**Environment**: Wikipedia Android app, current `main`.
