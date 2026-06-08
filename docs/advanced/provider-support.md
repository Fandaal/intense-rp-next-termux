---
icon: material/cloud
---

# :material-cloud: Provider Support

IntenseRP Next v2 is designed to support multiple providers by driving their web apps and intercepting the underlying network requests.

Today, **DeepSeek**, **GLM Chat (Z.ai)**, **Moonshot**, **QwenLM**, **Perplexity**, and **HuggingChat** are implemented and usable.

**Google AI Studio** is implemented too, but it is temporarily locked by default because AI Studio currently appears to detect Patchright/automated browser sessions and can block automated message sends. You can still configure it, and you can deliberately bypass the lock with **Settings -> Advanced -> Provider Stability -> Ignore Provider Locks**.

Search Older Matching Chats is currently supported on **DeepSeek**, **GLM Chat**, **Moonshot**, **QwenLM**, and **HuggingChat**. **Perplexity** does not support chat reuse yet, and **Google AI Studio** still only has the regular single-slot Reuse Matching Chat flow for now.

!!! note "GLM status (important)"
    The GLM driver is still beta-like. It is mostly usable, but:

    - Search and Advanced Search are supported (search results are not sent to the client)
    - Login requires solving a CAPTCHA (Persistent Sessions are strongly recommended)
    - GLM model selection is supported (GLM-5.1 / GLM-5-Turbo / GLM-5V-Turbo / GLM-5 / GLM-4.7) via **Settings -> Provider Behavior -> GLM Chat -> Model**
    - Reuse Matching Chat is currently unreliable with GLM

!!! warning "Web apps change"
    Provider drivers depend on the provider's web UI and internal API shapes. If a provider updates their frontend, a driver may break until it is updated.

---

## :material-connection: How providers work (in v2)

All providers follow the same general approach:

1. Launch a real browser session (Playwright/Patchright)
2. Log in (manual or auto-login, depending on settings)
3. Trigger a generation in the provider UI (type/upload + click send)
4. Intercept the provider's internal streaming request
5. Convert the provider stream into OpenAI-style SSE deltas (`/v1/chat/completions` or `/v1/completions`)

This is why IntenseRP can present an OpenAI-compatible API even though the underlying provider is a normal web chat app.

---

## :material-flag-checkered: Provider lifecycle stages

Every provider goes through the same lifecycle:

Queued :material-arrow-right: Planning :material-arrow-right: Prototyping :material-arrow-right: Driver Implementation :material-arrow-right: Integration :material-arrow-right: Verification :material-arrow-right: Stable

### :material-palette: Stage legend (icon + color coded)

| Stage | Indicator | What it means |
|---|---|---|
| **Queued** | :material-clock-outline:{ style="color: #ADB5BD" } | In the backlog, not started |
| **Planning** | :material-lightbulb-outline:{ style="color: #74C0FC" } | Design/requirements work |
| **Prototyping** | :material-flask-outline:{ style="color: #B197FC" } | Early experiments, not production-ready |
| **Driver Implementation** | :material-hammer-wrench:{ style="color: #FF922B" } | Building the provider driver (UI + interception) |
| **Integration** | :material-connection:{ style="color: #63E6BE" } | Wiring driver into the app and API surface |
| **Verification** | :material-shield-check:{ style="color: #FFD43B" } | Stress testing, edge cases, reliability |
| **Stable** | :material-check-circle:{ style="color: #51CF66" } | Considered reliable for normal use |

---

## :material-format-list-bulleted: Current provider roadmap

Providers are prioritized in this order:

| Provider | Priority | Current stage |
|---|---:|---|
| **DeepSeek** | 1 | :material-check-circle:{ style="color: #51CF66" } **Stable** |
| **GLM Chat** | 2 | :material-check-circle:{ style="color: #51CF66" } **Stable (mostly)** |
| **Moonshot** | 3 | :material-check-circle:{ style="color: #51CF66" } **Stable (mostly)** |
| **Google AI Studio** | 4 | :material-lock-alert:{ style="color: #FF922B" } **Temporarily Locked** |
| **QwenLM** | 5 | :material-check-circle:{ style="color: #51CF66" } **Stable** |
| **Perplexity** | 6 | :material-shield-check:{ style="color: #FFD43B" } **Verification** |
| **HuggingChat** | 7 | :material-hammer-wrench:{ style="color: #FF922B" } **Driver Implementation** |

!!! note "What 'Verification' means for Moonshot"
    Moonshot is implemented and usable, but this is the first integration pass. Expect selector and stream-shape adjustments as the provider UI evolves.

!!! warning "Google AI Studio status"
    Google AI Studio's driver code and settings are still present, but normal provider selection and routing are locked for now. Enable **Ignore Provider Locks** only if you're sure your AI Studio setup can send messages from the automated browser.

!!! note "Perplexity status"
    Perplexity is implemented as an early integration. It can send prompts and stream answer text, but chat reuse/regeneration and thinking-trace forwarding are not supported yet.

!!! note "HuggingChat status"
    HuggingChat is implemented as an early integration. It supports model selection, inference provider selection, thinking effort, Exa search, uploads, chat reuse, and account rotation, but HuggingChat's web UI and monthly credits are both easy to run into. Disable spent accounts until their credits reset.

---

## :material-arrow-right: Related pages

<div class="grid cards" markdown>

-   :providers-deepseek: **DeepSeek Behavior**

    DeepThink, Search, anti-censorship, and more.

    [:arrow_right: DeepSeek Behavior](../providers/deepseek-behavior.md)

-   :providers-zai: **GLM Behavior**

    Deep Think, modes, Search status, and GLM-specific notes.

    [:arrow_right: GLM Behavior](../providers/glm-behavior.md)

-   :providers-moonshot: **Moonshot Behavior**

    Thinking, Search, file uploads, and Kimi-specific caveats.

    [:arrow_right: Moonshot Behavior](../providers/moonshot-behavior.md)

-   :providers-qwen: **QwenLM Behavior**

    Thinking, Web search, model selection, and token counting.

    [:arrow_right: QwenLM Behavior](../providers/qwen-behavior.md)

-   :providers-perplexity: **Perplexity Behavior**

    Model selection, Thinking, Search, uploads, and email-code login notes.

    [:arrow_right: Perplexity Behavior](../providers/perplexity-behavior.md)

-   :providers-huggingface: **HuggingChat Behavior**

    Model selection, inference provider, thinking effort, Exa search, and quota/account notes.

    [:arrow_right: HuggingChat Behavior](../providers/huggingchat-behavior.md)

-   :providers-aistudio: **Google AI Studio Behavior**

    AI Studio model selection, Thinking Level, Search, URL Context, and sampling controls.

    [:arrow_right: Google AI Studio Behavior](../providers/aistudio-behavior.md)

-   :material-key: **Login & Sessions**

    Auto login and persistent sessions.

    [:arrow_right: Login & Sessions](../features/login-sessions.md)

-   :material-lan: **Network & API**

    Ports, LAN access, and API key auth.

    [:arrow_right: Network & API](../features/network-api.md)

-   :material-api: **API Behavior**

    Request flow, streaming, cancellation, and queueing.

    [:arrow_right: API Behavior](api-behavior.md)

</div>

---

## :material-arrow-left: Back to Advanced

[:material-arrow-left: Advanced](../advanced.md)
