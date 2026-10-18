# ipv6 host says invalid

### App version

3.11.4

### Android version

LineageOS (Android 16

### Device model

OnePlus Nord N200 5G

### First occurred

_No response_

### Steps to reproduce

Open network proxy settings
Choose socks as type
Set "::" or "[::]' as host
Set port to 9050
Press ok

### Expected behaviour

The app should accept the host

### Current behaviour

The app says the host is invalid.

---

**Maintainer comment:** Confirmed. While fixing this, please move the host check into
`UrlChecker.isValidHost(String host)` in the `net:common` module so that it can be unit-tested,
and use it in the proxy dialog. It should accept `localhost`, host names and IPv4 addresses as
before, and IPv6 addresses with or without square brackets (`::`, `[::]`, `::1`,
`::ffff:192.168.0.1`, …). The host field takes only a host — the port has its own field — so
`host:port`, `[::1]:9050`, unbalanced brackets, malformed addresses and anything with spaces stay
invalid.
