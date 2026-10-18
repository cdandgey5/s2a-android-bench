# Feed url entry field does not accept URLs without a TLD.

### App version

3.12.0f

### Android version

16

### Device model

_No response_

### First occurred

_No response_

### Steps to reproduce

1. Enter a feed url without a TLD such as "http://localhost:8080/feed"

### Expected behaviour

The app should allow all valid URLs, or have a way of bypass the validation.

### Current behaviour

Error message: "The RSS adress you entered is not valid", with no way to bypass.

---

**Maintainer comment:** Agreed, the check is too strict. Please put the decision "is this text a
feed URL?" into `UrlChecker.isValidUrl(String url)` in the `net:common` module (so it can be
unit-tested) and use it wherever the add-podcast screen validates the URL field. Anything that
looks like a web address keeps working, with or without a scheme (`example.com/feed`,
`192.168.1.2:8080/feed`). With an explicit `http://` or `https://` scheme (any letter case) it
should also accept hosts without a TLD (`http://localhost:8080/feed`, `https://podcast-server/feed`)
and IPv6 literals (`http://[::1]:8080/feed`). Plain words such as `podcast`, `some podcast` or
`podcast-server` are search queries, not URLs, and broken input (`http://`, `http:localhost/feed`,
`http:/localhost/feed`, a non-numeric port, a host with a space) is rejected.
