from __future__ import annotations

import asyncio
import json
import secrets
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel

from drivers.providers import DriverProvider, is_provider_locked, provider_options
from utils.logger import LogLevel, Logger
from utils.resource_path import resolve_resource_path

from .sessions import REMOTE_SESSION_TTL_SECONDS, RemoteControlSessionStore


PROVIDER_ICON_MAP: dict[str, str] = {
    DriverProvider.DEEPSEEK.value: "providers/deepseek.svg",
    DriverProvider.GLM_CHAT.value: "providers/zai.svg",
    DriverProvider.MOONSHOT.value: "providers/moonshot.svg",
    DriverProvider.QWEN_LM.value: "providers/qwen.svg",
    DriverProvider.PERPLEXITY.value: "providers/perplexity.svg",
    DriverProvider.HUGGINGCHAT.value: "providers/huggingface.svg",
    DriverProvider.AI_STUDIO.value: "providers/aistudio.svg",
    DriverProvider.MIMO.value: "providers/xiaomi.svg",
}


REMOTE_STYLE_ASSETS = (
    "styles/shell.css",
    "styles/base.css",
    "styles/layout.css",
    "styles/controls.css",
    "styles/views.css",
    "styles/responsive.css",
)

REMOTE_SCRIPT_ASSETS = (
    "scripts/core.js",
    "scripts/dropdowns.js",
    "scripts/switchers.js",
    "scripts/logs.js",
    "scripts/api.js",
    "scripts/views.js",
    "scripts/shell.js",
)


@dataclass
class RemoteControlActions:
    stop: Callable[[], Awaitable[None]]
    restart: Callable[[], Awaitable[None]]
    switch_account: Callable[[], Awaitable[None]]
    hotswap: Callable[[str], Awaitable[None]]
    switch_loadout: Callable[[dict[str, str]], Awaitable[None]]
    switch_model: Callable[[dict[str, str]], Awaitable[None]]
    get_state: Callable[[], dict[str, Any]]


class RemoteLoginRequest(BaseModel):
    password: str = ""


class RemoteActionRequest(BaseModel):
    provider: str | None = None
    loadout: str | None = None
    loadouts: dict[str, str] | None = None
    model: str | None = None
    models: dict[str, str] | None = None


class RemoteControlWeb:
    BASE_PATH = "/remote"
    LOG_BACKLOG_LIMIT = 300

    def __init__(
        self,
        config_manager: Any,
        *,
        enforce_ip_whitelist: Callable[[Request], Any],
        actions: RemoteControlActions,
    ) -> None:
        self.config_manager = config_manager
        self._enforce_ip_whitelist = enforce_ip_whitelist
        self._actions = actions
        self._loop = asyncio.get_running_loop()
        self._session_store = RemoteControlSessionStore(self.config_manager.config_dir)
        self._next_log_id = 0
        self._log_history: deque[dict[str, Any]] = deque(maxlen=self.LOG_BACKLOG_LIMIT)
        for level, message in Logger.recent_messages(self.LOG_BACKLOG_LIMIT):
            self._log_history.append(
                self._make_log_event(level.value, str(message or ""))
            )
        self._log_subscribers: set[asyncio.Queue] = set()
        self._template_env = Environment(
            loader=FileSystemLoader(
                str(resolve_resource_path("remote_control", "templates"))
            ),
            autoescape=select_autoescape(("html", "xml")),
        )
        self._asset_map = self._build_asset_map()
        Logger.add_listener(self._handle_log_message)

    def _build_asset_map(self) -> dict[str, Path]:
        assets: dict[str, Path] = {
            "brand/newlogo-nobg.png": resolve_resource_path(
                "ui", "assets", "brand", "newlogo-nobg.png"
            ),
            "styles/shell.css": resolve_resource_path(
                "remote_control", "assets", "shell.css"
            ),
            "scripts/shell.js": resolve_resource_path(
                "remote_control", "assets", "shell.js"
            ),
            "icons/check.svg": resolve_resource_path("ui", "assets", "icons", "check.svg"),
            "icons/chevron-down.svg": resolve_resource_path(
                "ui", "assets", "icons", "chevron-down.svg"
            ),
            "icons/chevron-right.svg": resolve_resource_path(
                "ui", "assets", "icons", "chevron-right.svg"
            ),
            "icons/square.svg": resolve_resource_path("ui", "assets", "icons", "square.svg"),
            "icons/terminal.svg": resolve_resource_path(
                "ui", "assets", "icons", "terminal.svg"
            ),
            "icons/brain.svg": resolve_resource_path(
                "ui", "assets", "icons", "sidebar", "brain.svg"
            ),
            "icons/backpack.svg": resolve_resource_path(
                "ui", "assets", "icons", "backpack.svg"
            ),
            "fonts/Blinker-Regular.ttf": resolve_resource_path(
                "ui", "fonts", "Blinker-Regular.ttf"
            ),
            "fonts/Blinker-SemiBold.ttf": resolve_resource_path(
                "ui", "fonts", "Blinker-SemiBold.ttf"
            ),
            "fonts/Blinker-Bold.ttf": resolve_resource_path(
                "ui", "fonts", "Blinker-Bold.ttf"
            ),
            "fonts/Blinker-ExtraBold.ttf": resolve_resource_path(
                "ui", "fonts", "Blinker-ExtraBold.ttf"
            ),
        }

        for asset_path in REMOTE_STYLE_ASSETS:
            if asset_path == "styles/shell.css":
                continue
            assets[asset_path] = resolve_resource_path(
                "remote_control",
                "assets",
                "styles",
                Path(asset_path).name,
            )

        for asset_path in REMOTE_SCRIPT_ASSETS:
            if asset_path == "scripts/shell.js":
                continue
            assets[asset_path] = resolve_resource_path(
                "remote_control",
                "assets",
                "scripts",
                Path(asset_path).name,
            )

        for provider_name, icon_name in PROVIDER_ICON_MAP.items():
            provider = DriverProvider.from_setting(provider_name)
            provider_key = provider.key if provider is not None else provider_name.lower().replace(" ", "_")
            assets[f"providers/{provider_name}.svg"] = resolve_resource_path(
                "ui", "assets", "icons", icon_name
            )
            assets[f"providers/{provider_key}.svg"] = resolve_resource_path(
                "ui", "assets", "icons", icon_name
            )

        return assets

    def stop(self) -> None:
        Logger.remove_listener(self._handle_log_message)
        for queue in list(self._log_subscribers):
            try:
                queue.put_nowait(None)
            except Exception:
                pass
        self._log_subscribers.clear()

    def register_routes(self, app) -> None:
        @app.get(f"{self.BASE_PATH}")
        async def remote_home(raw_request: Request):
            return self._render_shell(raw_request, initial_view="home")

        @app.get(f"{self.BASE_PATH}/logs")
        async def remote_logs(raw_request: Request):
            return self._render_shell(raw_request, initial_view="logs")

        @app.get(f"{self.BASE_PATH}/hotswap")
        async def remote_hotswap(raw_request: Request):
            return self._render_shell(raw_request, initial_view="hotswap")

        @app.get(f"{self.BASE_PATH}/models")
        async def remote_models(raw_request: Request):
            return self._render_shell(raw_request, initial_view="model-switch")

        @app.get(f"{self.BASE_PATH}/loadouts")
        async def remote_loadouts(raw_request: Request):
            return self._render_shell(raw_request, initial_view="loadout-switch")

        @app.get(f"{self.BASE_PATH}/disconnected")
        async def remote_disconnected(raw_request: Request):
            return self._render_shell(raw_request, initial_view="disconnected")

        @app.get(f"{self.BASE_PATH}/assets/v/{{asset_version}}/{{asset_path:path}}")
        @app.get(f"{self.BASE_PATH}/assets/{{asset_path:path}}")
        async def remote_asset(
            asset_path: str,
            raw_request: Request,
            asset_version: str | None = None,
        ):
            self._ensure_route_available(raw_request)
            resolved_asset_path = self._resolve_requested_asset_path(
                asset_path,
                asset_version=asset_version,
            )
            asset = self._asset_map.get(resolved_asset_path)
            if asset is None or not asset.is_file():
                raise HTTPException(status_code=404, detail="Asset not found")
            return FileResponse(asset, headers=self._build_no_store_headers())

        @app.post(f"{self.BASE_PATH}/api/login")
        async def remote_login(payload: RemoteLoginRequest, raw_request: Request):
            self._ensure_route_available(raw_request)
            if not self._needs_auth():
                return {
                    "authenticated": True,
                    "needs_auth": False,
                    "token": None,
                    "expires_at": None,
                }

            current_password = self._get_password()
            provided_password = str(payload.password or "")
            if not secrets.compare_digest(current_password, provided_password):
                raise HTTPException(status_code=401, detail="Invalid password")

            session = self._session_store.issue_session(current_password)
            return self._build_session_response(session)

        @app.get(f"{self.BASE_PATH}/api/session")
        async def remote_session(raw_request: Request):
            session = self._authenticate_remote_request(raw_request)
            return self._build_session_response(session)

        @app.get(f"{self.BASE_PATH}/api/state")
        async def remote_state(raw_request: Request):
            self._authenticate_remote_request(raw_request)
            return self._build_remote_state()

        @app.post(f"{self.BASE_PATH}/api/action/{{action_name}}")
        async def remote_action(
            action_name: str,
            payload: RemoteActionRequest,
            raw_request: Request,
        ):
            self._authenticate_remote_request(raw_request)
            action = str(action_name or "").strip().lower()
            state = self._build_remote_state()
            if not state.get("running"):
                raise HTTPException(status_code=409, detail="Services are not running")
            if state.get("busy"):
                raise HTTPException(status_code=409, detail="Services are busy")

            action_coro: Callable[[], Awaitable[None]]
            if action == "stop":
                action_coro = self._actions.stop
            elif action == "restart":
                action_coro = self._actions.restart
            elif action == "switch-account":
                if not state.get("can_switch_account"):
                    raise HTTPException(
                        status_code=409,
                        detail="Switch Account is not currently available",
                    )
                action_coro = self._actions.switch_account
            elif action == "hotswap":
                provider = DriverProvider.from_setting(payload.provider)
                if provider is None:
                    raise HTTPException(status_code=400, detail="Invalid provider")

                allowed_targets = {
                    str(item.get("name") or "")
                    for item in (state.get("hotswap_targets") or [])
                    if isinstance(item, dict)
                }
                if provider.value not in allowed_targets:
                    raise HTTPException(status_code=400, detail="Provider is unavailable")

                action_coro = lambda provider_name=provider.value: self._actions.hotswap(
                    provider_name
                )
            elif action == "switch-loadout":
                loadout_switch = state.get("loadout_switch") or {}
                if not bool(loadout_switch.get("supported")):
                    raise HTTPException(
                        status_code=409,
                        detail="Switch Loadouts is not available right now",
                    )

                providers_by_name = {
                    str(item.get("name") or ""): item
                    for item in (loadout_switch.get("providers") or [])
                    if isinstance(item, dict)
                }
                selected_loadouts: dict[str, str] = {}

                raw_loadouts = (
                    payload.loadouts if isinstance(payload.loadouts, dict) else {}
                )
                for raw_provider, raw_loadout in raw_loadouts.items():
                    provider = DriverProvider.from_setting(raw_provider)
                    provider_name = (
                        provider.value
                        if provider is not None
                        else str(raw_provider or "").strip()
                    )
                    loadout_name = str(raw_loadout or "").strip()
                    if provider_name and loadout_name:
                        selected_loadouts[provider_name] = loadout_name

                if not selected_loadouts:
                    provider = DriverProvider.from_setting(
                        payload.provider or loadout_switch.get("current_provider")
                    )
                    loadout_name = str(payload.loadout or "").strip()
                    if provider is not None and loadout_name:
                        selected_loadouts[provider.value] = loadout_name

                if not selected_loadouts:
                    raise HTTPException(status_code=400, detail="Invalid loadout")

                changes: dict[str, str] = {}
                for provider_name, loadout_name in selected_loadouts.items():
                    provider_info = providers_by_name.get(provider_name)
                    if provider_info is None:
                        raise HTTPException(
                            status_code=400,
                            detail="Provider is unavailable",
                        )

                    allowed_loadouts = {
                        str(item.get("name") or "")
                        for item in (provider_info.get("options") or [])
                        if isinstance(item, dict)
                    }
                    if loadout_name not in allowed_loadouts:
                        raise HTTPException(
                            status_code=400,
                            detail="Loadout is unavailable",
                        )

                    current_loadout = str(
                        provider_info.get("current_loadout") or ""
                    ).strip()
                    if loadout_name != current_loadout:
                        changes[provider_name] = loadout_name

                if not changes:
                    return {
                        "ok": True,
                        "disconnect": False,
                        "action": action,
                        "remote_state": self._build_remote_state(),
                    }

                try:
                    await self._actions.switch_loadout(changes)
                except Exception as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc

                return {
                    "ok": True,
                    "disconnect": False,
                    "action": action,
                    "remote_state": self._build_remote_state(),
                }
            elif action == "switch-model":
                model_switch = state.get("model_switch") or {}
                if not bool(model_switch.get("supported")):
                    raise HTTPException(
                        status_code=409,
                        detail="Switch Models is not available right now",
                    )

                providers_by_name = {
                    str(item.get("name") or ""): item
                    for item in (model_switch.get("providers") or [])
                    if isinstance(item, dict)
                }
                selected_models: dict[str, str] = {}

                raw_models = payload.models if isinstance(payload.models, dict) else {}
                for raw_provider, raw_model in raw_models.items():
                    provider = DriverProvider.from_setting(raw_provider)
                    provider_name = (
                        provider.value
                        if provider is not None
                        else str(raw_provider or "").strip()
                    )
                    model_name = str(raw_model or "").strip()
                    if provider_name and model_name:
                        selected_models[provider_name] = model_name

                if not selected_models:
                    provider = DriverProvider.from_setting(
                        payload.provider or model_switch.get("current_provider")
                    )
                    model_name = str(payload.model or "").strip()
                    if provider is not None and model_name:
                        selected_models[provider.value] = model_name

                if not selected_models:
                    raise HTTPException(status_code=400, detail="Invalid model")

                changes: dict[str, str] = {}
                for provider_name, model_name in selected_models.items():
                    provider_info = providers_by_name.get(provider_name)
                    if provider_info is None:
                        raise HTTPException(
                            status_code=400,
                            detail="Provider is unavailable",
                        )

                    allowed_models = {
                        str(item.get("name") or "")
                        for item in (provider_info.get("options") or [])
                        if isinstance(item, dict)
                    }
                    if model_name not in allowed_models:
                        raise HTTPException(status_code=400, detail="Model is unavailable")

                    current_model = str(provider_info.get("current_model") or "").strip()
                    if model_name != current_model:
                        changes[provider_name] = model_name

                if not changes:
                    return {
                        "ok": True,
                        "disconnect": False,
                        "action": action,
                        "remote_state": self._build_remote_state(),
                    }

                try:
                    await self._actions.switch_model(changes)
                except Exception as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc

                return {
                    "ok": True,
                    "disconnect": False,
                    "action": action,
                    "remote_state": self._build_remote_state(),
                }
            else:
                raise HTTPException(status_code=404, detail="Unknown action")

            asyncio.create_task(self._run_deferred_action(action, action_coro))
            return {
                "ok": True,
                "disconnect": True,
                "action": action,
            }

        @app.get(f"{self.BASE_PATH}/api/logs/history")
        async def remote_logs_history(raw_request: Request):
            self._authenticate_remote_request(raw_request)
            return self._build_logs_history_payload()

        @app.get(f"{self.BASE_PATH}/api/logs/stream")
        async def remote_logs_stream(raw_request: Request):
            self._authenticate_remote_request(raw_request)
            after_id = self._read_after_log_id(raw_request)
            queue: asyncio.Queue = asyncio.Queue()
            self._log_subscribers.add(queue)
            history = self._log_history_after(after_id)
            return StreamingResponse(
                self._log_stream(queue, history, raw_request, after_id=after_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

    def _render_shell(self, raw_request: Request, *, initial_view: str) -> HTMLResponse:
        self._ensure_route_available(raw_request)
        template = self._template_env.get_template("shell.html")
        asset_urls = self._build_template_assets()
        initial_view_name = str(initial_view or "home")
        initial_state = {
            "needs_auth": self._needs_auth(),
            "initial_view": initial_view_name,
            "remote_state": (
                None
                if initial_view_name == "logs"
                else self._build_remote_state()
            ),
        }
        html = template.render(
            base_path=self.BASE_PATH,
            base_path_json=json.dumps(self.BASE_PATH, ensure_ascii=True),
            initial_state_json=json.dumps(
                initial_state,
                ensure_ascii=True,
                separators=(",", ":"),
            ),
            asset_urls=asset_urls,
            asset_urls_json=json.dumps(
                asset_urls,
                ensure_ascii=True,
                separators=(",", ":"),
            ),
        )
        response = HTMLResponse(html)
        response.headers.update(self._build_no_store_headers())
        return response

    def _build_template_assets(self) -> dict[str, Any]:
        provider_assets: dict[str, str] = {}
        for provider_name in provider_options():
            provider = DriverProvider.from_setting(provider_name)
            provider_key = provider.key if provider is not None else provider_name.lower().replace(" ", "_")
            provider_assets[provider_name] = self.asset_url(f"providers/{provider_key}.svg")
        return {
            "logo_url": self.asset_url("brand/newlogo-nobg.png"),
            "styles": {
                "shell": self.asset_url("styles/shell.css"),
            },
            "scripts": {
                Path(asset_path).stem: self.asset_url(asset_path)
                for asset_path in REMOTE_SCRIPT_ASSETS
            },
            "script_urls": [
                self.asset_url(asset_path) for asset_path in REMOTE_SCRIPT_ASSETS
            ],
            "fonts": {
                "regular": self.asset_url("fonts/Blinker-Regular.ttf"),
                "semibold": self.asset_url("fonts/Blinker-SemiBold.ttf"),
                "bold": self.asset_url("fonts/Blinker-Bold.ttf"),
                "extrabold": self.asset_url("fonts/Blinker-ExtraBold.ttf"),
            },
            "icons": {
                "check": self.asset_url("icons/check.svg"),
                "chevron_down": self.asset_url("icons/chevron-down.svg"),
                "chevron_right": self.asset_url("icons/chevron-right.svg"),
                "stop": self.asset_url("icons/square.svg"),
                "terminal": self.asset_url("icons/terminal.svg"),
                "brain": self.asset_url("icons/brain.svg"),
                "backpack": self.asset_url("icons/backpack.svg"),
            },
            "providers": provider_assets,
        }

    def asset_url(self, asset_path: str) -> str:
        asset_version = self._resolve_asset_version(asset_path)
        return f"{self.BASE_PATH}/assets/v/{asset_version}/{asset_path}"

    @staticmethod
    def _build_no_store_headers() -> dict[str, str]:
        return {
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        }

    def _resolve_asset_version(self, asset_path: str) -> str:
        asset = self._asset_map.get(str(asset_path or "").strip())
        if asset is None:
            return "static"

        try:
            stat_result = asset.stat()
        except OSError:
            return "static"

        return f"{stat_result.st_mtime_ns:x}-{stat_result.st_size:x}"

    @staticmethod
    def _resolve_requested_asset_path(
        asset_path: str,
        *,
        asset_version: str | None = None,
    ) -> str:
        normalized_path = str(asset_path or "").strip().lstrip("/")
        if asset_version is not None or not normalized_path.startswith("v/"):
            return normalized_path

        parts = normalized_path.split("/", 2)
        if len(parts) == 3 and parts[1]:
            return parts[2]
        return normalized_path

    def _ensure_route_available(self, raw_request: Request) -> None:
        if not self.is_enabled():
            raise HTTPException(status_code=404, detail="Remote Control is disabled")
        self._enforce_ip_whitelist(raw_request)

    def _authenticate_remote_request(self, raw_request: Request) -> dict[str, Any] | None:
        self._ensure_route_available(raw_request)
        if not self._needs_auth():
            self._session_store.sync_password(self._get_password())
            return None

        token = self._read_bearer_token(raw_request)
        if not token:
            raise HTTPException(status_code=401, detail="Missing remote-control token")

        session = self._session_store.validate_token(token, self._get_password())
        if session is None:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        return session

    @staticmethod
    def _read_bearer_token(raw_request: Request) -> str:
        auth_header = str(raw_request.headers.get("Authorization") or "")
        if not auth_header.lower().startswith("bearer "):
            return ""
        return auth_header.split(" ", 1)[1].strip()

    def is_enabled(self) -> bool:
        return bool(self.config_manager.get_setting("experimental", "enable_remote_control"))

    def _get_password(self) -> str:
        value = self.config_manager.get_setting(
            "experimental", "remote_control_password"
        )
        return str(value or "")

    def _needs_auth(self) -> bool:
        return self._get_password() != ""

    def _build_session_response(
        self,
        session: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not self._needs_auth():
            return {
                "authenticated": True,
                "needs_auth": False,
                "token": None,
                "expires_at": None,
                "ttl_seconds": None,
            }

        if session is None:
            raise HTTPException(status_code=401, detail="Invalid or expired session")

        return {
            "authenticated": True,
            "needs_auth": True,
            "token": session.get("token"),
            "expires_at": session.get("expires_at"),
            "ttl_seconds": REMOTE_SESSION_TTL_SECONDS,
        }

    def _build_remote_state(self) -> dict[str, Any]:
        raw_state = self._actions.get_state() or {}
        current_provider = DriverProvider.from_setting(raw_state.get("current_provider"))
        provider_name = current_provider.value if current_provider else DriverProvider.DEEPSEEK.value

        targets = []
        raw_targets = raw_state.get("hotswap_targets")
        if not isinstance(raw_targets, list):
            raw_targets = [
                name
                for name in provider_options(
                    include_locked=False,
                    config_manager=self.config_manager,
                )
                if name != provider_name
            ]

        for raw_target in raw_targets:
            target_provider = DriverProvider.from_setting(raw_target)
            if target_provider is None or target_provider.value == provider_name:
                continue
            if is_provider_locked(target_provider, self.config_manager):
                continue
            targets.append(
                {
                    "name": target_provider.value,
                    "icon_url": self.asset_url(f"providers/{target_provider.key}.svg"),
                }
            )

        model_provider_items: list[dict[str, Any]] = []
        raw_model_providers = raw_state.get("model_switch_providers")
        if isinstance(raw_model_providers, list):
            for raw_provider_info in raw_model_providers:
                if not isinstance(raw_provider_info, dict):
                    continue

                provider = DriverProvider.from_setting(raw_provider_info.get("name"))
                if provider is None:
                    continue

                options: list[dict[str, Any]] = []
                raw_options = raw_provider_info.get("options")
                if isinstance(raw_options, list):
                    for raw_option in raw_options:
                        if isinstance(raw_option, dict):
                            option_name = str(raw_option.get("name") or "").strip()
                        else:
                            option_name = str(raw_option or "").strip()
                        if not option_name:
                            continue
                        options.append({"name": option_name})

                if not options:
                    continue

                model_provider_items.append(
                    {
                        "name": provider.value,
                        "key": provider.key,
                        "icon_url": self.asset_url(f"providers/{provider.key}.svg"),
                        "current_model": str(
                            raw_provider_info.get("current_model") or ""
                        ).strip(),
                        "options": options,
                    }
                )

        if not model_provider_items:
            model_switch_provider = (
                DriverProvider.from_setting(raw_state.get("model_switch_current_provider"))
                or current_provider
                or DriverProvider.DEEPSEEK
            )
            raw_model_options = raw_state.get("model_switch_options")
            model_options: list[dict[str, Any]] = []
            if isinstance(raw_model_options, list):
                for raw_option in raw_model_options:
                    option_name = str(raw_option or "").strip()
                    if not option_name:
                        continue
                    model_options.append({"name": option_name})

            if model_options:
                model_provider_items.append(
                    {
                        "name": model_switch_provider.value,
                        "key": model_switch_provider.key,
                        "icon_url": self.asset_url(f"providers/{model_switch_provider.key}.svg"),
                        "current_model": str(
                            raw_state.get("model_switch_current_model") or ""
                        ).strip(),
                        "options": model_options,
                    }
                )

        raw_model_current_provider = DriverProvider.from_setting(
            raw_state.get("model_switch_current_provider")
        )
        model_current_provider = (
            raw_model_current_provider.value
            if raw_model_current_provider is not None
            else (
                model_provider_items[0]["name"]
                if model_provider_items
                else provider_name
            )
        )
        if not any(item.get("name") == model_current_provider for item in model_provider_items):
            model_current_provider = (
                model_provider_items[0]["name"]
                if model_provider_items
                else provider_name
            )

        current_model = ""
        model_options: list[dict[str, Any]] = []
        for provider_info in model_provider_items:
            if provider_info.get("name") == model_current_provider:
                current_model = str(provider_info.get("current_model") or "").strip()
                raw_options = provider_info.get("options")
                model_options = raw_options if isinstance(raw_options, list) else []
                break

        model_switch_supported = bool(
            raw_state.get("model_switch_supported", False)
        ) and bool(model_provider_items)
        model_switch_parallel = bool(raw_state.get("model_switch_parallel", False))

        loadout_provider_items: list[dict[str, Any]] = []
        raw_loadout_providers = raw_state.get("loadout_switch_providers")
        if isinstance(raw_loadout_providers, list):
            for raw_provider_info in raw_loadout_providers:
                if not isinstance(raw_provider_info, dict):
                    continue

                provider = DriverProvider.from_setting(raw_provider_info.get("name"))
                if provider is None:
                    continue

                options: list[dict[str, Any]] = []
                raw_options = raw_provider_info.get("options")
                if isinstance(raw_options, list):
                    for raw_option in raw_options:
                        if isinstance(raw_option, dict):
                            option_name = str(raw_option.get("name") or "").strip()
                        else:
                            option_name = str(raw_option or "").strip()
                        if not option_name:
                            continue
                        options.append({"name": option_name})

                if not options:
                    continue

                loadout_provider_items.append(
                    {
                        "name": provider.value,
                        "key": provider.key,
                        "icon_url": self.asset_url(f"providers/{provider.key}.svg"),
                        "current_loadout": str(
                            raw_provider_info.get("current_loadout") or ""
                        ).strip(),
                        "options": options,
                    }
                )

        raw_loadout_current_provider = DriverProvider.from_setting(
            raw_state.get("loadout_switch_current_provider")
        )
        loadout_current_provider = (
            raw_loadout_current_provider.value
            if raw_loadout_current_provider is not None
            else (
                loadout_provider_items[0]["name"]
                if loadout_provider_items
                else provider_name
            )
        )
        loadout_switch_supported = bool(
            raw_state.get("loadout_switch_supported", False)
        ) and bool(loadout_provider_items)
        loadout_switch_parallel = bool(raw_state.get("loadout_switch_parallel", False))

        return {
            "running": bool(raw_state.get("running", True)),
            "busy": bool(raw_state.get("busy", False)),
            "can_switch_account": bool(raw_state.get("can_switch_account", False)),
            "current_provider": provider_name,
            "hotswap_targets": targets,
            "model_switch": {
                "supported": model_switch_supported,
                "parallel": model_switch_parallel and len(model_provider_items) > 1,
                "current_provider": model_current_provider,
                "current_model": current_model,
                "options": model_options,
                "providers": model_provider_items,
            },
            "loadout_switch": {
                "supported": loadout_switch_supported,
                "parallel": loadout_switch_parallel and len(loadout_provider_items) > 1,
                "current_provider": loadout_current_provider,
                "providers": loadout_provider_items,
            },
        }

    async def _run_deferred_action(
        self,
        action_name: str,
        action_coro: Callable[[], Awaitable[None]],
    ) -> None:
        try:
            await asyncio.sleep(0.15)
            await action_coro()
        except Exception as exc:
            Logger.error(f"Remote control action '{action_name}' failed: {exc}")

    def _handle_log_message(self, level: LogLevel, message: str) -> None:
        event = {
            "level": level.value,
            "message": str(message or ""),
        }
        try:
            self._loop.call_soon_threadsafe(self._broadcast_log_event, event)
        except RuntimeError:
            pass

    def _broadcast_log_event(self, event: dict[str, Any]) -> None:
        log_event = self._make_log_event(
            str(event.get("level") or LogLevel.INFO.value),
            str(event.get("message") or ""),
        )
        self._log_history.append(dict(log_event))
        for queue in list(self._log_subscribers):
            try:
                queue.put_nowait(dict(log_event))
            except Exception:
                self._log_subscribers.discard(queue)

    def _make_log_event(self, level: str, message: str) -> dict[str, Any]:
        self._next_log_id += 1
        return {
            "id": self._next_log_id,
            "level": str(level or LogLevel.INFO.value),
            "message": str(message or ""),
        }

    def _build_logs_history_payload(self) -> dict[str, Any]:
        entries = list(self._log_history)
        return {
            "entries": entries,
            "latest_id": self._latest_log_id(entries),
        }

    def _log_history_after(self, after_id: int) -> list[dict[str, Any]]:
        return [
            dict(entry)
            for entry in self._log_history
            if self._log_entry_id(entry) > after_id
        ]

    @staticmethod
    def _latest_log_id(entries: list[dict[str, Any]]) -> int:
        latest_id = 0
        for entry in entries:
            latest_id = max(latest_id, RemoteControlWeb._log_entry_id(entry))
        return latest_id

    @staticmethod
    def _log_entry_id(entry: dict[str, Any]) -> int:
        try:
            return max(0, int(entry.get("id") or 0))
        except Exception:
            return 0

    @staticmethod
    def _read_after_log_id(raw_request: Request) -> int:
        try:
            return max(0, int(raw_request.query_params.get("after") or 0))
        except Exception:
            return 0

    async def _log_stream(
        self,
        queue: asyncio.Queue,
        history: list[dict[str, Any]],
        raw_request: Request,
        *,
        after_id: int = 0,
    ):
        latest_sent_id = max(0, int(after_id or 0))
        try:
            yield self._encode_sse_event(
                "connected",
                {"ok": True, "after": latest_sent_id},
            )
            for entry in history:
                entry_id = self._log_entry_id(entry)
                if entry_id <= latest_sent_id:
                    continue
                yield self._encode_sse_event("log", entry)
                latest_sent_id = entry_id

            while True:
                if await raw_request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                if event is None:
                    break
                event_id = self._log_entry_id(event)
                if event_id <= latest_sent_id:
                    continue
                yield self._encode_sse_event("log", event)
                latest_sent_id = event_id
        except asyncio.CancelledError:
            raise
        finally:
            self._log_subscribers.discard(queue)

    @staticmethod
    def _encode_sse_event(event_name: str, payload: dict[str, Any]) -> str:
        data = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        return f"event: {event_name}\ndata: {data}\n\n"
