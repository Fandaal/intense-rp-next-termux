---
icon: material/earth
---

# :material-earth: Browser Environment

Browser Environment controls the launch-time hints IntenseRP passes to provider pages.

:material-arrow-right: **Settings** -> **Browser & Runtime** -> **Browser Environment**

The settings here cover a few launch-time browser hints:

- **Preferred Browser Locale** defaults to **English (en-US)**. It affects browser language signals such as `navigator.language`, request language headers, and locale-sensitive formatting.
- **Browser Timezone** defaults to **System Default**. The built-in override is **New York (`America/New_York`)**.
- **Resize Viewport With Window** is off by default. It lets the provider page viewport follow the real browser window size instead of Playwright's fixed viewport.
- **Browser Proxy URL** is optional. It routes provider browser contexts through an HTTP, HTTPS, SOCKS4, or SOCKS5 proxy.

This is best-effort, not a magic cloak. Saved provider preferences, account settings, cookies, local storage, and IP geolocation can still matter.

!!! tip "Recommended default"
    Keep the locale on **English (en-US)** unless you have a specific reason not to. IntenseRP's provider drivers expect English UI text, so this tends to be the most predictable choice.

Timezone is more situational. Leave it on **System Default** unless you specifically need a browser page to report New York time.

---

## :material-fit-to-screen-outline: Resize Viewport With Window

:material-arrow-right: **Settings** -> **Browser & Runtime** -> **Browser Environment** -> **Resize Viewport With Window**

By default, Playwright/Patchright gives provider pages a fixed viewport. That keeps existing behavior predictable, but on some systems the real browser window can resize while the page viewport stays stuck at the original size. The result is the empty-space windows or clipped content you sometimes see when maximizing or resizing the provider browser window.

Turn this on if maximizing or resizing the provider browser window doesn't resize the actual page area. IntenseRP will launch the provider browser context with Playwright's fixed viewport disabled, so the page viewport follows the browser window instead.

!!! note "Restart required"
    This setting applies when the provider browser context is created. Stop and start the provider browser after changing it.

---

## :material-lan-connect: Browser Proxy URL

:material-arrow-right: **Settings** -> **Browser & Runtime** -> **Browser Environment** -> **Browser Proxy URL**

This is a global provider-browser proxy. Leave it blank to connect directly.

Supported examples:

```text
http://127.0.0.1:8080
https://proxy.example:8443
socks4://127.0.0.1:1080
socks5://user:pass@127.0.0.1:1080
```

The scheme (`http`, `https`, `socks4`, or `socks5`) tells Playwright/Patchright which proxy type to use. Username and password can be included in the URL when your proxy requires authentication.

!!! note "Restart required"
    Proxy settings apply when a provider browser context is created. Stop and start the provider browser after changing this.

!!! tip "MiMo-specific proxy"
    Xiaomi MiMo also has its own **Provider Behavior -> Xiaomi MiMo -> Proxy** settings. Use that when only MiMo needs a supported-region proxy and you want other providers to connect normally.

---

## :material-arrow-left: Back to Browser & Runtime

[:material-arrow-left: Browser & Runtime Overview](../runtime.md)
