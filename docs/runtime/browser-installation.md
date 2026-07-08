---
icon: material/download-circle
---

# :material-download-circle: Browser Installation

Browser Installation covers the Chromium bundle IntenseRP downloads through Playwright/Patchright.

:material-arrow-right: **Settings** -> **Browser & Runtime** -> **Browser Installation**

Most people can leave this alone. IntenseRP uses Patchright's default browser download CDNs, and the **Browser Manager** handles install, reinstall, and delete actions for you.

---

## :material-cloud-download: Chromium Download Mirror

:material-arrow-right: **Settings** -> **Browser & Runtime** -> **Browser Installation** -> **Chromium Download Mirror**

This optional field sets the download host Patchright uses when IntenseRP installs or reinstalls Chromium.

It is mainly useful when the official Playwright/Patchright browser CDN is blocked in your region or by your network. Put the mirror base URL here, then run **Install** or **Reinstall** from **Tools -> Browser Manager**.

!!! warning "Use a trusted mirror"
    This replaces Patchright's default browser download CDNs for install and reinstall actions. A broken mirror can make installation fail, and an untrusted mirror can provide malware. Clear the field to go back to the official defaults.

The mirror must use the same path layout Patchright expects. For the current Chrome for Testing builds, Patchright appends paths like this to the URL you enter:

```text
builds/cft/<browser-version>/win64/chrome-win64.zip
```

!!! warning "Do not add this path yourself"
    The mirror URL you enter should be the base URL only. Patchright appends the rest automatically. If you add the path yourself, Patchright will try to download from a non-existent location.

So if the mirror URL is:

```text
https://mirror.example/playwright
```

Patchright will try a URL shaped like:

```text
https://mirror.example/playwright/builds/cft/<browser-version>/win64/chrome-win64.zip
```

!!! note "Install only"
    This does not proxy provider websites after the browser starts. Use **Browser Proxy URL** in **Browser Environment** for provider-page traffic.

---

## :material-arrow-left: Back to Browser & Runtime

[:material-arrow-left: Browser & Runtime Overview](../runtime.md)
