# Provenance notes (not shown to agents)

- Source: authored for this benchmark (drafted by the building agent with claude-opus-5-5 at base 0c7ee9b4682512217e01d829fb0b6d068d268724).

# wikipedia-0012 — reviewer notes

**What it checks.** `LinkHandler.onExternalLinkClicked` passes the decoded `params` query value of a
GeoHack link to the existing `StringUtil.geoHackToLocation(params: String?): Location?` and opens
the Places map when it returns a location, otherwise the browser. At base that function only
recognises the hemisphere form (one regex, `find` anywhere in the string: `D[_M[_S]]_N|S_[D_][M_][S_]E|W`),
so GeoHack's other documented `params` form, signed decimals `lat;lon` (optionally followed by
`_type:…`, `_region:…`, `_scale:…`), falls back to the browser. The task: parse that form, ignore
the trailing `_key:value` parts, keep the hemisphere forms exactly as they are, and return no
location for out-of-range (lat outside [-90, 90], lon outside [-180, 180]) or unparsable input.
It is realistic: small parser extension in an existing utility, found by tracing the GeoHack
link handling (brownfield navigation from the symptom to the function), with a range-validation
twist that a quick "add a second regex" fix can miss. The signature is unchanged, so no new API is
named in the ticket (D-020 not triggered).

**Production files changed (gold).**
- `app/src/main/java/org/wikipedia/util/StringUtil.kt` — new decimal branch in
  `geoHackToLocation` (regex `^(-?[\d.]+);(-?[\d.]+)(_|$)`, `toDoubleOrNull`), and a private
  `createValidLocation(lat, lon)` used by both branches that returns null outside the valid range.

**Test file added.** `app/src/test/java/org/wikipedia/util/StringUtilGeoHackTest.kt`
(Robolectric runner, as in the existing `StringUtilTest`, because `android.location.Location` is
an Android class; `robolectric.properties` sets sdk=24). Doubles compared with delta 1e-6. The
existing `StringUtilTest.testGeoHackToLocation` is untouched and still passes with the gold.

| Test method | Inputs | Expected at base |
|---|---|---|
| `testSignedDecimalCoordinates` | `51.5072;-0.1276`, `-33.8568;151.2153` | fail (assertNotNull: base returns null) |
| `testSignedDecimalCoordinatesWithExtraParams` | `-33.8568;151.2153_type:landmark`, `51.5072;-0.1276_type:city_region:GB_scale:300000` | fail (base returns null) |
| `testHemisphereCoordinatesUnchanged` | `40.6892_N_74.0445_W_region:US`, `51_30_N_0_7_W_region:GB` (D_M), `42_21_30_N_71_3_37_W` (D_M_S), `33_51_25_S_151_12_55_E_type:landmark` (S/E) | pass (pins existing behaviour; expected values computed from the base formula) |
| `testOutOfRangeSignedDecimalCoordinates` | `95;10`, `-95;10`, `10;190`, `10;-190_type:landmark` → null | pass at base (base parses no decimals); fails for a fix that parses decimals without range validation |
| `testInvalidCoordinates` | `null`, `""`, `test`, `abc;def`, `51.5072;`, `;-0.1276` → null | pass at base; fails for a fix that crashes (`toDouble`) or returns a location for malformed input |

F2P: the first two. P2P guards: the last three.

**Module / Gradle task.** `:app` — `:app:testDevDebugUnitTest` (filter
`org.wikipedia.util.StringUtilGeoHackTest`).

**Risks / notes.**
- Not compiled or run here (no Gradle per the brief). Base and gold results for every test input
  were checked by simulating both regexes and the arithmetic in Python (same regex syntax; Kotlin
  `Regex.find` = Python `re.search`; unmatched groups → `"0"` as in `ifEmpty`).
- The gold applies the range check to both forms (so an out-of-range hemisphere value such as
  `95_N_10_E` now also yields null). The tests only check out-of-range for the decimal form, so a
  fix that validates only decimals also passes; hemisphere tests use valid inputs only.
- The tests pin the behaviour at the parser (`geoHackToLocation` returns null), while the visible
  symptom is in link handling. A fix that keeps the parser permissive and validates in
  `LinkHandler` instead would fail `testOutOfRangeSignedDecimalCoordinates`; the ticket's
  requirements are worded as rules for "converting the GeoHack `params` value into a location …
  must produce no location", which points at the conversion without naming it.
- Not pinned (ticket does not ask): anchoring of the decimal form at the start of `params`
  (GeoHack reads it from the first `_` piece), whitespace around `;`, a leading `+`, boundary
  values exactly ±90/±180, and the pre-existing `NumberFormatException` for inputs like
  `1.2.3_N_4_E` in the hemisphere branch (left as is).
