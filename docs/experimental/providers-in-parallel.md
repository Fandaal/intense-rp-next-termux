---
icon: material/source-branch
---

# :material-source-branch: Providers in Parallel (Experimental)

This one is exactly what it sounds like: instead of keeping just 1 provider browser alive, IntenseRP can keep multiple provider browsers open at the same time and route requests between them.

It is neat, and can actually save you time if you use a lot of different models often, BUT it is also *extremely* heavy on resources, and it is still a bit rough around the edges.

!!! warning "Experimental and heavy"
    This feature opens extra browser windows and keeps their sessions loaded in memory.

    If your machine is already struggling with 1 provider window, this setting will make things much worse. RAM usage can easily jump from ~200-300MB to ~1-2GB with 3+ providers active.

---

## :material-toggle-switch: Enable it

:material-arrow-right: **Settings** -> **Advanced** -> **Experimental Features** -> **Run Providers in Parallel**

After you enable it, you also get per-provider toggles right under that setting.

- The **current provider** is always forced on.
- The other toggles let you choose which other providers you want to keep alive in parallel.
- Temporarily locked providers, such as Google AI Studio right now, stay forced off unless **Ignore Provider Locks** is enabled under **Advanced** -> **Provider Stability**.
- If you also want requests themselves to overlap, turn on **Parallelize API Request Queue** after this.
- If you also want multiple account-backed instances for the same provider, turn on **Full Parallelization** after the queue mode.
- Changes only apply after you **restart the browser** with **Stop -> Start**.

If fewer than 2 providers end up enabled, IntenseRP quietly falls back to the normal single-provider behavior.

---

## :material-monitor-multiple: What actually happens

When the feature is active, IntenseRP launches 1 browser window per selected provider.

Each provider keeps using its own normal stuff (accounts, sessions, cookies, etc.) but they all run at the same time instead of just 1.

At startup, each provider also logs which profile/account it selected. If one of those startup picks came from a pinned Saved Accounts row, the log line includes `[PINNED]`.

!!! warn "Might not be worth it"
    Most of those browser windows are idle until you send a request that belongs to them. Do keep that in mind if you don't jump between providers often, as the extra windows will just consume resources without much benefit.

---

## :material-api: Model routing

While this mode is active, routing is done by the **provider-prefixed model IDs**:

- `deepseek-auto` / `deepseek-chat` / `deepseek-reasoner`
- `glm-auto` / `glm-chat` / `glm-reasoner`
- `moonshot-auto` / `moonshot-chat` / `moonshot-reasoner`
- `qwen-auto` / `qwen-chat` / `qwen-reasoner`
- `perplexity-auto` / `perplexity-chat` / `perplexity-reasoner`
- `huggingchat-auto` / `huggingchat-chat` / `huggingchat-reasoner`
- `aistudio-auto` / `aistudio-chat` / `aistudio-reasoner` (only when AI Studio is unlocked)

`GET /v1/models` returns the variants for every enabled provider.

!!! note "Universal Model Names is partial here"
    `intenserp-*` is invalid in this mode because it doesn't tell the router which provider should receive the request.

    If **Use Universal Model Names** is enabled, providers with real model pickers can also expose real-model IDs here. Only exact ID conflicts get provider prefixes, like `aistudio-gemini-3-1-pro-reasoner` and `perplexity-gemini-3-1-pro-reasoner`, so overlapping model names can route cleanly.

If you send a model ID that belongs to a provider you did **not** enable, IntenseRP returns an error instead of guessing.

---

## :material-lan-pending: Queue behavior

On its own, this feature keeps multiple provider lanes alive and routes requests to the correct one by model ID.

If you leave **Parallelize API Request Queue** off, requests are still handled one at a time globally. They just get sent to the correct already-running provider lane when their turn comes up.

If you turn **Parallelize API Request Queue** on as well, the queue becomes lane-aware:

- requests for the **same lane** still stay serialized
- requests for **different lanes** can run side by side

So you can queue a `deepseek-*` request and a `glm-*` request and let them work in parallel, while 2 `glm-*` requests still line up behind the same GLM lane unless Full Parallelization adds more GLM lanes.

[:material-arrow-right: Read Parallel Request Queue docs](parallel-request-queue.md)

If you turn **Full Parallelization** on after that, enabled providers can get more than 1 account-backed lane. That is the same-provider version: 2 DeepSeek requests can overlap only when DeepSeek has multiple full-parallel instances available.

[:material-arrow-right: Read Full Parallelization docs](full-parallelization.md)

---

## :material-alert-circle-outline: Good to know

- Browser restarts are still required after changing the provider selection for this feature.
- If one of the managed provider browser windows crashes or gets closed, IntenseRP currently stops the parallel runtime and expects you to start it again.
- This feature does not rewrite provider behavior logic. It mostly reuses the normal provider drivers and runs more than 1 of them at once.

If you want something stable and lightweight, the normal single-provider mode is still the safer choice.
