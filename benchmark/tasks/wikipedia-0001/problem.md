# Investigate citation preview rendering broken for {{Cite}} template references on Polish Wikipedia

Steps to replicate the issue (include links if applicable):

- Open an article on Polish Wikipedia in the Wikipedia Android app that uses the {{Cite}} template in references

- Tap a reference link to open the citation preview popup

- Observe the citation layout/rendering

Example provided by the user:

https://commons.wikimedia.org/wiki/File:Zrzut_ekranu_z_historii_Irlandii.jpg#%7B%7Bint%3Afiledesc%7D%7D

What happens?:

Citation previews rendered from the {{Cite}} template appear visually broken or inconsistently formatted in the Android app reference preview UI.

The issue reproduces in:

Wikipedia Android app

Wikipedia Android Beta app

The issue does not reproduce in:

iOS app

Web browsers (Chrome, Firefox, Safari)

The user noted the issue is not related to comma vs semicolon separators in author fields and is not limited to subreferences.

Additionally, {{Cite book}} references appear to render correctly under the same conditions.

What should have happened instead?:

Citation previews should render consistently and correctly in the Android app, matching the formatting seen on web browsers and iOS.

Software version (on Special:Version page; skip for WMF-hosted wikis like Wikipedia):

The beta and production versions of the app

Other information (browser name/version, screenshots, etc.):

The issue may be related to CSS rendering differences or how {{Cite}} template output is processed inside the Android app’s reference preview mechanism.

---

**Triage comment (developer):** Reproduced. The Polish `{{Cite}}` template hides parts of each
author name with `style="display:none"`, and the hidden span itself contains further spans with
text. A trimmed example of the reference HTML for one author:

```html
<span class="cite-name-before"><span class="cite-name-full">Guy</span><span class="cite-name-initials" style="display:none">G.</span><span>&nbsp;</span></span><span class="cite-lastname">Mansell</span><span class="cite-name-after" style="display:none"><span>&nbsp;</span><span class="cite-name-full">Guy</span><span class="cite-name-initials">G.</span></span>, <i>Irlandia</i>
```

The web shows "Guy Mansell, *Irlandia*"; our preview shows the hidden parts too ("Guy Mansell Guy G.").
Everything inside a hidden span has to stay hidden however deeply it is nested, several hidden
spans in a row must all disappear, ordinary spans keep their text, and some templates write the
style as `display: none` (with a space).
