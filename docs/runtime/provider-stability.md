---
icon: material/shield-check-outline
---

# :material-shield-check-outline: Provider Stability

Provider Stability keeps the runtime honest when provider windows close unexpectedly or when a provider is temporarily safety-locked.

:material-arrow-right: **Settings** -> **Browser & Runtime** -> **Provider Stability**

## :material-alert-circle-outline: Provider Window Warnings

**Warn if the Provider Window Closes** shows a notification when the active provider browser closes or crashes unexpectedly.

Most users should leave this enabled. If a provider window disappears, requests may stop working until you start the browser again.

## :material-lock-alert: Provider Locks

Provider locks are temporary safety blocks for providers that are implemented, but currently known to fail in a way that would make normal automation misleading or unusable.

:material-arrow-right: **Settings** -> **Browser & Runtime** -> **Provider Stability** -> **Ignore Provider Locks**

Right now, there is no default provider lock active. Google AI Studio is selectable again because its **Humanize Mouse Movements** reliability mode is enabled by default.

!!! warning "The override is not a fix"
    **Ignore Provider Locks** only skips IntenseRP's safety lock if a future temporary lock is active. It does not make a provider more automation-friendly.

---

## :material-arrow-left: Back to Browser & Runtime

[:material-arrow-left: Browser & Runtime Overview](../runtime.md)
