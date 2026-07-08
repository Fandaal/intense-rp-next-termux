---
icon: material/cloud
---

# :material-cloud: Providers

Each provider has its own Behavior page because the web UIs don't all expose the same controls, and some of them have unique quirks that need extra explanation. If you are looking for a specific toggle, model picker, or provider quirk, this is the place to find it.

!!! tip "App-wide settings live elsewhere"
    Accounts, sessions, formatting, ports, API keys, and logging are covered under :material-star-four-points: [Features](features.md). This section is for provider-specific controls like Thinking, Search, model pickers, uploads, blocked-response handling, and provider quirks.

---

<div class="grid cards" markdown>

-   :providers-deepseek: **DeepSeek Behavior**

    DeepThink, Search, file uploads, blocked-response handling, and chat reuse.

    [:arrow_right: Open DeepSeek](providers/deepseek-behavior.md)

-   :providers-zai: **GLM Behavior**

    Deep Think, Search, Advanced Search, Tools, model selection, token counting, uploads, and GLM-specific caveats.

    [:arrow_right: Open GLM](providers/glm-behavior.md)

-   :providers-moonshot: **Kimi Behavior**

    Thinking, Search, file uploads, blocked-response handling, and Kimi account-tier notes.

    [:arrow_right: Open Kimi](providers/moonshot-behavior.md)

-   :providers-qwen: **QwenLM Behavior**

    Thinking, Web Search, model selection, token counting, uploads, and provider guardrails.

    [:arrow_right: Open QwenLM](providers/qwen-behavior.md)

-   :providers-perplexity: **Perplexity Behavior**

    Model selection, Thinking, Search, uploads, and email-code login notes.

    [:arrow_right: Open Perplexity](providers/perplexity-behavior.md)

-   :providers-huggingface: **HuggingChat Behavior**

    Model selection, inference provider, Thinking Effort, Exa search, uploads, and account limits.

    [:arrow_right: Open HuggingChat](providers/huggingchat-behavior.md)

-   :providers-aistudio: **Google AI Studio Behavior**

    Gemini model selection, Thinking Level, Search grounding, URL Context, uploads, sampling, and humanized mouse movement.

    [:arrow_right: Open AI Studio](providers/aistudio-behavior.md)

-   :providers-xiaomi: **Xiaomi MiMo Behavior**

    MiMo model selection, thinking output filtering, uploads, regional availability notes, token usage, and chat reuse.

    [:arrow_right: Open MiMo](providers/mimo-behavior.md)

</div>

---

## :material-compass-outline: Quick Picker

| Provider | Best doc to read when... |
|---|---|
| **DeepSeek** | You need DeepThink/Search controls, duplicate-prompt reuse, or the DeepSeek refusal-message workaround. |
| **GLM Chat** | You need Tools, token counting, model picker behavior, Repetition Buster, or timing/instability notes. |
| **Kimi / Moonshot** | You use Kimi's Thinking/Search modes, Google login, uploads, or want to understand its account-tier caveats. |
| **QwenLM** | You need Qwen Thinking, Web Search, model selection, token counting, file uploads, or guardrail behavior. |
| **Perplexity** | You use Perplexity's model picker, Thinking/Search behavior, uploads, or email-code login. |
| **HuggingChat** | You need model/provider selection, Thinking Effort, Exa search, uploads, or help with monthly credit limits. |
| **Google AI Studio** | You use Gemini through AI Studio, need model/Thinking/Search controls, etc. |
| **Xiaomi MiMo** | You need MiMo model selection, thinking output filtering, proxy setup, or regional availability notes. |

Provider docs are intentionally a little more detailed than the overview pages, though they're still focused on practical user-facing info, as I wanted to avoid dumping too much technicalities into the main flow. If you want to understand more about how a provider integration works under the hood, you're going to have to dig through the code or ask in the community.

---

## :material-arrow-right-bold: Related Pages

<div class="grid cards" markdown>

-   :material-key: **Login & Sessions**

    Auto Login and persistent browser sessions for supported providers.

    [:arrow_right: Open Login & Sessions](features/login-sessions.md)

-   :material-account-switch: **Accounts & Credentials**

    Saved accounts, rotation, retry-on-failure, pinning, and disabling account rows.

    [:arrow_right: Open Accounts & Credentials](features/accounts.md)

-   :material-cloud: **Provider Support**

    Provider roadmap, lifecycle stages, and implementation status.

    [:arrow_right: Open Provider Support](advanced/provider-support.md)

</div>
