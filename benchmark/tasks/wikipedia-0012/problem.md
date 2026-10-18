# Coordinates links with decimal coordinates open in the browser instead of the map

Steps to replicate the issue

1. Open an article whose coordinates link points to GeoHack with decimal coordinates, for example
   a link to
   `https://geohack.toolforge.org/geohack.php?pagename=Sydney_Opera_House&params=-33.8568;151.2153_type:landmark`.
2. Tap the coordinates link.

What happens?

The GeoHack page is opened in the external browser.

What should have happened instead?

The location should open in the in-app Places map, the same way it already does for coordinates
links in degree form, e.g. `params=33_51_25_S_151_12_55_E_type:landmark`.

Environments observed

App version: 

Android OS versions: 

Device model: 

Device language: English

---

**Developer comment:** GeoHack accepts the `params` value either in the hemisphere form we already
handle (`D_M_S_N_D_M_S_E`, `D_M_N_D_M_E`, `D_N_D_E`) or as signed decimal latitude and longitude
separated by a semicolon: `51.5072;-0.1276`, where negative numbers mean south / west. Either form
can be followed by the usual `_key:value` parts (`_type:landmark`, `_region:GB`,
`_scale:300000`, ...), which carry no position and should be ignored.

Requirements for converting the GeoHack `params` value into a location:

- `51.5072;-0.1276` → latitude 51.5072, longitude -0.1276; `-33.8568;151.2153_type:landmark` →
  latitude -33.8568, longitude 151.2153.
- The hemisphere forms must keep producing exactly the locations they produce today (e.g.
  `40.6892_N_74.0445_W_region:US` → 40.6892, -74.0445).
- Coordinates outside the valid range (latitude outside -90..90, longitude outside -180..180, e.g.
  `95;10` or `10;190`) and values that cannot be parsed (e.g. `abc;def`, `51.5072;`) must produce no
  location at all, so that the existing fallback to the browser is used. Nothing should crash.
