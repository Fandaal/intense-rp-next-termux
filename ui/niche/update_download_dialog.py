from __future__ import annotations

import asyncio
import inspect
import subprocess
import sys
import tempfile
import os
import shutil
from pathlib import Path
from typing import Optional, List

from PySide6.QtCore import Qt, QSize, QThread, Signal, QObject, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QMessageBox,
    QApplication,
)

from ui.core.brand import BrandColors
from ui.core.icons import IconType, IconUtils
from ui.widgets.rounded_progress_bar import RoundedProgressBar
from utils.auto_update import (
    AutoUpdateError,
    PreparedUpdate,
    prepare_update_from_github,
    prepare_update_from_local_archive,
    DownloadProgress,
)


class MissingUpdaterError(RuntimeError):
    pass


class _UpdaterLauncher(QObject):
    """Launches the updater executable off the main thread so the UI stays responsive."""

    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, cmd: List[str], cwd: str, parent=None):
        super().__init__(parent)
        self._cmd = cmd
        self._cwd = cwd

    def run(self) -> None:
        try:
            kwargs: dict = {
                "cwd": self._cwd,
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if sys.platform.startswith("win"):
                kwargs["creationflags"] = (
                    subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                kwargs["start_new_session"] = True
            process = subprocess.Popen(self._cmd, **kwargs)
            try:
                return_code = process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                return_code = None

            if return_code is not None:
                self.failed.emit(
                    "The updater exited immediately "
                    f"(code {return_code}). The staged updater may be from an older build."
                )
                return

            self.succeeded.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


def _find_staged_updater(prepared: PreparedUpdate) -> Path:
    """Find the updater binary in the staged update package."""
    package_root = prepared.extracted_app_root.resolve().parent
    if sys.platform.startswith("win"):
        updater_name = "updater.exe"
    else:
        updater_name = "updater"
    updater_path = package_root / "optional" / updater_name
    if updater_path.exists():
        return updater_path
    raise MissingUpdaterError(f"Update package does not contain {updater_path}")


def _cleanup_prepared_update(prepared: PreparedUpdate) -> None:
    """Remove a staged update that will not be handed to the standalone updater."""
    try:
        shutil.rmtree(prepared.staging_dir, ignore_errors=True)
    except Exception:
        pass


def _format_bytes(n: Optional[int]) -> str:
    if n is None:
        return "?"
    value = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024.0:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024.0
    return f"{value:.1f} TB"


def _format_speed(bps: float) -> str:
    if not bps or bps < 1:
        return "0 KB/s"
    return f"{_format_bytes(int(bps))}/s"


class _AutoUpdateWorker(QObject):
    status = Signal(str)
    progress = Signal(int, int, float)  # downloaded, total(-1 unknown), speed_bps
    finished = Signal(object)  # PreparedUpdate
    failed = Signal(str)

    def __init__(
        self,
        remote_version: str,
        expected_exe_name: str,
        local_archive_path: Optional[Path] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._remote_version = remote_version
        self._expected_exe_name = expected_exe_name
        self._local_archive_path = local_archive_path
        self._cancelled = False

        self._staging_dir = Path(tempfile.mkdtemp(prefix="intenserp-update-extract-"))
        self._download_dir = self._staging_dir
        self._extract_dir = self._staging_dir

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        succeeded = False
        try:
            def should_cancel() -> bool:
                return bool(self._cancelled)

            def on_progress(p: DownloadProgress) -> None:
                total = p.total_bytes if p.total_bytes is not None else -1
                self.progress.emit(p.bytes_downloaded, total, float(p.speed_bytes_per_s))

            if self._local_archive_path is not None:
                self.status.emit("Staging local update archive...")
                prepared = prepare_update_from_local_archive(
                    archive_path=self._local_archive_path,
                    expected_exe_name=self._expected_exe_name,
                    download_dir=self._download_dir,
                    extract_dir=self._extract_dir,
                    progress_cb=on_progress,
                    should_cancel=should_cancel,
                )
            else:
                self.status.emit("Contacting GitHub…")
                self.status.emit("Downloading update…")
                prepared = prepare_update_from_github(
                    remote_version=self._remote_version,
                    expected_exe_name=self._expected_exe_name,
                    download_dir=self._download_dir,
                    extract_dir=self._extract_dir,
                    progress_cb=on_progress,
                    should_cancel=should_cancel,
                )

            self.status.emit(
                "Local archive staged." if self._local_archive_path is not None else "Download complete."
            )
            succeeded = True
            self.finished.emit(prepared)
        except AutoUpdateError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if not succeeded:
                try:
                    shutil.rmtree(self._staging_dir, ignore_errors=True)
                except Exception:
                    pass


class UpdateDownloadDialog(QDialog):
    """
    Downloads and prepares an update from GitHub.

    On success, sets self.prepared_update and enables the install action (implemented in follow-up).
    """

    def __init__(
        self,
        remote_version: str,
        local_archive_path: Optional[Path | str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._remote_version = remote_version
        self._local_archive_path = (
            Path(local_archive_path).expanduser().resolve() if local_archive_path else None
        )
        self.prepared_update: Optional[PreparedUpdate] = None
        self._cancel_requested = False
        self._install_started = False
        self._install_task: asyncio.Task | None = None
        self._legacy_restore_config_logs = self._read_legacy_restore_config_logs_setting()

        self.setWindowTitle(
            "Preparing Debug Update" if self._local_archive_path is not None else "Downloading Update"
        )
        self.setModal(True)
        self.setFixedWidth(520)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("updateDownloadCard")
        card.setStyleSheet(
            f"""
            QFrame#updateDownloadCard {{
                background-color: {BrandColors.WINDOW_BG};
                border: none;
            }}
            """
        )
        root_layout.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(12)

        title = QLabel(
            "Preparing debug update..." if self._local_archive_path is not None else "Downloading update…"
        )
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"""
            font-size: {BrandColors.FONT_SIZE_TITLE};
            font-weight: 800;
            color: {BrandColors.TEXT_PRIMARY};
            background-color: transparent;
            """
        )
        layout.addWidget(title)

        self._status_label = QLabel("Preparing…")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            f"""
            font-size: {BrandColors.FONT_SIZE_REGULAR};
            color: {BrandColors.TEXT_SECONDARY};
            background-color: transparent;
            """
        )
        layout.addWidget(self._status_label)

        self._progress = RoundedProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(14)
        layout.addWidget(self._progress)

        self._details_label = QLabel("0 MB / ?  •  0 KB/s")
        self._details_label.setAlignment(Qt.AlignCenter)
        self._details_label.setStyleSheet(
            f"""
            font-size: {BrandColors.FONT_SIZE_SMALL};
            color: {BrandColors.TEXT_DISABLED};
            background-color: transparent;
            """
        )
        layout.addWidget(self._details_label)

        self._asset_label = QLabel("")
        self._asset_label.setAlignment(Qt.AlignCenter)
        self._asset_label.setWordWrap(True)
        self._asset_label.setStyleSheet(
            f"""
            font-size: {BrandColors.FONT_SIZE_SMALL};
            color: {BrandColors.TEXT_DISABLED};
            background-color: transparent;
            """
        )
        layout.addWidget(self._asset_label)

        layout.addWidget(self._build_button_row())

        self._start_worker()

    def closeEvent(self, event):
        if self._install_started:
            event.ignore()
            return

        # Best-effort cancellation when the user closes the dialog.
        self._cancel_requested = True
        if self.prepared_update is None and self._worker_thread_is_running():
            self._request_worker_cancel()
            event.ignore()
            return
        self._cancel_worker()
        self._discard_prepared_update()
        super().closeEvent(event)

    def _build_button_row(self) -> QFrame:
        row = QFrame()
        row.setStyleSheet("background-color: transparent;")

        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {BrandColors.SIDEBAR_BG};
                color: {BrandColors.TEXT_PRIMARY};
                border: none;
                padding: 10px 14px;
                border-radius: 8px;
                font-size: {BrandColors.FONT_SIZE_REGULAR};
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {BrandColors.ITEM_HOVER};
            }}
            """
        )
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self._cancel_btn, 1)

        self._install_btn = QPushButton("Install && Restart")
        self._install_btn.setCursor(Qt.PointingHandCursor)
        self._install_btn.setEnabled(False)
        self._install_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {BrandColors.ACCENT};
                color: {BrandColors.TEXT_PRIMARY};
                border: none;
                padding: 10px 14px;
                border-radius: 8px;
                font-size: {BrandColors.FONT_SIZE_REGULAR};
                font-weight: 800;
            }}
            QPushButton:hover {{
                background-color: #4a80e0;
            }}
            QPushButton:pressed {{
                background-color: #3c6ac3;
            }}
            QPushButton:disabled {{
                background-color: {BrandColors.TEXT_DISABLED};
                color: {BrandColors.TEXT_PRIMARY};
            }}
            """
        )
        IconUtils.apply_icon(self._install_btn, IconType.BACKUP, BrandColors.TEXT_PRIMARY, size=16)
        self._install_btn.setIconSize(QSize(16, 16))
        self._install_btn.clicked.connect(self._on_install_clicked)
        layout.addWidget(self._install_btn, 1)
        return row

    def _start_worker(self) -> None:
        if not sys.platform.startswith(("win", "linux")):
            QMessageBox.warning(self, "Auto-Update", "Auto-update is supported only on Windows and Linux.")
            self.reject()
            return

        if not getattr(sys, "frozen", False):
            QMessageBox.warning(
                self, "Auto-Update", "Auto-update is available only in the packaged (PyInstaller) build."
            )
            self.reject()
            return

        expected_exe_name = Path(sys.executable).name
        self._thread = QThread(self)
        self._worker = _AutoUpdateWorker(
            remote_version=self._remote_version,
            expected_exe_name=expected_exe_name,
            local_archive_path=self._local_archive_path,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status.connect(self._on_status)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _cancel_worker(self) -> None:
        worker = getattr(self, "_worker", None)
        thread = getattr(self, "_thread", None)
        if worker is not None:
            try:
                worker.cancel()
            except Exception:
                pass
        if thread is not None:
            try:
                thread.quit()
                thread.wait(1500)
            except Exception:
                pass

    def _worker_thread_is_running(self) -> bool:
        thread = getattr(self, "_thread", None)
        try:
            return bool(thread is not None and thread.isRunning())
        except Exception:
            return False

    def _request_worker_cancel(self) -> None:
        worker = getattr(self, "_worker", None)
        if worker is not None:
            try:
                worker.cancel()
            except Exception:
                pass
        self._status_label.setText("Canceling...")
        self._cancel_btn.setEnabled(False)
        self._install_btn.setEnabled(False)
        self._progress.setRange(0, 0)

    def _discard_prepared_update(self) -> None:
        prepared = self.prepared_update
        if prepared is None or self._install_started:
            return
        _cleanup_prepared_update(prepared)
        self.prepared_update = None

    def _on_status(self, text: str) -> None:
        self._status_label.setText(text or "")

    def _on_progress(self, downloaded: int, total: int, speed_bps: float) -> None:
        total_bytes = None if total < 0 else int(total)
        self._details_label.setText(
            f"{_format_bytes(downloaded)} / {_format_bytes(total_bytes)}  •  {_format_speed(speed_bps)}"
        )
        if total_bytes is None or total_bytes <= 0:
            self._progress.setRange(0, 0)  # indeterminate
            return
        if self._progress.maximum() == 0:
            self._progress.setRange(0, 100)
        pct = int((downloaded / total_bytes) * 100) if total_bytes else 0
        self._progress.setValue(max(0, min(100, pct)))

    def _on_finished(self, prepared: PreparedUpdate) -> None:
        if self._cancel_requested:
            self.prepared_update = prepared
            self._cancel_worker()
            self._discard_prepared_update()
            self.reject()
            return
        self._cancel_requested = False
        self.prepared_update = prepared
        self._cancel_btn.setText("Close")
        self._status_label.setText("Ready to install.")
        self._install_btn.setEnabled(True)
        self._asset_label.setText(f"{prepared.tag}  •  {prepared.asset_name}")
        self._cancel_worker()

    def _on_failed(self, message: str) -> None:
        self._cancel_worker()
        if self._cancel_requested:
            self.reject()
            return
        failure_message = (
            "Failed to prepare the local update archive."
            if self._local_archive_path is not None
            else "Failed to download the update."
        )
        QMessageBox.warning(
            self,
            "Auto-Update",
            f"{failure_message}\n\n"
            f"{message}",
        )
        self.reject()

    def _on_cancel_clicked(self) -> None:
        if self.prepared_update is not None:
            self._discard_prepared_update()
            self.accept()
            return
        self._cancel_requested = True
        self._request_worker_cancel()

    def _find_stop_services_owner(self):
        current = self.parent()
        while current is not None:
            stop_services = getattr(current, "stop_services", None)
            if callable(stop_services):
                return current
            try:
                current = current.parent()
            except Exception:
                return None
        return None

    def _read_legacy_restore_config_logs_setting(self) -> bool:
        current = self.parent()
        while current is not None:
            config_manager = getattr(current, "config_manager", None)
            get_setting = getattr(config_manager, "get_setting", None)
            if callable(get_setting):
                try:
                    return bool(
                        get_setting(
                            "application_settings",
                            "legacy_update_restore_config_logs",
                        )
                    )
                except Exception:
                    return False
            try:
                current = current.parent()
            except Exception:
                return False
        return False

    async def _stop_services_before_update(self) -> None:
        owner = self._find_stop_services_owner()
        if owner is None:
            return

        stop_services = getattr(owner, "stop_services", None)
        if not callable(stop_services):
            return

        try:
            result = stop_services(update_ui=False)
        except TypeError:
            result = stop_services()

        if inspect.isawaitable(result):
            await result

    async def _prepare_and_launch_updater(self, prepared: PreparedUpdate, updater_exe: Path) -> None:
        try:
            self._status_label.setText("Stopping services...")
            await asyncio.wait_for(self._stop_services_before_update(), timeout=60.0)
        except asyncio.TimeoutError:
            self._on_install_prepare_failed("Timed out while waiting for running services to stop.")
            return
        except Exception as exc:
            self._on_install_prepare_failed(str(exc))
            return

        if not self._install_started:
            return
        try:
            self._launch_updater(prepared, updater_exe)
        except Exception as exc:
            self._on_install_prepare_failed(str(exc))

    def _on_install_prepare_failed(self, message: str) -> None:
        self._install_started = False
        self._status_label.setText("Ready to install.")
        self._install_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        self._progress.setRange(0, 100)
        self._progress.setValue(100)
        QMessageBox.warning(
            self,
            "Auto-Update",
            "Failed to stop running services before starting the updater.\n\n"
            f"{message}",
        )

    def _launch_updater(self, prepared: PreparedUpdate, updater_exe: Path) -> None:
        self._status_label.setText("Launching Updater...")

        install_dir = Path(sys.executable).resolve().parent
        exe_name = Path(sys.executable).name
        cmd = [
            str(updater_exe),
            "--install-dir",
            str(install_dir),
            "--app-pid",
            str(os.getpid()),
            "--exe-name",
            str(exe_name),
            "--payload-dir",
            str(prepared.extracted_app_root),
        ]
        release_url = str(prepared.release_html_url or "").strip()
        if release_url:
            cmd += ["--release-url", release_url]
        if self._legacy_restore_config_logs:
            cmd.append("--legacy-restore-config-logs")

        self._launcher_thread = QThread(self)
        self._launcher_worker = _UpdaterLauncher(cmd, tempfile.gettempdir())
        self._launcher_worker.moveToThread(self._launcher_thread)
        self._launcher_thread.started.connect(self._launcher_worker.run)
        self._launcher_worker.succeeded.connect(self._on_updater_started)
        self._launcher_worker.failed.connect(
            lambda message: self._on_updater_start_failed(prepared, message)
        )
        self._launcher_thread.start()

    def _on_install_clicked(self) -> None:
        if self._install_started:
            return

        prepared = self.prepared_update
        if prepared is None:
            return

        reply = QMessageBox.question(
            self,
            "Install Update",
            "The app will close to install the update and then relaunch.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            updater_exe = _find_staged_updater(prepared)
        except Exception as exc:
            QMessageBox.warning(self, "Auto-Update", f"Update package is missing the updater.\n\n{exc}")
            return

        # lock ui and launch the updater off the main thread so the UI stays responsive while the updater starts
        self._install_started = True
        self._status_label.setText("Preparing update...")
        self._install_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._progress.setRange(0, 0)  # indeterminate spinner

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._launch_updater(prepared, updater_exe)
            return

        self._install_task = loop.create_task(
            self._prepare_and_launch_updater(prepared, updater_exe)
        )

        def _clear_install_task(_task: asyncio.Task) -> None:
            self._install_task = None

        self._install_task.add_done_callback(_clear_install_task)

    def _on_updater_started(self) -> None:
        """Called on the main thread once the updater process is running."""
        self._status_label.setText("Running Updater...")

        def force_exit():
            os._exit(0)

        QTimer.singleShot(500, force_exit)

    def _on_updater_start_failed(self, prepared: PreparedUpdate, message: str = "") -> None:
        """Called on the main thread if the updater failed to launch."""
        self._install_started = False
        self._status_label.setText("Ready to install.")
        self._install_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        self._progress.setRange(0, 100)
        self._progress.setValue(100)
        QMessageBox.warning(
            self,
            "Auto-Update",
            "Failed to start the updater.\n\n"
            f"{message}\n\n"
            "You can still download manually from the release page.",
        )
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl(prepared.release_html_url))

    # Icon rendering is handled centrally by IconUtils
