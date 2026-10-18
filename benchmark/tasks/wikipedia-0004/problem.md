# Introduce additional replaceable parameters to fundraising configuration json.

Currently the fundraising json structure supports a client-side parameter called $platform;, which gets replaced by the respective client with the corresponding platform name (Android / iOS). This is used in the action url string for filling in the platform name for analytics purposes.

We propose adding the following additional parameters:

- $formattedId; -- which would take the place of the entire value of the current wmf_source url parameter. The notion of "formatted ID" is already something that is firmly established within our code. Specifically, the formatted ID is a string that is made up of these components: [language][country]_[campaignID]_[platform]. So then, the formatted ID effectively becomes something of this form: enUS_US_2025_Android. But if you look closely at the url parameters specified in the current campaign configuration, this is exactly what the wmf_source parameter is trying to be. Except currently, the wmf_source parameter must be manually composed by the creators of the campaign structure, which can lead to errors and inconsistencies such as observed in T415692. If we introduce a $formattedId; parameter, and simply plug it into the url as wmf_source=$formattedId;, the authors of the campaign configuration will no longer need to worry about composing it properly, and will eliminate this class of bugs.

- $country; -- replaced by the current GeoIP country of the client.

- $language; -- replaced by the current language selected by the client.

- $appVersion; -- replaced by the current app version string.

- $appInstallId; -- replaced by the current app install ID.

We are also agreeing that this would necessitate bumping the structure version number to 3.

iOS-specific notes

- $formattedId; -The iOS codebase uses the naming metricsID for this particular type of ID. iOS should also rename codebase references from "metricsID" to "formattedID" to match Android.

- $country; -- replace with Locale.current.region?.identifier

- $language; -- replace by the current article wiki language code OR language variant code if it applies. We construct the article's wiki project before displaying campaigns here. The wiki project enum has .languageCode and .languageVariantCode helper properties.

- $appVersion; trace appendingAppVersionAndAppInstallID for how we pull this.

- $appInstallId; - trace appendingAppVersionAndAppInstallID for how we pull this.

Testing config

A config for testing has already been bumped to version 3 and updated with the correct url parameters. Raw view is located at https://test.wikipedia.org/wiki/MediaWiki:AppsCampaignConfig.json?action=raw.

---

**Status update (Android):** `$formattedId;`, `$country;` and `$language;` are in and the
structure version is 3. `$appVersion;` and `$appInstallId;` are not replaced yet; the test config
already uses them (`…&appVersion=$appVersion;&appInstallId=$appInstallId;`), so they currently
reach the donation page verbatim.
