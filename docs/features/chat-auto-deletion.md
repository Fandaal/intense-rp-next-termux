---
icon: material/delete-clock-outline
---

# :material-delete-clock-outline: Chat Auto-Deletion

## :material-toggle-switch: Delete Chat After Reply

`Delete Chat After Reply` is the setting name. The idea is pretty simple but useful - let IntenseRP use the provider chat for the request, then clean that chat up automatically once the reply is done.

This is meant for people who like the provider browser staying neat instead of filling up with one-off chats all day.

!!! warning "This can be noticeably slower"
    IntenseRP has to do extra browser/API cleanup around every request, so this can slow requests down quite a bit.

---

## :material-check-decagram: Supported providers

Right now this works on:

- DeepSeek
- GLM Chat
- Moonshot / Kimi
- QwenLM
- HuggingChat

It does **not** apply to **Perplexity**, **Google AI Studio**, or **Xiaomi MiMo**. Perplexity and MiMo do not have stable cleanup paths yet, and AI Studio already starts chats with its incognito mode, so there is nothing useful for IntenseRP to auto-delete there.

---

## :material-arrow-right: Where to enable it

You enable it from the provider Behavior page for the provider you are using:

- **Provider Behavior** -> **DeepSeek** -> **Delete Chat After Reply**
- **Provider Behavior** -> **GLM Chat** -> **Delete Chat After Reply**
- **Provider Behavior** -> **Moonshot** -> **Delete Chat After Reply**
- **Provider Behavior** -> **QwenLM** -> **Delete Chat After Reply**
- **Provider Behavior** -> **HuggingChat** -> **Delete Chat After Reply**

---

## :material-cog-refresh: How it works

After a successful reply finishes, IntenseRP grabs the current provider chat ID and asks the provider to delete that chat.

So that providers don't give us a broken session, IntenseRP creates a new chat right before deleting the old one. That way the session stays alive and we just lose the old chat. If the request is aborted or errors out, IntenseRP leaves the chat alone.

!!! danger "The chat buttons stay in the UI"
    Since we send a constructed request to the provider, the frontend doesn't know the chat was deleted. So the old chat buttons stay there, but they won't work if you click them. Just ignore them, or hit refresh if you want them to disappear.

---

## :material-link-off: On compatibility

This feature does **not** work together with **Reuse Matching Chat** or **Search Older Matching Chats**.

That's not a bug, it's by design. Those features rely on old chats sticking around so IntenseRP can jump back to them, but auto-deletion does the opposite on purpose. So if you turn on auto-deletion, the reuse/search toggles get disabled and vice versa.

---

## :material-shuffle-variant: GLM Repetition Buster

This *does* work with **GLM Chat -> Repetition Buster**.

When GLM sends its throwaway cache-buster prompt, IntenseRP deletes that temporary cache-buster chat as well before sending the real request. So you still get the cache-busting behavior without leaving extra junk behind.

!!! warning "This can make GLM requests even slower"
    The repetition buster already adds extra overhead by sending the cache-buster prompt first, and auto-deletion adds more overhead on top of that by doing extra cleanup after both the cache-buster and the real request. So if you use both, expect GLM requests to be quite a bit slower than usual.

---

## :material-link-variant: Related pages

- [:material-refresh: DeepSeek Behavior](../providers/deepseek-behavior.md#delete-chat-after-reply)
- [:material-refresh: GLM Behavior](../providers/glm-behavior.md#delete-chat-after-reply)
- [:material-refresh: Moonshot Behavior](../providers/moonshot-behavior.md#delete-chat-after-reply)
- [:material-refresh: QwenLM Behavior](../providers/qwen-behavior.md#delete-chat-after-reply)
- [:material-refresh: HuggingChat Behavior](../providers/huggingchat-behavior.md#delete-chat-after-reply)
- [:material-layers-triple-outline: Search Older Matching Chats](multi-slot-cache.md)
- [:material-file-code-outline: Loadouts](../experimental/loadouts.md)

---

## :material-arrow-left: Back to Features

[:material-arrow-left: Features](../features.md)
