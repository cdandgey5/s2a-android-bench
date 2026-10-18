# notification error - too many values supplied for parameter notwikis. the limit is 50. on read and hidden, new notifications

- wikipedia alpha android app v. 50569-alpha-2026-03-06

- tap bell icon (notifications) on app top right corner

- actual outcome: error: too many values supplied for parameter notwikis. the limit is 50.

- desired outcome: view notifications (without going through below workaround)

- workaround (new and old notifications): tapping notification preferences in notifications

- video (read and hidden notifications): https://commons.wikimedia.org/wiki/File:Error-too-many-values-supplied-for-parameter-notwikis-the-limit-is-50-alpha-2026-03-06.webm

---

**Developer comment:** We should stop sending our own list of wikis altogether and always ask for
notifications from all wikis (`notwikis=*`), for the notification screen and for the background
poll alike. Please drop the wiki-list parameter from the API call as part of this, i.e.
`Service.getAllNotifications(filter: String?, continueStr: String?)`, and make sure a
notification from a wiki we have no site entry for does not crash the screen.
