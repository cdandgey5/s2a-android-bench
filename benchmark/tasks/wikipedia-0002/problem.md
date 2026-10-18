# CentralAuth cookies are sent to hosts that only look like Wikimedia domains

From a security report (coordinated disclosure; the reporter's PoC is attached to the private task).

The app keeps the session cookies it receives per host. When it makes a request to a host for
which it has no cookies of its own, it reuses the user's CentralAuth cookies
(`centralauth_Token`, `centralauth_User`, …) from another Wikimedia host so that the user stays
logged in across projects. The check that decides whether the target host is a Wikimedia host
is too loose: a request to `https://evil-wikipedia.org/w/api.php`,
`https://en.wikipedia.org.example.com/w/api.php` or `https://wikipedia.org.example.com/…` also
receives the user's CentralAuth cookies. Any page or link that makes the app call such a host
can collect them.

**Expected:**

- CentralAuth cookies are carried over only to Wikimedia hosts — `wikipedia.org`, `wikimedia.org`,
  `wikidata.org` and their subdomains (e.g. `en.wikipedia.org`, `zh-yue.m.wikipedia.org`,
  `meta.wikimedia.org`, `www.wikidata.org`) — and only from cookies that were stored for a
  Wikimedia host in the first place;
- only cookies whose name starts with `centralauth_` (exact case) are carried over; per-wiki
  session cookies never are;
- a host still gets all of its own cookies;
- expired cookies are neither sent nor kept.
