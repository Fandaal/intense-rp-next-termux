from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class UpdateFailed(RuntimeError):
    pass


DEFAULT_PAYLOAD_DIRNAME = "intense-rp-next"
DEFAULT_OPTIONAL_DIRNAME = "optional"
DEFAULT_LOCK_WAIT_S = 300.0
POSTUPDATE_FLAG_FILENAME = "postupdate_notes_url.txt"
POSTUPDATE_CLEANUP_FILENAME = "postupdate_cleanup.json"
PRESERVED_DIR_NAMES = ("config_data", "logs")
PRESERVED_ROOT_FILENAMES = ("loadouts.json",)
PRESERVED_ROOT_GLOB_PATTERNS = ("*_dir.txt",)
CHROMIUM_SINGLETON_LOCK_FILENAMES = (
    "SingletonLock",
    "SingletonCookie",
    "SingletonSocket",
)


@dataclass(frozen=True)
class UpdateArgs:
    install_dir: Path
    app_pid: int
    exe_name: Optional[str]
    payload_dir: Optional[Path]
    release_url: str = ""
    legacy_restore_config_logs: bool = False


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _resolve_updater_exe_path() -> Path:
    if _is_frozen():
        return Path(sys.executable).resolve()
    return Path(__file__).resolve()


def _default_payload_dir(updater_path: Path) -> Path:
    updater_dir = updater_path.parent
    if updater_dir.name.lower() == DEFAULT_OPTIONAL_DIRNAME.lower():
        return updater_dir.parent / DEFAULT_PAYLOAD_DIRNAME
    return updater_dir / DEFAULT_PAYLOAD_DIRNAME


def _wait_for_pid(pid: int, *, timeout_s: float = 120.0) -> None:
    if pid <= 0:
        return

    if not sys.platform.startswith("win"):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                return
            time.sleep(0.25)
        raise UpdateFailed("Timed out waiting for the app to exit.")

    try:
        import ctypes

        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
        if not handle:
            raise OSError("OpenProcess failed")
        try:
            WAIT_OBJECT_0 = 0
            timeout_ms = int(timeout_s * 1000)
            result = ctypes.windll.kernel32.WaitForSingleObject(handle, timeout_ms)
            if result != WAIT_OBJECT_0:
                raise UpdateFailed("Timed out waiting for the app to exit.")
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except UpdateFailed:
        raise
    except Exception:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                return
            time.sleep(0.25)
        raise UpdateFailed("Timed out waiting for the app to exit.")


def _is_windows_lock_error(exc: BaseException) -> bool:
    if not isinstance(exc, OSError):
        return False
    winerror = getattr(exc, "winerror", None)
    # 32 = ERROR_SHARING_VIOLATION, 5 = ERROR_ACCESS_DENIED (sometimes from locks).
    return winerror in (32, 5)


def _retry(
    action,
    *,
    retries: int = 240,
    delay_s: float = 0.25,
    on_retry=None,
) -> None:
    last_exc: Optional[BaseException] = None
    for attempt in range(retries):
        try:
            action()
            return
        except Exception as exc:
            last_exc = exc
            if on_retry is not None:
                try:
                    on_retry(exc, attempt + 1, retries)
                except Exception:
                    pass
            if attempt >= retries - 1:
                raise
            time.sleep(delay_s)
    if last_exc is not None:
        raise last_exc


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path_s = os.path.normcase(str(path.resolve()))
        parent_s = os.path.normcase(str(parent.resolve()))
        return os.path.commonpath([path_s, parent_s]) == parent_s
    except Exception:
        return False


def _normalized_resolved_path(path: Path) -> str:
    try:
        return os.path.normcase(str(path.resolve()))
    except Exception:
        try:
            return os.path.normcase(str(path.absolute()))
        except Exception:
            return os.path.normcase(str(path))


def _read_config_dir_pointer(pointer_path: Path, install_dir: Path) -> Path | None:
    try:
        text = pointer_path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return None
    if not text:
        return None

    try:
        path = Path(text).expanduser()
        if not path.is_absolute():
            path = install_dir / path
        return path.resolve()
    except Exception:
        try:
            return path.absolute()
        except Exception:
            return None


def _discover_config_dirs_for_update(install_dir: Path) -> list[Path]:
    candidates: list[Path] = [install_dir / "config_data"]

    try:
        pointer_paths = [p for p in install_dir.glob("*_dir.txt") if p.is_file()]
    except Exception:
        pointer_paths = []

    for pointer_path in pointer_paths:
        target = _read_config_dir_pointer(pointer_path, install_dir)
        if target is not None:
            candidates.append(target)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = _normalized_resolved_path(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _running_chromium_user_data_dirs() -> set[str]:
    try:
        import psutil  # type: ignore
    except Exception:
        return set()

    running_dirs: set[str] = set()
    for proc in psutil.process_iter(["cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
        except Exception:
            continue
        if not cmdline:
            continue

        for index, arg in enumerate(cmdline):
            arg_text = str(arg or "")
            user_data_dir = ""
            if arg_text.startswith("--user-data-dir="):
                user_data_dir = arg_text.split("=", 1)[1]
            elif arg_text == "--user-data-dir" and index + 1 < len(cmdline):
                user_data_dir = str(cmdline[index + 1] or "")

            user_data_dir = user_data_dir.strip().strip('"')
            if not user_data_dir:
                continue
            try:
                running_dirs.add(_normalized_resolved_path(Path(user_data_dir).expanduser()))
            except Exception:
                continue
    return running_dirs


def _cleanup_playwright_singleton_locks(install_dir: Path) -> int:
    """
    Remove stale Chromium ProcessSingleton files from IntenseRP-managed profiles.

    These files are lock/IPC markers, not cookies or provider session data. The
    cleanup is deliberately scoped to config/playwright_profiles and exact file
    names only, so update installation cannot wander into unrelated browser data.
    """
    removed = 0
    running_user_data_dirs = _running_chromium_user_data_dirs()

    for config_dir in _discover_config_dirs_for_update(install_dir):
        profiles_root = config_dir / "playwright_profiles"
        try:
            profiles_root_resolved = profiles_root.resolve()
        except Exception:
            profiles_root_resolved = profiles_root.absolute()
        if not profiles_root_resolved.exists() or not profiles_root_resolved.is_dir():
            continue

        try:
            walker = os.walk(profiles_root_resolved, topdown=True, followlinks=False)
            for current_dir, dirnames, filenames in walker:
                names = set(dirnames) | set(filenames)
                for name in CHROMIUM_SINGLETON_LOCK_FILENAMES:
                    if name not in names:
                        continue
                    lock_path = Path(current_dir) / name
                    try:
                        if not _path_is_relative_to(lock_path.parent, profiles_root_resolved):
                            continue
                        if lock_path.is_dir() and not lock_path.is_symlink():
                            continue
                        profile_key = _normalized_resolved_path(lock_path.parent)
                        if profile_key in running_user_data_dirs:
                            continue
                        lock_path.unlink(missing_ok=True)
                        removed += 1
                    except Exception:
                        continue
        except Exception:
            continue

    return removed


def _stop_processes_under_dir(install_dir: Path) -> None:
    try:
        import psutil  # type: ignore
    except Exception:
        return

    install_root = install_dir.resolve()
    me = os.getpid()

    procs = []
    for p in psutil.process_iter(["pid", "exe", "name"]):
        try:
            pid = int(p.info.get("pid") or 0)
            if pid <= 0 or pid == me:
                continue
            exe = p.info.get("exe") or ""
            if not exe:
                continue
            if _path_is_relative_to(Path(str(exe)), install_root):
                procs.append(p)
        except Exception:
            continue

    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass

    _, alive = psutil.wait_procs(procs, timeout=3.0)
    for p in alive:
        try:
            p.kill()
        except Exception:
            pass


def _merge_copy_dir(src: Path, dst: Path) -> None:
    if not src.exists() or not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        dest = dst / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)


def _merge_copy_root_files(src_dir: Path, dst_dir: Path, filenames: tuple[str, ...]) -> None:
    if not src_dir.exists() or not src_dir.is_dir():
        return

    for filename in filenames:
        source = src_dir / filename
        if not source.exists() or source.is_dir():
            continue
        destination = dst_dir / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _select_main_executable(install_dir: Path, preferred_name: Optional[str]) -> Path:
    """Find the main app executable in install_dir."""
    if not preferred_name:
        raise UpdateFailed("No executable name provided")
    
    candidate = install_dir / preferred_name
    if candidate.exists():
        return candidate
    
    raise UpdateFailed(f"Could not locate executable '{preferred_name}' in {install_dir}")


# Keep old name as alias
def _select_main_exe(install_dir: Path, preferred_name: Optional[str]) -> Path:
    return _select_main_executable(install_dir, preferred_name)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _compute_backup_dir(install_dir: Path) -> Path:
    base = install_dir.with_name(f"{install_dir.name}-backup")
    if not base.exists():
        return base
    return install_dir.with_name(f"{install_dir.name}-backup-{_timestamp()}")


def _compute_preserve_dir(install_dir: Path) -> Path:
    return install_dir.with_name(f"{install_dir.name}-preserve-{_timestamp()}")


def _unique_relpaths(relpaths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for relpath in relpaths:
        key = relpath.as_posix().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(relpath)
    return unique


def _iter_preserved_relpaths(root: Path) -> list[Path]:
    relpaths: list[Path] = []

    for dirname in PRESERVED_DIR_NAMES:
        path = root / dirname
        if path.exists():
            relpaths.append(Path(dirname))

    for filename in PRESERVED_ROOT_FILENAMES:
        path = root / filename
        if path.exists():
            relpaths.append(Path(filename))

    for pattern in PRESERVED_ROOT_GLOB_PATTERNS:
        try:
            matches = list(root.glob(pattern))
        except Exception:
            matches = []
        for match in matches:
            if match.exists():
                relpaths.append(Path(match.name))

    return _unique_relpaths(relpaths)


def _remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _scrub_payload_preserved_items(payload_dir: Path, *, log_cb=None) -> None:
    """
    Release packages should not ship config/log data, but remove it from the
    staged payload just in case so local data never gets replaced by accident.
    """
    for relpath in _iter_preserved_relpaths(payload_dir):
        target = payload_dir / relpath
        try:
            _remove_path(target)
            if log_cb is not None:
                log_cb(f"Removed preserved path from payload: {relpath.as_posix()}")
        except Exception as exc:
            raise UpdateFailed(f"Could not remove preserved payload path '{relpath}': {exc}") from exc


def _detach_preserved_items(install_dir: Path, preserve_dir: Path, *, log_cb=None) -> list[Path]:
    detached: list[Path] = []
    try:
        for relpath in _iter_preserved_relpaths(install_dir):
            source = install_dir / relpath
            destination = preserve_dir / relpath
            destination.parent.mkdir(parents=True, exist_ok=True)

            def do_move() -> None:
                shutil.move(str(source), str(destination))

            _retry(do_move, retries=60, delay_s=0.5)
            detached.append(relpath)
            if log_cb is not None:
                log_cb(f"Preserved local path: {relpath.as_posix()}")
    except Exception:
        try:
            _restore_detached_items(preserve_dir, install_dir, detached, log_cb=log_cb)
        except Exception as restore_exc:
            if log_cb is not None:
                log_cb(f"Failed to restore local data after preserve failure: {restore_exc}")
        raise
    return detached


def _restore_detached_items(preserve_dir: Path, install_dir: Path, relpaths: list[Path], *, log_cb=None) -> None:
    restored: list[Path] = []
    try:
        for relpath in relpaths:
            source = preserve_dir / relpath
            if not source.exists() and not source.is_symlink():
                continue

            destination = install_dir / relpath
            if destination.exists() or destination.is_symlink():
                raise UpdateFailed(f"Refusing to replace preserved local path: {destination}")

            destination.parent.mkdir(parents=True, exist_ok=True)

            def do_move() -> None:
                shutil.move(str(source), str(destination))

            _retry(do_move, retries=60, delay_s=0.5)
            restored.append(relpath)
            if log_cb is not None:
                log_cb(f"Restored local path: {relpath.as_posix()}")
    except Exception:
        for relpath in reversed(restored):
            source = install_dir / relpath
            destination = preserve_dir / relpath
            if not source.exists() and not source.is_symlink():
                continue
            if destination.exists() or destination.is_symlink():
                continue
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
            except Exception as restore_exc:
                if log_cb is not None:
                    log_cb(f"Failed to re-preserve local path '{relpath}': {restore_exc}")
        raise

    try:
        preserve_dir.rmdir()
    except Exception:
        pass


def _rollback_update(
    *,
    install_dir: Path,
    backup_dir: Path,
    preserve_dir: Path,
    detached_relpaths: list[Path],
    log_cb=None,
) -> None:
    try:
        if install_dir.exists() and backup_dir.exists():
            _remove_path(install_dir)
        if backup_dir.exists() and not install_dir.exists():
            backup_dir.rename(install_dir)
        if detached_relpaths and install_dir.exists():
            _restore_detached_items(preserve_dir, install_dir, detached_relpaths, log_cb=log_cb)
    except Exception as exc:
        if log_cb is not None:
            log_cb(f"Rollback failed: {exc}")


def _write_postupdate_cleanup_manifest(install_dir: Path, backup_dir: Path, *, log_cb=None) -> None:
    payload = {
        "version": 1,
        "backup_dir": str(backup_dir),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        (install_dir / POSTUPDATE_CLEANUP_FILENAME).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        if log_cb is not None:
            log_cb(f"Wrote post-update cleanup manifest for backup: {backup_dir}")
    except Exception as exc:
        if log_cb is not None:
            log_cb(f"Failed to write post-update cleanup manifest: {exc}")


def _make_update_log_path() -> Path:
    return Path(tempfile.gettempdir()) / f"intenserp-updater-{_timestamp()}.log"


def _append_update_log(log_path: Path, message: str) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
    except Exception:
        pass


def _latest_backup_dir(install_dir: Path) -> Path | None:
    try:
        parent = install_dir.resolve().parent
    except Exception:
        parent = install_dir.parent

    try:
        candidates = [
            path
            for path in parent.glob(f"{install_dir.name}-backup*")
            if path.exists() and path.is_dir()
        ]
    except Exception:
        candidates = []

    if not candidates:
        return None

    def mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except Exception:
            return 0.0

    candidates.sort(key=mtime, reverse=True)
    return candidates[0]


def _perform_update(args: UpdateArgs, *, status_cb, progress_cb, log_cb=None) -> None:
    install_dir = args.install_dir.resolve()
    updater_path = _resolve_updater_exe_path()
    payload_dir = (args.payload_dir or _default_payload_dir(updater_path)).resolve()
    preserve_dir = _compute_preserve_dir(install_dir)
    detached_relpaths: list[Path] = []
    rollback_allowed = True

    def status(text: str) -> None:
        if log_cb is not None:
            log_cb(text)
        status_cb(text)

    try:
        os.chdir(tempfile.gettempdir())
    except Exception:
        pass

    status("Waiting for the app to close…")
    progress_cb(5)
    _wait_for_pid(args.app_pid, timeout_s=240.0)
    try:
        _stop_processes_under_dir(install_dir)
    except Exception:
        pass
    try:
        removed_locks = _cleanup_playwright_singleton_locks(install_dir)
        if removed_locks:
            status(f"Removed {removed_locks} stale browser profile lock file(s)…")
    except Exception:
        pass

    if not install_dir.exists() or not install_dir.is_dir():
        raise UpdateFailed(f"Install directory not found: {install_dir}")

    if not payload_dir.exists() or not payload_dir.is_dir():
        raise UpdateFailed(f"Update payload directory not found: {payload_dir}")

    if args.legacy_restore_config_logs:
        status("Using legacy config/log restore mode…")
    else:
        status("Preserving local data…")
        progress_cb(10)
        _scrub_payload_preserved_items(payload_dir, log_cb=log_cb)
        detached_relpaths = _detach_preserved_items(install_dir, preserve_dir, log_cb=log_cb)

    status("Preparing backup…")
    progress_cb(15)
    backup_dir = _compute_backup_dir(install_dir)

    def do_backup() -> None:
        install_dir.rename(backup_dir)

    last_hint_at = 0.0

    def on_backup_retry(exc: BaseException, attempt: int, total: int) -> None:
        nonlocal last_hint_at
        if not _is_windows_lock_error(exc):
            return
        now = time.monotonic()
        if now - last_hint_at < 2.0:
            return
        last_hint_at = now
        status(
            "Waiting for Windows to release files…\n"
            "Close File Explorer windows opened to the app folder and try again."
        )

    lock_wait_s = DEFAULT_LOCK_WAIT_S if sys.platform.startswith("win") else 60.0
    try:
        _retry(
            do_backup,
            retries=max(1, int(lock_wait_s / 0.25)),
            delay_s=0.25,
            on_retry=on_backup_retry,
        )
    except Exception:
        if detached_relpaths:
            _restore_detached_items(preserve_dir, install_dir, detached_relpaths, log_cb=log_cb)
        raise

    try:
        status("Installing new version…")
        progress_cb(35)

        def do_install() -> None:
            shutil.move(str(payload_dir), str(install_dir))

        _retry(do_install, retries=40, delay_s=0.5)

        exe_path = _select_main_exe(install_dir, args.exe_name)

        progress_cb(60)
        if args.legacy_restore_config_logs:
            status("Restoring configs and logs…")
            _merge_copy_dir(backup_dir / "config_data", install_dir / "config_data")
            _merge_copy_dir(backup_dir / "logs", install_dir / "logs")
            _merge_copy_root_files(backup_dir, install_dir, PRESERVED_ROOT_FILENAMES)

            for txt_path in backup_dir.glob("*_dir.txt"):
                if txt_path.is_file():
                    shutil.copy2(txt_path, install_dir / txt_path.name)
        else:
            status("Restoring local data…")
            _restore_detached_items(preserve_dir, install_dir, detached_relpaths, log_cb=log_cb)

        # DON'T ROLL BACK RIGHT AWAY
        # users will do it manually if they want to revetr
        rollback_allowed = False

        status("Leaving old version available until relaunch…")
        progress_cb(75)
        _write_postupdate_cleanup_manifest(install_dir, backup_dir, log_cb=log_cb)

        status("Launching updated app…")
        progress_cb(90)

        try:
            (install_dir / POSTUPDATE_FLAG_FILENAME).write_text("true", encoding="utf-8")
        except Exception:
            pass

        cmd = [str(exe_path)]
        if _is_frozen():
            # Pass the temp extraction root directory for cleanup (not just the updater.exe path)
            # Structure: .../intenserp-update-extract-xyz/optional/updater.exe
            temp_cleanup_dir = updater_path.parent.parent
            cmd += ["--deleteupdater", "--updaterpath", str(temp_cleanup_dir)]

        subprocess.Popen(
            cmd,
            cwd=str(install_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

        status("Done.")
        progress_cb(100)
    except Exception:
        if rollback_allowed:
            _rollback_update(
                install_dir=install_dir,
                backup_dir=backup_dir,
                preserve_dir=preserve_dir,
                detached_relpaths=detached_relpaths,
                log_cb=log_cb,
            )
        raise


class _Worker(QObject):
    status = Signal(str)
    progress = Signal(int)
    finished = Signal()
    failed = Signal(str, str)

    def __init__(self, args: UpdateArgs):
        super().__init__()
        self._args = args
        self._log_path = _make_update_log_path()

    def run(self) -> None:
        def log(message: str) -> None:
            _append_update_log(self._log_path, message)

        log("Updater started.")
        log(f"Install dir: {self._args.install_dir}")
        log(f"Payload dir: {self._args.payload_dir}")
        log(f"Legacy config/log restore: {self._args.legacy_restore_config_logs}")
        try:
            _perform_update(
                self._args,
                status_cb=lambda s: self.status.emit(s),
                progress_cb=lambda p: self.progress.emit(int(p)),
                log_cb=log,
            )
            log("Updater finished successfully.")
            self.finished.emit()
        except Exception as exc:
            log("Updater failed.")
            log(traceback.format_exc())
            self.failed.emit(str(exc), str(self._log_path))


class UpdateWindow(QWidget):
    def __init__(self, args: UpdateArgs):
        super().__init__()
        self._args = args
        self._failure_text = ""
        self._failure_log_path = ""

        self.setWindowTitle("Updating…")
        self.setFixedWidth(520)
        self.setMinimumHeight(140)

        icon = _find_default_icon()
        if icon is not None:
            self.setWindowIcon(icon)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        self._label = QLabel("Starting…")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        layout.addWidget(self._bar)

        self._failure_buttons = self._build_failure_buttons()
        self._failure_buttons.hide()
        layout.addWidget(self._failure_buttons)

        self._thread = QThread(self)
        self._worker = _Worker(args)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status.connect(self._label.setText)
        self._worker.progress.connect(self._bar.setValue)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _on_finished(self) -> None:
        self._label.setText("Update complete. Launching…")
        self._bar.setValue(100)
        self._thread.quit()
        self._thread.wait(1000)
        QApplication.instance().quit()

    def _on_failed(self, message: str, log_path: str = "") -> None:
        hint = ""
        lowered = (message or "").lower()
        # Windows-specific file locking hints
        if sys.platform.startswith("win"):
            if "winerror 32" in lowered or "being used" in lowered or "access" in lowered:
                hint = (
                    "\n\nTip: close any File Explorer windows opened to the app folder "
                    "(and disable Preview pane), then try again."
                )
        log_hint = f"\n\nLog: {log_path}" if log_path else ""
        self._failure_log_path = log_path
        self._failure_text = f"Update failed:\n{message}{hint}{log_hint}"
        self._label.setText(self._failure_text)
        self._failure_buttons.show()
        self._thread.quit()
        self._thread.wait(1000)

    def _build_failure_buttons(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("background-color: transparent;")

        outer = QVBoxLayout(frame)
        outer.setContentsMargins(0, 4, 0, 0)
        outer.setSpacing(8)

        first_row = QHBoxLayout()
        first_row.setContentsMargins(0, 0, 0, 0)
        first_row.setSpacing(8)
        first_row.addWidget(self._make_failure_button("Copy Error", self._copy_failure_text))
        first_row.addWidget(self._make_failure_button("Open Install Folder", self._open_install_folder))
        first_row.addWidget(self._make_failure_button("Open Backup", self._open_backup_folder))
        outer.addLayout(first_row)

        second_row = QHBoxLayout()
        second_row.setContentsMargins(0, 0, 0, 0)
        second_row.setSpacing(8)
        if (self._args.release_url or "").strip():
            second_row.addWidget(self._make_failure_button("Release Page", self._open_release_page))
        second_row.addWidget(self._make_failure_button("Close", self._close_after_failure))
        outer.addLayout(second_row)
        return frame

    def _make_failure_button(self, text: str, callback: Callable[[], None]) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda _checked=False: callback())
        return button

    def _copy_failure_text(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._failure_text)

    def _open_install_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._args.install_dir)))

    def _open_backup_folder(self) -> None:
        backup_dir = _latest_backup_dir(self._args.install_dir)
        if backup_dir is None:
            self._label.setText(f"{self._failure_text}\n\nNo backup folder was found next to the app.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(backup_dir)))

    def _open_release_page(self) -> None:
        url = (self._args.release_url or "").strip()
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _close_after_failure(self) -> None:
        QApplication.instance().quit()


def _find_default_icon() -> Optional[QIcon]:
    candidates: list[Path] = []
    try:
        base = Path(__file__).resolve().parent.parent
        candidates.append(base / "ui" / "assets" / "brand" / "newlogo.ico")
    except Exception:
        pass

    for p in candidates:
        if p.exists():
            icon = QIcon(str(p))
            if not icon.isNull():
                return icon
    return None


def _parse_args(argv: list[str]) -> UpdateArgs:
    parser = argparse.ArgumentParser(prog="updater", add_help=True)
    parser.add_argument("--install-dir", required=True)
    parser.add_argument("--app-pid", type=int, default=0)
    parser.add_argument("--exe-name", default=None)
    parser.add_argument("--payload-dir", default=None)
    parser.add_argument("--release-url", default="")
    parser.add_argument("--legacy-restore-config-logs", action="store_true")
    ns = parser.parse_args(argv)

    install_dir = Path(ns.install_dir).expanduser()
    exe_name = (ns.exe_name or "").strip() or None
    payload_dir = Path(ns.payload_dir).expanduser() if ns.payload_dir else None
    return UpdateArgs(
        install_dir=install_dir,
        app_pid=int(ns.app_pid or 0),
        exe_name=exe_name,
        payload_dir=payload_dir,
        release_url=str(ns.release_url or "").strip(),
        legacy_restore_config_logs=bool(ns.legacy_restore_config_logs),
    )


def main() -> int:
    if not sys.platform.startswith(("win", "linux")):
        print(f"This updater supports Windows and Linux only (got {sys.platform}).", file=sys.stderr)
        return 2

    args = _parse_args(sys.argv[1:])
    app = QApplication(sys.argv[:1])
    window = UpdateWindow(args)
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
