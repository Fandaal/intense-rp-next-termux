---
icon: providers/perplexity
---

# :providers-perplexity: Perplexity Behavior

This page covers the settings that control how IntenseRP interacts with **Perplexity** (`perplexity.ai`).

Perplexity is powerful, but its web app is fairly strict. IntenseRP drives the same composer you use in the browser, watches the `perplexity_ask` stream, and forwards only the assistant answer text to the OpenAI-compatible API.

!!! warning "Account capability limitations"
    Perplexity exposes different controls depending on the account. If your account does not expose model or Thinking controls, IntenseRP skips those steps and uses whatever the Perplexity UI allows.

!!! note "Special thanks"
    Huge **thank you** to [Yurushia](https://github.com/twgok123) for Perplexity testing help during development.

---

## :material-tune: Modes (model IDs)

In IntenseRP Next v2, the `model` you select in SillyTavern is mostly a **behavior preset**, not the same thing as Perplexity's own model picker.

For Perplexity, these model IDs map to simple behavior presets:

| Model ID | Behavior |
|---|---|
| `perplexity-auto` | Uses your IntenseRP settings |
| `perplexity-chat` | Forces Thinking off |
| `perplexity-reasoner` | Forces Thinking on when the account/model allows it |

---

## :material-chip: Real Perplexity model selection (web UI)

IntenseRP can switch Perplexity's real model picker in the web UI when your account exposes it:

:material-arrow-right: **Settings** -> **Provider Behavior** -> **Perplexity** -> **Model**

The dropdown includes **Best (Auto)** plus the account-tier model entries IntenseRP knows how to select. Exact labels live in Settings, since Perplexity's picker can change faster than this page should try to keep up with.

!!! note "Account-tier controls"
    Perplexity only exposes some controls on some accounts. If a control is unavailable, IntenseRP skips it and uses the current Perplexity UI defaults.

---

## :material-auto-fix: Spaces Mode

Spaces mode makes IntenseRP use an **IntenseRP Next** Space instead of the normal Perplexity chat page.

:material-arrow-right: **Settings** -> **Provider Behavior** -> **Perplexity** -> **Use Perplexity Spaces**

When enabled, IntenseRP opens `https://www.perplexity.ai/spaces`, looks for an existing Space named `IntenseRP Next`, and creates it if it isn't there yet. The Space ID is remembered only for the current browser session, so if the Space is deleted IntenseRP will warn in the logs and recreate it next time.

After the Space is ready, prompts, model selection, Thinking, Search, and file uploads keep using the same Perplexity composer flow as normal chat mode.

### Space Instructions

You can also move leading system messages into the Space instructions field:

:material-arrow-right: **Settings** -> **Provider Behavior** -> **Perplexity** -> **Paste System Instructions Into Space Instructions**

Only leading system messages are moved. Once a user or assistant message appears, later system messages stay in the regular prompt. Perplexity caps Space instructions at 8000 characters, so anything that doesn't fit also stays in the prompt.

!!! tip "Loadouts"
    Both Spaces settings are Perplexity Behavior settings, so Perplexity loadouts can turn Spaces mode and Space-instruction syncing on or off per loadout.

---

## :material-head-cog: Thinking

### Enable Thinking

When enabled, IntenseRP tries to toggle Perplexity Thinking before sending the prompt.

:material-arrow-right: **Settings** -> **Provider Behavior** -> **Perplexity** -> **Enable Thinking**

Some models force Thinking on, and some account tiers do not expose the toggle. In those cases IntenseRP logs what happened and keeps the request moving.

### Send Thinking

Perplexity does not currently expose usable thinking traces in the intercepted stream. The setting exists for mode/loadout consistency, but IntenseRP does **not** forward `<think>` content for Perplexity yet.

:material-arrow-right: **Settings** -> **Provider Behavior** -> **Perplexity** -> **Send Thinking**

---

## :material-magnify: Search

Perplexity Web search can be toggled through the composer tools menu.

:material-arrow-right: **Settings** -> **Provider Behavior** -> **Perplexity** -> **Enable Search**

!!! note "Search payloads"
    Perplexity streams search/source data around the answer. IntenseRP strips those provider-specific payloads and forwards only the assistant text.

---

## :material-file-upload: File Upload Mode

Instead of pasting your full prompt into Perplexity's editor, IntenseRP can upload it as a text file.

:material-arrow-right: **Settings** -> **Provider Behavior** -> **Perplexity** -> **Send As Text File**

If Perplexity indicates that the upload cap is reached, IntenseRP falls back to pasting the prompt as normal text for that request.

### Text File Message

Optional text pasted alongside the uploaded prompt file.

:material-arrow-right: **Settings** -> **Provider Behavior** -> **Perplexity** -> **Text File Message**

### File Upload Timeout

Controls how long IntenseRP waits for the send button to become available after selecting the file.

:material-arrow-right: **Settings** -> **Provider Behavior** -> **Perplexity** -> **File Upload Timeout**

### Message Send Timeout

Controls how long IntenseRP waits for the send button to appear after text entry in normal, non-file mode.

:material-arrow-right: **Settings** -> **Provider Behavior** -> **Perplexity** -> **Message Send Timeout (s)**

---

## :material-key: Login notes

Perplexity uses email-code login. Auto Login can enter the saved email and click through the first step, but you still need to type the 6-digit code in the browser window.

!!! warning "Persistent Sessions strongly recommended"
    Perplexity sessions are much nicer when the browser profile stays signed in. Keep **Persistent Sessions** on unless you have a specific reason to reset the provider profile each time.

See: [:material-key: Login & Sessions](../features/login-sessions.md)

---

## :material-translate: UI language requirement

The Perplexity driver currently expects the web UI language to be English (`en` / `en-US`). If the page is in another language, IntenseRP may fail to find the Sign In label, model menu, or tools menu reliably.

If you see a warning about Perplexity UI language:

1. Change Perplexity language to **English**
2. Reload the page (F5 / Ctrl+R)
3. Retry / restart the browser from IntenseRP if needed

---

## :material-code-tags: Per-message macros

You can add simple `[[...]]` macros to the latest user message in SillyTavern to override certain Perplexity Behavior settings for that request only.

All macros are stripped from the message before sending it to Perplexity.

| Macro | Effect |
|------|--------|
| `[[think]]`, `[[r1]]` | Force Thinking on |
| `[[nothink]]`, `[[r0]]` | Force Thinking off |
| `[[search]]` | Force Search on |
| `[[nosearch]]`, `[[no_search]]` | Force Search off |
| `[[file]]` | Force Send As Text File on |
| `[[nofile]]` | Force Send As Text File off |

!!! note "Scope"
    Only macros from the latest user message apply. They do not persist across requests.

---

## :material-format-list-checks: Quick Reference

| Setting | What It Does | Default |
|---------|--------------|---------|
| **Model** | Selects Perplexity's real model picker when available | Best (Auto) |
| **Enable Thinking** | Toggles Perplexity Thinking where available | Off |
| **Send Thinking** | Reserved; no thinking traces are forwarded yet | Off |
| **Enable Search** | Enables Perplexity Web search | Off |
| **Use Perplexity Spaces** | Uses an IntenseRP-managed Space instead of normal chat | Off |
| **Paste System Instructions Into Space Instructions** | Moves leading system messages into Space instructions | Off |
| **Send As Text File** | Uploads prompt as .txt | Off |
| **Text File Message** | Text pasted alongside uploaded file | (empty) |
| **File Upload Timeout** | Seconds to wait after upload | 20 |
| **Message Send Timeout (s)** | Seconds to wait for send button | 8 |

---

## :material-arrow-left: Back to Providers

[:material-arrow-left: Providers Overview](../providers.md)
