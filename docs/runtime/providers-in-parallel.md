---
icon: material/source-branch
---

# :material-source-branch: Providers in Parallel

Providers in Parallel controls how many provider browser lanes IntenseRP keeps alive, and how much queued API work those lanes can process at the same time.

In other words, with this on, you can make IntenseRP open many provider browsers and let them all work on queued API requests together instead of one at a time.

:material-arrow-right: **Settings** -> **Browser & Runtime** -> **Providers in Parallel**

This feature is stable enough to use when you need it, but it is intentionally heavy. Each extra lane is another live browser session, and active concurrent requests can raise CPU, RAM, and provider-side pressure.

---

## :material-toggle-switch: Run Providers in Parallel

Turn on **Run Providers in Parallel** first. This lets IntenseRP keep more than 1 provider browser available at once.

The current provider is always included. In the provider selector it appears with a yellow checked state because it cannot be removed from the runtime while it is your current provider.

Changes apply after you restart the browser with **Stop** -> **Start**.

---

## :material-tune: Providers in Parallel Mode

The mode dropdown replaces the older separate queue/full-parallel toggles.

| Mode | What it does |
| --- | --- |
| **One Instance per Provider** | Keeps selected provider browsers warm, but the API queue still processes one request at a time. |
| **One Instance per Provider + Concurrent Requests** | Lets different provider lanes answer queued API requests at the same time. Same-provider requests still wait for that provider's lane. |
| **Multiple Instances per Provider + Concurrent Requests** | Also allows selected providers to launch multiple account-backed instances, so same-provider requests can overlap when enough accounts/profiles are available. |

If you only switch between providers often, the first mode may be enough. If multiple API clients share IntenseRP, the concurrent request modes are usually the useful ones.

---

## :material-format-list-checks: Provider Lanes

Use **Provider Lanes** to choose which providers participate in Providers in Parallel.

In **Multiple Instances per Provider + Concurrent Requests**, each enabled provider also shows a small instance count. The default is **1**, and IntenseRP caps the real launch count to the usable saved accounts/profiles available for that provider.

If you ask for 3 DeepSeek instances but only have 2 usable DeepSeek accounts saved, IntenseRP launches 2 and logs the cap. If there are no saved accounts, it falls back to one normal manual lane.

!!! tip "Account selection"
    If **Prefer the Least Used Account** is enabled, startup account selection favors saved accounts with older last-used timestamps before newer ones.

---

## :material-rocket-launch-outline: Startup

By default, parallel lanes launch one after another.

**Launch Provider Lanes Concurrently** starts active lanes at the same time. This can make startup faster, but it can also make the startup burst heavier.

If concurrent launch is useful but too slow/heavy, enable **Launch in Batches** and set **Max Lanes per Batch**. IntenseRP waits for the current batch to finish launching or failing before moving to the next one.

---

## :material-routes: Routing

When multiple providers are active, API requests use provider-prefixed model IDs such as `deepseek-auto`, `glm-chat`, `huggingchat-reasoner`, `aistudio-reasoner`, or `mimo-auto`.

The model ID tells IntenseRP which provider lane should receive the request. If you send a model ID for a provider that is not enabled in the parallel runtime, IntenseRP returns an error instead of guessing.

If **Use Universal Model Names** is enabled, providers with real model pickers can expose real-model IDs too. Exact conflicts get provider prefixes so overlapping model names still route cleanly. (e.g. Gemini 3.1 Pro on Perplexity / Google AI Studio, or Qwen models in QwenLM / HuggingChat)

---

## :material-alert-circle-outline: Good to Know

- Browser restarts are required after changing provider selection, mode, or instance counts.
- Model and loadout settings remain provider-level, so multiple instances for the same provider share those choices.
- If a managed provider browser crashes or is closed manually, the parallel runtime may stop and ask you to start it again.

The normal single-provider runtime is still the lightest setup. Providers in Parallel is for when the extra lanes are worth the extra browser weight.

---

## :material-arrow-left: Back to Browser & Runtime

[:material-arrow-left: Browser & Runtime Overview](../runtime.md)
