# share of article displays zh-classical wiki landing page

Steps to reproduce

- settings - add language - add literary chinese (zh-classical)

- app search bar - for example - 萬國首都全覽

- after loading article - on 3 dot menu - tap share

Expected results

- load 萬國首都全覽 page: https://zh-classical.wikipedia.org/wiki/%E8%90%AC%E5%9C%8B%E9%A6%96%E9%83%BD%E5%85%A8%E8%A6%BD

Actual results

- it loads zh-classical landing page: https://zh-classical.wikipedia.org/wiki/%E7%B6%AD%E5%9F%BA%E5%A4%A7%E5%85%B8:%E5%8D%B7%E9%A6%96

Stack trace

(Optional logcat output)

Environments observed

App version: r/50563-r-2025-12-11

Android OS versions: 

Device model: 

Device language:

tested on browsers: fenix nightly (2025-12-18T09:56:01) and samsung internet (27.0.0.79)

---

**Developer comment:** The same happens for the other wikis whose language code starts with
`zh-` but which are separate wikis rather than variants of Chinese Wikipedia (`zh-min-nan`,
`zh-yue`): links to their articles must use the plain `https://<code>.wikipedia.org/wiki/<Title>`
form.
