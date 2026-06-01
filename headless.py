#!/usr/bin/env python3
"""IntenseRP Next v2 — CLI launcher (Xvfb, no visible windows)."""
import sys, os, asyncio, argparse, logging, subprocess, time

def ensure_xvfb():
    display = os.environ.get("DISPLAY", "")
    if display and os.path.exists(f"/tmp/.X11-unix/X{display[1:]}"):
        return display
    for num in range(99, 110):
        lock = f"/tmp/.X{num}-lock"
        if os.path.exists(lock):
            try: os.remove(lock)
            except: pass
        try:
            subprocess.run(["Xvfb", f":{num}", "-screen", "0", "1280x720x24", "-ac"],
                start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            os.environ["DISPLAY"] = f":{num}"
            return f":{num}"
        except FileNotFoundError:
            print("[ERROR] Xvfb not found. apt install xvfb")
            sys.exit(1)
    return None

display = ensure_xvfb()
print(f"[Xvfb] Display {display} ready")

_CHROME_DIR = os.path.expanduser("~/.cache/ms-playwright/chromium-1223/chrome-linux")
_CHROME_BIN = os.path.join(_CHROME_DIR, "chrome")
if os.path.isfile(_CHROME_BIN):
    os.environ.setdefault("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH", _CHROME_BIN)
    print(f"[Patch] Using full Chrome: {_CHROME_BIN}")

import patchright.async_api as _pw
_orig_launch = _pw.BrowserType.launch
_orig_launch_persistent = _pw.BrowserType.launch_persistent_context
_PROOT_ARGS = [
    "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
    "--disable-gpu", "--disable-software-rasterizer",
]
def _apply_patch(kwargs):
    kwargs["headless"] = False
    args = list(kwargs.get("args") or [])
    for a in _PROOT_ARGS:
        if a not in args: args.append(a)
    kwargs["args"] = args
async def _pl(self, **kw): _apply_patch(kw); return await _orig_launch(self, **kw)
async def _plp(self, ud, **kw): _apply_patch(kw); return await _orig_launch_persistent(self, ud, **kw)
_pw.BrowserType.launch = _pl
_pw.BrowserType.launch_persistent_context = _plp
print("[Patch] Monkey-patch applied")

from config.manager import ConfigManager
from drivers.factory import create_driver
from drivers.providers import provider_options, DriverProvider
from api import API
from remote_control import RemoteControlActions
from utils.logger import Logger, LogLevel
import uvicorn

PROVIDER_BEHAVIOR_KEYS = {
    DriverProvider.DEEPSEEK: "deepseek_behavior",
    DriverProvider.GLM_CHAT: "glm_behavior",
    DriverProvider.MOONSHOT: "moonshot_behavior",
    DriverProvider.QWEN_LM: "qwen_behavior",
    DriverProvider.PERPLEXITY: "perplexity_behavior",
    DriverProvider.HUGGINGCHAT: "huggingchat_behavior",
    DriverProvider.AI_STUDIO: "aistudio_behavior",
}

def parse_args():
    p = argparse.ArgumentParser(
        description="IntenseRP Next v2 — CLI launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python headless.py -p DeepSeek
  python headless.py -p QwenLM --port 8080 --lan
  python headless.py -p DeepSeek --deepthink --search
  python headless.py -p "Google AI Studio" --aistudio-model gemini-2.5-flash
  python headless.py -p "GLM Chat" --glm-model GLM-4-Flash
  python headless.py -p DeepSeek --auto-login --no-persistent-sessions
  python headless.py -p QwenLM --formatting-preset "Classic - Name"
""")
    # ── Connection ──
    p.add_argument("--provider", "-p", choices=provider_options(), default=None,
        help="Provider (overrides config)")
    p.add_argument("--port", type=int, default=None,
        help="API port (default: config or 7777)")
    p.add_argument("--host", default="127.0.0.1",
        help="Bind host (default: 127.0.0.1)")
    p.add_argument("--lan", action="store_true",
        help="Shortcut for --host 0.0.0.0")

    # ── Auth ──
    p.add_argument("--auto-login", action="store_true", default=None,
        help="Enable auto-login with saved accounts")
    p.add_argument("--no-auto-login", action="store_false", dest="auto_login",
        help="Disable auto-login")
    p.add_argument("--no-persistent-sessions", action="store_true", default=None,
        help="Disable persistent browser sessions")
    p.add_argument("--least-used", action="store_true", default=None,
        help="Prefer least used account")
    p.add_argument("--retry-on-failure", action="store_true", default=None,
        help="Retry with another account on failure")

    # ── DeepSeek ──
    ds = p.add_argument_group("DeepSeek")
    ds.add_argument("--deepthink", action="store_true", default=None,
        help="Enable DeepThink")
    ds.add_argument("--no-deepthink", action="store_false", dest="deepthink",
        help="Disable DeepThink")
    ds.add_argument("--send-deepthink", action="store_true", default=None,
        help="Include thinking in response")
    ds.add_argument("--search", action="store_true", default=None,
        help="Enable Search")
    ds.add_argument("--no-search", action="store_false", dest="search",
        help="Disable Search")

    # ── GLM Chat ──
    glm = p.add_argument_group("GLM Chat")
    glm.add_argument("--glm-model", default=None,
        help="GLM model (e.g. GLM-4-Flash, GLM-4-Plus, GLM-5V-Turbo)")
    glm.add_argument("--glm-deepthink", action="store_true", default=None,
        help="Enable GLM Deep Think")
    glm.add_argument("--glm-search", action="store_true", default=None,
        help="Enable GLM Search")

    # ── QwenLM ──
    qn = p.add_argument_group("QwenLM")
    qn.add_argument("--qwen-model", default=None,
        help="Qwen model name")
    qn.add_argument("--qwen-thinking", action="store_true", default=None,
        help="Enable Qwen Thinking")
    qn.add_argument("--qwen-web-search", action="store_true", default=None,
        help="Enable Qwen Web Search")

    # ── Moonshot ──
    ms = p.add_argument_group("Moonshot")
    ms.add_argument("--moonshot-thinking", action="store_true", default=None,
        help="Enable Moonshot Thinking")

    # ── Perplexity ──
    pp = p.add_argument_group("Perplexity")
    pp.add_argument("--perplexity-model", default=None,
        help="Perplexity model")
    pp.add_argument("--perplexity-reasoning", action="store_true", default=None,
        help="Enable Perplexity Reasoning")

    # ── HuggingChat ──
    hc = p.add_argument_group("HuggingChat")
    hc.add_argument("--huggingchat-model", default=None,
        help="HuggingChat model")

    # ── AI Studio ──
    ai = p.add_argument_group("Google AI Studio")
    ai.add_argument("--aistudio-model", default=None,
        help="AI Studio model (e.g. gemini-2.5-flash, gemini-2.5-pro)")
    ai.add_argument("--aistudio-thinking", action="store_true", default=None,
        help="Enable AI Studio Thinking")
    ai.add_argument("--aistudio-thinking-level", default=None,
        choices=["minimal","low","medium","high"],
        help="AI Studio Thinking Level")
    ai.add_argument("--aistudio-temperature", default=None, type=float,
        help="Temperature (0.0-2.0)")
    ai.add_argument("--aistudio-max-tokens", default=None, type=int,
        help="Max output tokens")

    # ── Formatting ──
    fmt = p.add_argument_group("Formatting")
    fmt.add_argument("--formatting-preset", default=None,
        help="Message style preset")
    fmt.add_argument("--formatting-template", default=None,
        help="Custom formatting template")
    fmt.add_argument("--formatting-divider", default=None,
        help="Divider between messages")
    fmt.add_argument("--no-formatting", action="store_true", default=None,
        help="Disable message formatting")

    # ── Config persistence ──
    p.add_argument("--no-save", action="store_true",
        help="Do not save CLI overrides to disk (runtime-only)")

    # ── Logging ──
    p.add_argument("--log-level", default="info",
        choices=["debug","success","info","warning","error"])
    return p.parse_args()

LM = {"debug":LogLevel.DEBUG,"success":LogLevel.SUCCESS,"info":LogLevel.INFO,
      "warning":LogLevel.WARNING,"error":LogLevel.ERROR}

def apply_cli_overrides(config, args):
    """Apply CLI arguments to config (only non-None values override)."""
    changed = []

    # Provider
    if args.provider:
        config.set_setting("providers_credentials", "provider", args.provider)
        changed.append(f"provider={args.provider}")

    # Auth
    if args.auto_login is not None:
        config.set_setting("providers_credentials", "auto_login", args.auto_login)
        changed.append(f"auto_login={args.auto_login}")
    if args.no_persistent_sessions:
        config.set_setting("system_settings", "persistent_sessions", False)
        changed.append("persistent_sessions=False")
    if args.least_used is not None:
        config.set_setting("providers_credentials", "select_least_used", args.least_used)
        changed.append(f"select_least_used={args.least_used}")
    if args.retry_on_failure is not None:
        config.set_setting("providers_credentials", "reload_on_failure", args.retry_on_failure)
        changed.append(f"reload_on_failure={args.retry_on_failure}")

    # DeepSeek
    if args.deepthink is not None:
        config.set_setting("deepseek_behavior", "enable_deepthink", args.deepthink)
        changed.append(f"deepthink={args.deepthink}")
    if args.send_deepthink is not None:
        config.set_setting("deepseek_behavior", "send_deepthink", args.send_deepthink)
        changed.append(f"send_deepthink={args.send_deepthink}")
    if args.search is not None:
        config.set_setting("deepseek_behavior", "enable_search", args.search)
        changed.append(f"search={args.search}")

    # GLM
    if args.glm_model:
        config.set_setting("glm_behavior", "model", args.glm_model)
        changed.append(f"glm_model={args.glm_model}")
    if args.glm_deepthink is not None:
        config.set_setting("glm_behavior", "enable_deepthink", args.glm_deepthink)
        changed.append(f"glm_deepthink={args.glm_deepthink}")
    if args.glm_search is not None:
        config.set_setting("glm_behavior", "enable_search", args.glm_search)
        changed.append(f"glm_search={args.glm_search}")

    # Qwen
    if args.qwen_model:
        config.set_setting("qwen_behavior", "model", args.qwen_model)
        changed.append(f"qwen_model={args.qwen_model}")
    if args.qwen_thinking is not None:
        config.set_setting("qwen_behavior", "enable_thinking", args.qwen_thinking)
        changed.append(f"qwen_thinking={args.qwen_thinking}")
    if args.qwen_web_search is not None:
        config.set_setting("qwen_behavior", "enable_web_search", args.qwen_web_search)
        changed.append(f"qwen_web_search={args.qwen_web_search}")

    # Moonshot
    if args.moonshot_thinking is not None:
        config.set_setting("moonshot_behavior", "enable_thinking", args.moonshot_thinking)
        changed.append(f"moonshot_thinking={args.moonshot_thinking}")

    # Perplexity
    if args.perplexity_model:
        config.set_setting("perplexity_behavior", "model", args.perplexity_model)
        changed.append(f"perplexity_model={args.perplexity_model}")
    if args.perplexity_reasoning is not None:
        config.set_setting("perplexity_behavior", "enable_reasoning", args.perplexity_reasoning)
        changed.append(f"perplexity_reasoning={args.perplexity_reasoning}")

    # HuggingChat
    if args.huggingchat_model:
        config.set_setting("huggingchat_behavior", "model", args.huggingchat_model)
        changed.append(f"huggingchat_model={args.huggingchat_model}")

    # AI Studio
    if args.aistudio_model:
        config.set_setting("aistudio_behavior", "model", args.aistudio_model)
        changed.append(f"aistudio_model={args.aistudio_model}")
    if args.aistudio_thinking is not None:
        config.set_setting("aistudio_behavior", "enable_thinking", args.aistudio_thinking)
        changed.append(f"aistudio_thinking={args.aistudio_thinking}")
    if args.aistudio_thinking_level:
        config.set_setting("aistudio_behavior", "thinking_level", args.aistudio_thinking_level)
        changed.append(f"aistudio_thinking_level={args.aistudio_thinking_level}")
    if args.aistudio_temperature is not None:
        config.set_setting("aistudio_behavior", "temperature", str(args.aistudio_temperature))
        changed.append(f"aistudio_temperature={args.aistudio_temperature}")
    if args.aistudio_max_tokens is not None:
        config.set_setting("aistudio_behavior", "max_output_tokens", args.aistudio_max_tokens)
        changed.append(f"aistudio_max_tokens={args.aistudio_max_tokens}")

    # Formatting
    if args.formatting_preset:
        config.set_setting("formatting", "formatting_preset", args.formatting_preset)
        changed.append(f"formatting_preset={args.formatting_preset}")
    if args.formatting_template:
        config.set_setting("formatting", "formatting_template", args.formatting_template)
        config.set_setting("formatting", "formatting_preset", "Custom")
        changed.append(f"formatting_template={args.formatting_template}")
    if args.formatting_divider:
        config.set_setting("formatting", "formatting_divider", args.formatting_divider)
        changed.append(f"formatting_divider={args.formatting_divider}")
    if args.no_formatting is not None:
        config.set_setting("formatting", "apply_formatting", not args.no_formatting)
        changed.append(f"apply_formatting={not args.no_formatting}")

    if changed:
        if not getattr(args, 'no_save', False):
            config.save_settings()
            Logger.info("Config saved to disk")
        else:
            Logger.info("Config NOT saved (--no-save), overrides are runtime-only")
        for c in changed:
            Logger.info(f"CLI override: {c}")
    else:
        Logger.info("No CLI overrides, using saved config")

async def run(args):
    config = ConfigManager()
    apply_cli_overrides(config, args)

    port = args.port
    if port is None:
        try: port = int(config.get_setting("network_settings", "port") or 7777)
        except: port = 7777
    host = "0.0.0.0" if args.lan else args.host

    for name in ("uvicorn","uvicorn.error","uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = [logging.NullHandler()]
        lg.setLevel(logging.CRITICAL)
        lg.propagate = False
        lg.disabled = True

    Logger.info("Creating driver...")
    driver = create_driver(config)
    driver.notify_user_callback = lambda t,m,l: Logger.warning(f"[{l.upper()}] {t}: {m}")
    async def _ni(*a,**kw):
        Logger.warning("Interactive input unavailable in CLI")
        return None
    driver.request_user_text_callback = _ni

    Logger.info(f"Launching {driver.provider_label}...")
    try:
        await driver.start(status_callback=lambda m: Logger.info(f"[Browser] {m}"))
    except Exception as e:
        Logger.error(f"Launch failed: {e}")
        await driver.close()
        return

    try:
        await driver.check_ui_language()
    except: pass

    if not driver.is_running:
        Logger.error("Driver not running")
        await driver.close()
        return

    api = API(driver, remote_actions=RemoteControlActions(
        stop=lambda: None, restart=lambda: None,
        switch_account=lambda: None, hotswap=lambda p: None,
        switch_loadout=lambda s: None, switch_model=lambda s: None,
        get_state=lambda: {"running": True},
    ))
    Logger.success(f"API at http://{host}:{port}/v1")
    Logger.info("Ctrl+C to stop")
    cfg = uvicorn.Config(app=api.app, host=host, port=port,
        log_level="critical", log_config=None, access_log=False)
    await uvicorn.Server(cfg).serve()

def main():
    args = parse_args()
    Logger.set_stdout_enabled(True)
    Logger.set_stdout_level(LM.get(args.log_level, LogLevel.INFO))
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        Logger.info("Stopped")
    except Exception as e:
        Logger.error(f"Fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
