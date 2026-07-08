---
icon: material/star-four-points
---

# :material-star-four-points: Features

Use this page as a map of the app-wide docs. If you are looking for provider-specific toggles, model pickers, search controls, or provider quirks, go to :material-cloud: [Providers](providers.md) instead.

!!! info "Provider settings moved"
    DeepSeek, GLM, Moonshot, QwenLM, Perplexity, HuggingChat, Google AI Studio, and Xiaomi MiMo Behavior settings now live in the dedicated [:material-cloud: Providers](providers.md) section.

---

<div class="grid cards" markdown>

-   :material-account-switch: **Accounts & Credentials**

    Saved accounts, account rotation, pinning, disabling rows, and retrying with another account.

    [:arrow_right: Open Accounts](features/accounts.md)

-   :material-format-text: **Formatting**

    Templates, presets, name detection, message dividers, and injection.

    [:arrow_right: Open Formatting](features/formatting.md)

-   :material-layers-triple-outline: **Search Older Matching Chats**

    Reuse older cached chats on supported providers instead of only checking the latest one.

    [:arrow_right: Open Search Older Matching Chats](features/multi-slot-cache.md)

-   :material-delete-clock-outline: **Chat Auto-Deletion**

    Delete the provider-side chat after a reply finishes, where supported.

    [:arrow_right: Open Chat Auto-Deletion](features/chat-auto-deletion.md)

-   :material-account-multiple: **STMP Support**

    Patch RossAscends's STMP so character names can reach IntenseRP reliably.

    [:arrow_right: Open STMP Support](features/stmp-support.md)

-   :material-key: **Login & Sessions**

    Auto Login, persistent sessions, saved browser profiles, and session cleanup.

    [:arrow_right: Open Login & Sessions](features/login-sessions.md)

-   :material-lan: **Network & API**

    Port settings, LAN access, API keys, model IDs, and OpenAI-compatible endpoints.

    [:arrow_right: Open Network & API](features/network-api.md)

-   :material-tag-text-outline: **Universal Model Names**

    Optional provider-neutral model IDs like `intenserp-auto`.

    [:arrow_right: Open Universal Model Names](features/universal-model-names.md)

-   :material-console: **Console & Logging**

    Console window, log levels, file logging, console export, and bug report helpers.

    [:arrow_right: Open Console & Logging](features/console-logging.md)

-   :material-swap-horizontal: **Hotswaps**

    Switch providers from the main window without reopening Settings.

    [:arrow_right: Open Hotswaps](features/hotswaps.md)

-   :material-cog: **System**

    Config storage, updates, profiles, backup/restore, and maintenance settings.

    [:arrow_right: Open System](features/system.md)

</div>

---

## :material-compass-outline: Which Page Do I Need?

| If you want to... | Start here |
|---|---|
| Add accounts, rotate accounts, or recover from a bad account row | [:material-account-switch: Accounts & Credentials](features/accounts.md) |
| Fix names, prompt shape, templates, or injection | [:material-format-text: Formatting](features/formatting.md) |
| Stay logged in between restarts | [:material-key: Login & Sessions](features/login-sessions.md) |
| Change the port, connect from another device, or require API keys | [:material-lan: Network & API](features/network-api.md) |
| Use `intenserp-auto` instead of provider-prefixed model IDs | [:material-tag-text-outline: Universal Model Names](features/universal-model-names.md) |
| See what happened during a failed request | [:material-console: Console & Logging](features/console-logging.md) |
| Switch providers without going back into Settings | [:material-swap-horizontal: Hotswaps](features/hotswaps.md) |
| Move config storage, back up settings, or reset browser profiles | [:material-cog: System](features/system.md) |
| Find provider-specific Thinking/Search/upload/model controls | [:material-cloud: Providers](providers.md) |

!!! tip "When in doubt"
    If the setting name includes a provider name, it probably belongs in :material-cloud: [Providers](providers.md). If it affects the local API server, logging, formatting, accounts, or app maintenance, it probably belongs here.

---

## :material-arrow-right-bold: Next Steps

<div class="grid cards" markdown>

-   :material-rocket-launch: **Getting Started**

    New here? Set up the app and connect to SillyTavern.

    [:arrow_right: Get Started](getting-started.md)

-   :material-cloud: **Providers**

    Tune DeepSeek, GLM, Moonshot, QwenLM, Perplexity, HuggingChat, Google AI Studio, or Xiaomi MiMo.

    [:arrow_right: Browse Providers](providers.md)

-   :material-bug: **Troubleshooting**

    Use the checklist when the browser, login, or API connection misbehaves.

    [:arrow_right: Troubleshoot](hands/troubleshooting.md)

</div>
