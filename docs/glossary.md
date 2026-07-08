---
icon: material/translate
---

# :material-translate: Glossary

This page translates the names, acronyms, and weird bits that show up around IntenseRP. More of a pocket dictionary for when a setting doesn't make sense, if you will!

!!! tip "Quick mental model"
    IntenseRP is a local bridge. Your client talks to IntenseRP through an OpenAI-compatible API, IntenseRP drives a provider website in a real browser, then it sends the provider's answer back to your client.

## :material-map-marker-path: Core Flow

| Term | Plain meaning | Notes |
|---|---|---|
| IntenseRP / IRP | The local desktop app and API bridge. | "IRP" is just the short name people use when typing fast. |
| IRP Next v2 | The current rewritten version of IntenseRP Next. | v2 uses FastAPI, PySide6, and Playwright/Patchright instead of the older v1 stack. |
| Client | The app sending requests to IntenseRP. | Usually SillyTavern, but any OpenAI-compatible client can work. |
| Provider | The AI service IntenseRP is driving in a browser. | Examples: DeepSeek, GLM Chat, Kimi / Moonshot, QwenLM, Perplexity, HuggingChat, Google AI Studio, and Xiaomi MiMo. |
| Provider web UI | The normal website interface for a provider. | IntenseRP automates this page instead of calling the provider's official API. |
| Driver | Provider-specific automation code. | A driver knows which buttons, streams, model pickers, and quirks belong to one provider. |
| OpenAI-compatible API | An API shaped like OpenAI's chat/completions endpoints. | It lets clients reuse their OpenAI-style connection settings with IntenseRP. |
| Endpoint | The URL your client sends requests to. | Default: `http://127.0.0.1:7777/v1`. See [Network & API](features/network-api.md). |
| `/v1` | The API route prefix IntenseRP exposes. | The main routes are `/v1/models`, `/v1/chat/completions`, and `/v1/completions`. |
| Model ID | The model name sent by the client. | In IntenseRP, many model IDs are really behavior presets rather than exact provider models. |
| Behavior preset | A model ID that selects a behavior mode. | Example: `deepseek-reasoner` turns DeepThink on, while `deepseek-chat` turns it off. |
| Real model ID | A model ID that maps to an actual provider model picker entry. | Used for providers with real model selection, such as GLM Chat, QwenLM, Perplexity, HuggingChat, Google AI Studio, and Xiaomi MiMo. |
| UMM / Universal Model Names | Provider-neutral model names like `intenserp-auto`. | Handy if you switch providers often. See [Universal Model Names](features/universal-model-names.md). |
| Hotswap | Switching providers from the main window while the app is running. | It saves a trip into Settings. See [Hotswaps](features/hotswaps.md). |
| Loadout | A named set of formatting and provider behavior settings. | Experimental, provider-scoped, and useful for quickly changing "profiles" of settings. |

## :material-api: API And Networking

| Term | Plain meaning | Notes |
|---|---|---|
| API | Application Programming Interface. | The part of IntenseRP that clients call instead of clicking buttons. |
| LLM | Large Language Model. | The model behind the provider chat, like a Gemini, Qwen, GLM, or DeepSeek model. |
| UI | User Interface. | Usually means the visible provider website or the IntenseRP desktop window. |
| Chat completions | The modern chat-style OpenAI route. | Uses messages with roles like `system`, `user`, and `assistant`. |
| Text completions | The older prompt-only route. | Uses one raw `prompt`; IntenseRP skips chat formatting here. |
| Streaming | Sending answer text gradually as it appears. | Usually enabled with `stream: true`. |
| SSE | Server-Sent Events. | The streaming format IntenseRP uses for `data:` chunks. |
| Delta | A small piece of a streamed response. | In OpenAI-style streams, text arrives through `delta.content`. |
| JSON | JavaScript Object Notation. | The data format used for API requests and responses. |
| Queue | The line of API requests waiting to run. | Normal mode processes one generation at a time. |
| FIFO | First in, first out. | The default queue order: earlier requests run before later ones. |
| Request Queue Panel | Optional main-window view of active and waiting requests. | Useful when a client retries and quietly builds up a queue. |
| Port | The number after the host in the endpoint. | Default is `7777`; change it if another app already uses that port. |
| `localhost` / `127.0.0.1` | "This same computer." | The safest default: only apps on your own machine can connect. |
| LAN | Local Area Network. | Your home/work network. Enable LAN access only when another device needs to connect. |
| IP address | A network address for a device. | Used for LAN access and IP whitelist rules. |
| IP whitelist | A list of IP addresses allowed to use the API. | Helpful when LAN access is enabled. See [IP Whitelist](advanced/ip-whitelist.md). |
| API key | A secret token required by the API when key auth is enabled. | Adds a basic security layer for local/LAN use. |
| Bearer token | The `Authorization: Bearer ...` header format. | SillyTavern sends this automatically when you fill in its API key field. |
| `reasoning_effort` | OpenAI-style request field for reasoning level. | IntenseRP can map it to supported provider thinking controls. |
| `temperature` | Sampling control for randomness. | Currently applied in Google AI Studio when the web UI exposes the control. |
| `top_p` | Sampling control for nucleus sampling. | Another compatibility field, also applied mainly through AI Studio today. |
| `max_tokens` / Max Output Tokens | Output length budget. | For AI Studio, this maps to the web UI's max output tokens control when available. |

## :material-format-text: Formatting And Names

| Term | Plain meaning | Notes |
|---|---|---|
| Formatting pipeline | How chat messages become one provider-ready prompt. | Name detection -> template -> divider -> injection -> send. |
| Template | The pattern used for each message. | Example: `{{name}}: {{content}}`. See [Formatting](features/formatting.md). |
| Placeholder | A value IntenseRP replaces inside a template. | Common placeholders: `{{name}}`, `{{role}}`, and `{{content}}`. |
| Divider | Text inserted between formatted messages. | Default is a newline. `\n\n` gives extra spacing. |
| Injection | Extra instruction text added before or after the formatted chat. | Supports `{{user}}` and `{{char}}` placeholders. |
| Name Detection | How IntenseRP figures out who is speaking. | It checks message objects, IR2 blocks, and Classic IntenseRP tags in order. |
| Message Objects | OpenAI-style messages with a `name` field. | Recommended when your client can send names cleanly. |
| STMP | SillyTavern MultiPlayer. | RossAscends's STMP can be patched so IntenseRP receives per-message names. |
| STMP Patcher | Utility that patches STMP to include names. | See [STMP Patcher](util-reference/stmp-patcher.md). |
| IR2 | IntenseRP 2 name tags. | Uses tags like `[[IR2u]]...[[/IR2u]]` and `[[IR2a]]...[[/IR2a]]`. |
| Classic IntenseRP tags | Older `DATA1` / `DATA2` name format. | `DATA1` is the character name, `DATA2` is the user name. Yes, backwards. |
| System message | A high-priority instruction message from the client. | Some providers support moving leading system messages into a native system prompt field. |
| System prompt field | A provider's separate field for system instructions. | Available on providers like Google AI Studio and HuggingChat. |
| Macro | A small inline command inside a prompt. | Examples include `[[think]]`, `[[nothink]]`, `[[search]]`, and `[[nosearch]]` on supported providers. |

## :material-head-cog: Provider Behavior

| Term | Plain meaning | Notes |
|---|---|---|
| Provider Behavior | The settings section for provider-specific controls. | This is where Thinking, Search, uploads, model pickers, and quirks usually live. |
| DeepThink / Deep Think | Provider-specific reasoning mode names. | DeepSeek says DeepThink; GLM writes it as Deep Think. Same general idea. |
| Thinking / Reasoning | Letting a provider use its reasoning mode before answering. | Names vary by provider, but docs usually group them together. |
| Thinking Level | Google AI Studio's reasoning strength control. | Maps to values like Minimal, Low, Medium, and High when supported. |
| Thinking Effort | HuggingChat's reasoning effort selector. | Can be Low, Medium, High, or provider/model defaults. |
| Send Thinking / Send DeepThink | Whether reasoning text is forwarded to the API client. | When off, IntenseRP tries to strip thinking traces before the client sees them. |
| Search / Web Search | Letting a provider use its web search tool. | Source/tool metadata is usually filtered out of API responses. |
| Grounding | Provider search/tool output used to support an answer. | Google AI Studio calls this Google Search grounding. |
| URL Context | AI Studio tool for browsing URLs found in prompts. | Separate from normal Search. |
| Exa | The search provider used by HuggingChat's search toggle. | In docs this may appear as Exa MCP search. |
| MCP | Model Context Protocol. | In this project it mainly appears in HuggingChat search wording, such as Exa MCP. |
| Send As Text File | Upload the prompt as a `.txt` file instead of typing it. | Useful for very long prompts or providers with fragile textareas. |
| Text File Message / Filler | Text sent alongside an uploaded prompt file. | Some providers refuse file-only messages, because of course they do. |
| Reuse Matching Chat / Clean Regeneration | Reopen/regenerate a matching previous chat instead of creating a new one. | Helpful for SillyTavern swipes/regenerations. |
| Search Older Matching Chats | Reuse one of several older cached matching chats. | Also called multi-slot cache in older/internal wording. |
| Delete Chat After Reply | Delete the provider-side chat after a successful response. | Usually incompatible with Reuse Matching Chat. |
| Repetition Buster | GLM duplicate-prompt workaround. | Sends a throwaway prompt first so GLM treats the real request as fresh. |
| Blocked-Response Handling | Provider-specific handling for blocked/refusal-like output. | Behavior differs by provider; it does not override provider policy or guarantee any result. |
| CAARS | AI Studio-only prelude for blocked-response handling. | Runs a secondary model before continuing with the main one. |
| Preflight Next Chat | Prepare a blank AI Studio chat after a response finishes. | Best-effort speed-up for the next request. |
| Safety Filters | Provider-side content filters. | AI Studio exposes sliders; IntenseRP can lower them, but cannot make the model ignore all safety behavior. |

## :material-account-switch: Accounts, Browser, And Maintenance

| Term | Plain meaning | Notes |
|---|---|---|
| Saved Account | A provider login row stored in IntenseRP. | Used for auto-login, account rotation, pinning, and disabling accounts. |
| Auto Login | IntenseRP fills saved credentials into supported provider login pages. | If CAPTCHA or provider friction appears, manual login may still be needed. |
| CAPTCHA | Anti-bot challenge during login. | GLM and some other providers may ask for one. |
| Persistent Sessions | Reusing a saved browser profile so you stay logged in. | Stores cookies and local storage in the config directory. |
| Browser profile | The saved browser data for one provider/account identity. | Deleting it logs that identity out. |
| Profile Compatibility Warning | Warning that a saved profile may be from an older browser version. | Usually fixed by logging in successfully with the current browser. |
| Chromium | The browser engine IntenseRP launches. | No longer used in IRP. |
| Chrome for Testing | Google's test-friendly Chrome build. | Now used in IRP (as of 2.8.3). |
| Playwright | Browser automation library. | IntenseRP uses it to control the provider web UI. |
| Patchright | Playwright-compatible browser automation fork used here. | Helps IntenseRP drive provider pages in a real browser. |
| Browser Manager | Utility window for installing, reinstalling, or deleting the browser bundle. | See [Browser Manager](util-reference/browser-manager.md). |
| Browser proxy | Optional proxy passed to provider browser contexts. | Useful for providers with regional access issues, especially MiMo. |
| WAF | Web Application Firewall. | A provider-side protection layer that can sometimes dislike automated browsers. |
| Config directory | The folder where IntenseRP stores settings, keys, profiles, and logs. | Treat it as sensitive. It can contain credentials and session data. |
| App flags | Hidden persistent app switches. | Advanced/internal state stored separately from normal settings. |
| Logfile | A saved log file on disk. | Useful for debugging crashes or provider breakage. |
| Activity Log | The small log view in the main IntenseRP window. | Good for quick status without opening the full console. |
| Console Window | Separate window with runtime logs. | Helpful when troubleshooting a request live. |
| Console dump | Export of console contents. | Useful when sharing logs after something breaks. |
| Bug report bundle | A zip with selected diagnostics. | Built to share enough context for debugging while redacting some sensitive values. |
| Remote Control | Experimental browser page for controlling IntenseRP from another device. | Still respects IP whitelist rules when enabled. |
| Providers in Parallel | Runtime mode that keeps multiple provider browsers alive. | Requests route by model ID. |
| Concurrent Requests | Runtime queue mode that lets different provider lanes work at once. | Now part of Providers in Parallel Mode. |
| Multiple Instances per Provider | Providers in Parallel mode with multiple lanes per provider. | Needs saved accounts/profiles and uses much more RAM. |

---

[:material-arrow-left: Back to Home](index.md)
