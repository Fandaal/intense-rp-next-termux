from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

from patchright.async_api import async_playwright

from utils.logger import Logger


StatusCallback = Callable[[str], None]


@dataclass(frozen=True)
class PatchrightCommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def combined_output(self) -> str:
        parts: list[str] = []
        stdout = (self.stdout or "").strip()
        stderr = (self.stderr or "").strip()

        if stdout:
            parts.append(stdout)
        if stderr and stderr != stdout:
            parts.append(stderr)
        return "\n\n".join(parts).strip()

    @property
    def other_installations_detected(self) -> bool:
        return "used by other playwright installations" in self.combined_output.lower()

    @property
    def other_installations_browser_count(self) -> int | None:
        match = re.search(
            r"There are still (\d+) browsers left, used by other Playwright installations\.",
            self.combined_output,
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        try:
            return int(match.group(1))
        except Exception:
            return None


def _decode_process_output(stdout: bytes | None, stderr: bytes | None) -> str:
    stderr_text = stderr.decode(errors="replace").strip() if stderr else ""
    stdout_text = stdout.decode(errors="replace").strip() if stdout else ""
    return stderr_text or stdout_text or "Unknown error"


def _normalize_download_host(download_host: str | None) -> str:
    return str(download_host or "").strip().rstrip("/")


def _patchright_cli_env(download_host: str | None = None) -> dict[str, str] | None:
    normalized_host = _normalize_download_host(download_host)
    if not normalized_host:
        return None

    env = os.environ.copy()
    env["PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST"] = normalized_host
    return env


async def _run_patchright_cli(
    *args: str,
    timeout_s: float = 300.0,
    download_host: str | None = None,
) -> PatchrightCommandResult:
    env = _patchright_cli_env(download_host)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "patchright",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        try:
            process.kill()
        except Exception:
            pass
        try:
            await process.communicate()
        except Exception:
            pass
        raise RuntimeError(f"Browser command timed out after {int(timeout_s)} seconds.")

    result = PatchrightCommandResult(
        args=tuple(str(arg) for arg in args),
        returncode=int(process.returncode or 0),
        stdout=stdout.decode(errors="replace").strip() if stdout else "",
        stderr=stderr.decode(errors="replace").strip() if stderr else "",
    )

    if process.returncode == 0:
        return result

    raise RuntimeError(_decode_process_output(stdout, stderr))


async def probe_browser_executable_path() -> str | None:
    playwright = None
    browser_path = ""

    try:
        playwright = await async_playwright().start()
        browser_path = str(playwright.chromium.executable_path or "").strip()
    except Exception as e:
        Logger.debug(f"Browser executable probe failed: {e}")
        return None
    finally:
        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:
                pass

    if not browser_path:
        return None

    path_obj = Path(browser_path)
    return str(path_obj) if path_obj.exists() else None


async def is_browser_installed() -> bool:
    return bool(await probe_browser_executable_path())


async def install_chromium_browser(
    status_callback: StatusCallback | None = None,
    download_host: str | None = None,
) -> PatchrightCommandResult:
    Logger.info("Verifying/Installing Chromium browser...")
    if status_callback:
        status_callback("Verifying Browser...")

    normalized_host = _normalize_download_host(download_host)
    if normalized_host:
        Logger.info(f"Using configured Chromium download mirror: {normalized_host}")
        if status_callback:
            status_callback("Using Browser Download Mirror...")

    try:
        result = await _run_patchright_cli(
            "install",
            "chromium",
            download_host=normalized_host,
        )
    except Exception as e:
        Logger.error(f"Browser installation failed: {e}")
        if normalized_host:
            raise RuntimeError(
                "Browser installation failed while using the configured Chromium "
                f"download mirror ({normalized_host}): {e}"
            )
        raise RuntimeError(f"Browser installation failed: {e}")

    if result.stdout:
        Logger.info(f"Patchright install output:\n{result.stdout}")
    if result.stderr:
        Logger.warning(f"Patchright install stderr:\n{result.stderr}")
    Logger.success("Chromium browser verified/installed.")
    return result


async def uninstall_playwright_browsers(status_callback: StatusCallback | None = None) -> PatchrightCommandResult:
    Logger.info("Removing Playwright browser installation...")
    if status_callback:
        status_callback("Removing Browser...")

    try:
        result = await _run_patchright_cli("uninstall")
    except Exception as e:
        Logger.error(f"Browser removal failed: {e}")
        raise RuntimeError(f"Browser removal failed: {e}")

    if result.stdout:
        Logger.info(f"Patchright uninstall output:\n{result.stdout}")
    if result.stderr:
        Logger.warning(f"Patchright uninstall stderr:\n{result.stderr}")
    Logger.success("Playwright browser installation removed.")
    return result


async def uninstall_playwright_browsers_all(status_callback: StatusCallback | None = None) -> PatchrightCommandResult:
    Logger.info("Removing Playwright browser installation from all Playwright installs...")
    if status_callback:
        status_callback("Removing Browser From All Installs...")

    try:
        result = await _run_patchright_cli("uninstall", "--all")
    except Exception as e:
        Logger.error(f"Browser removal (--all) failed: {e}")
        raise RuntimeError(f"Browser removal (--all) failed: {e}")

    if result.stdout:
        Logger.info(f"Patchright uninstall --all output:\n{result.stdout}")
    if result.stderr:
        Logger.warning(f"Patchright uninstall --all stderr:\n{result.stderr}")
    Logger.success("Playwright browser installation removed from all Playwright installs.")
    return result
