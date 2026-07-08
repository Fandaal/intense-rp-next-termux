from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ui.core.brand import BrandColors
from ui.widgets.rounded_progress_bar import RoundedProgressBar
from ui.widgets.components import Description, Divider, StyledButton
from utils.browser_manager import (
    PatchrightCommandResult,
    install_chromium_browser,
    probe_browser_executable_path,
    uninstall_playwright_browsers,
    uninstall_playwright_browsers_all,
)
from utils.logger import Logger


class BrowserManagerWindow(QMainWindow):
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self._browser_path: str | None = None
        self._current_task: asyncio.Task | None = None
        self._refresh_task: asyncio.Task | None = None
        self._busy = False

        self.setWindowTitle("Browser Manager")
        self.resize(600, 520)
        self.setStyleSheet(f"background-color: {BrandColors.WINDOW_BG};")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Browser Manager")
        title.setStyleSheet(
            f"""
            font-size: 24px;
            font-weight: bold;
            color: {BrandColors.TEXT_PRIMARY};
            """
        )
        layout.addWidget(title)

        layout.addWidget(
            Description(
                "Manage the Playwright/Patchright Chromium install used by IntenseRP. "
            )
        )

        layout.addWidget(Divider("Current Browser Installation"))

        self.path_label = QLabel("Checking browser installation...")
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.path_label.setStyleSheet(
            f"""
            QLabel {{
                color: {BrandColors.TEXT_PRIMARY};
                background-color: {BrandColors.SIDEBAR_BG};
                border: 1px solid {BrandColors.INPUT_BORDER};
                border-radius: 8px;
                padding: 10px 12px;
                font-size: {BrandColors.FONT_SIZE_REGULAR};
            }}
            """
        )
        layout.addWidget(self.path_label)

        self.path_hint_label = QLabel("This points to the actual Chromium executable Playwright will launch.")
        self.path_hint_label.setWordWrap(True)
        self.path_hint_label.setStyleSheet(
            f"""
            color: {BrandColors.TEXT_DISABLED};
            background-color: transparent;
            font-size: {BrandColors.FONT_SIZE_SMALL};
            """
        )
        layout.addWidget(self.path_hint_label)

        self.notice_label = QLabel("")
        self.notice_label.setWordWrap(True)
        self.notice_label.setStyleSheet(
            f"""
            color: {BrandColors.TEXT_SECONDARY};
            background-color: transparent;
            font-size: {BrandColors.FONT_SIZE_SMALL};
            """
        )
        layout.addWidget(self.notice_label)

        layout.addWidget(Divider("Browser Actions"))

        row = QHBoxLayout()
        row.setSpacing(10)

        self.delete_btn = StyledButton("Delete")
        self.delete_btn.setToolTip("Remove the current Playwright browser installation.")
        self.delete_btn.clicked.connect(self._start_delete)
        row.addWidget(self.delete_btn, stretch=1)

        self.reinstall_btn = StyledButton("Reinstall")
        self.reinstall_btn.setToolTip("Delete the current browser install and download a fresh one.")
        self.reinstall_btn.clicked.connect(self._start_reinstall)
        row.addWidget(self.reinstall_btn, stretch=1)

        self.install_btn = StyledButton("Install")
        self.install_btn.setToolTip("Install the Chromium browser bundle used by IntenseRP.")
        self.install_btn.clicked.connect(self._start_install)
        row.addWidget(self.install_btn, stretch=1)

        layout.addLayout(row)

        self.status_label = QLabel("Checking browser state...")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            f"""
            color: {BrandColors.TEXT_SECONDARY};
            background-color: transparent;
            font-size: {BrandColors.FONT_SIZE_SMALL};
            """
        )
        layout.addWidget(self.status_label)

        self.progress = RoundedProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(14)
        layout.addWidget(self.progress)

        layout.addWidget(Divider())

        close_row = QHBoxLayout()
        close_row.addStretch()
        self.close_btn = StyledButton("Close")
        self.close_btn.clicked.connect(self.close)
        close_row.addWidget(self.close_btn)
        layout.addLayout(close_row)

        self._notice_timer = QTimer(self)
        self._notice_timer.setInterval(1000)
        self._notice_timer.timeout.connect(self._refresh_runtime_notice)
        self._notice_timer.start()

        self._refresh_runtime_notice()
        QTimer.singleShot(0, self.refresh_state)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_runtime_notice()
        self.refresh_state()

    def _is_task_running(self, task: asyncio.Task | None) -> bool:
        return task is not None and (not task.done())

    def _services_locked(self) -> bool:
        main_window = getattr(self, "main_window", None)
        if main_window is None:
            return False

        try:
            if bool(main_window._are_services_running()):
                return True
        except Exception:
            pass

        try:
            return bool(main_window._is_services_busy())
        except Exception:
            return False

    def _browser_download_mirror_url(self) -> str:
        main_window = getattr(self, "main_window", None)
        config_manager = getattr(main_window, "config_manager", None)
        if config_manager is None:
            return ""

        try:
            return str(
                config_manager.get_setting(
                    "system_settings",
                    "browser_download_mirror_url",
                )
                or ""
            ).strip()
        except Exception:
            return ""

    def _running_driver_browser_path(self) -> str | None:
        main_window = getattr(self, "main_window", None)
        if main_window is None:
            return None

        driver = getattr(main_window, "driver", None)
        playwright = getattr(driver, "playwright", None)
        if playwright is None:
            return None

        try:
            browser_path = str(playwright.chromium.executable_path or "").strip()
        except Exception:
            return None

        if not browser_path:
            return None

        path_obj = Path(browser_path)
        return str(path_obj) if path_obj.exists() else None

    async def _detect_browser_path(self) -> str | None:
        running_path = self._running_driver_browser_path()
        if running_path:
            return running_path
        return await probe_browser_executable_path()

    def _set_status(self, text: str, tone: str = "secondary") -> None:
        color_map = {
            "secondary": BrandColors.TEXT_SECONDARY,
            "info": BrandColors.ACCENT,
            "success": BrandColors.SUCCESS,
            "warning": BrandColors.WARNING,
            "error": BrandColors.DANGER,
        }
        color = color_map.get(tone, BrandColors.TEXT_SECONDARY)
        self.status_label.setStyleSheet(
            f"""
            color: {color};
            background-color: transparent;
            font-size: {BrandColors.FONT_SIZE_SMALL};
            """
        )
        self.status_label.setText(text or "")

    def _set_progress_step(self, current_step: int, total_steps: int) -> None:
        if total_steps <= 0:
            self.progress.setValue(0)
            return

        current = max(0, min(int(current_step), int(total_steps)))
        value = int(round((current / total_steps) * 100))
        self.progress.setValue(value)

    def _update_action_buttons(self) -> None:
        has_browser = bool(self._browser_path)
        can_click = not self._busy

        self.delete_btn.setEnabled(can_click and has_browser)
        self.reinstall_btn.setEnabled(can_click and has_browser)
        self.install_btn.setEnabled(can_click and (not has_browser))
        self.close_btn.setEnabled(True)

    def _refresh_idle_status(self) -> None:
        if self._busy:
            return

        if self._browser_path:
            self._set_status("Browser installation detected and ready.", "secondary")
        else:
            self._set_status("No browser installation detected yet.", "secondary")

    def _apply_browser_state(self, browser_path: str | None, *, update_status: bool = True) -> None:
        self._browser_path = browser_path or None

        if self._browser_path:
            self.path_label.setText(self._browser_path)
        else:
            self.path_label.setText("No browser installation detected.")

        self._update_action_buttons()
        if update_status:
            self._refresh_idle_status()

    def _refresh_runtime_notice(self) -> None:
        if self._services_locked():
            text = (
                "Services are active right now. Stop everything from the main window "
                "before changing the browser installation."
            )
            color = BrandColors.WARNING
        else:
            text = (
                "These actions are meant to run while the browser/API services are stopped. "
                "If they are still running, Browser Manager will block the action."
            )
            color = BrandColors.TEXT_SECONDARY

        self.notice_label.setStyleSheet(
            f"""
            color: {color};
            background-color: transparent;
            font-size: {BrandColors.FONT_SIZE_SMALL};
            """
        )
        self.notice_label.setText(text)

    @staticmethod
    def _format_patchright_output(result: PatchrightCommandResult | None) -> str:
        if result is None:
            return ""

        parts: list[str] = []
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if stdout:
            parts.append(f"stdout:\n{stdout}")
        if stderr:
            parts.append(f"stderr:\n{stderr}")
        return "\n\n".join(parts).strip()

    def _show_details_dialog(
        self,
        *,
        title: str,
        text: str,
        icon=QMessageBox.Information,
        informative_text: str = "",
        details: str = "",
    ) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setIcon(icon)
        dialog.setText(text)
        if informative_text:
            dialog.setInformativeText(informative_text)
        if details:
            dialog.setDetailedText(details)
        dialog.exec()

    def _show_delete_incomplete_dialog(
        self,
        *,
        informative_text: str,
        details: str,
    ) -> bool:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Delete Incomplete")
        dialog.setIcon(QMessageBox.Warning)
        dialog.setText("Patchright uninstall completed, but the browser executable is still present.")
        if informative_text:
            dialog.setInformativeText(informative_text)
        if details:
            dialog.setDetailedText(details)

        delete_all_btn = dialog.addButton("Delete All (--all)", QMessageBox.ActionRole)
        dialog.addButton(QMessageBox.Close)
        dialog.exec()
        return dialog.clickedButton() is delete_all_btn

    def _confirm_delete_all_after_incomplete(self) -> bool:
        reply = QMessageBox.question(
            self,
            "Delete All Browser Registrations",
            "This will run `patchright uninstall --all`.\n\n"
            "That removes browser registrations for all Playwright/Patchright installations on this machine, "
            "not just IntenseRP. Other tools or environments may need to reinstall their browser components afterward.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def refresh_state(self) -> None:
        if self._busy or self._is_task_running(self._refresh_task):
            return

        self._refresh_task = asyncio.create_task(self._refresh_state_async())

    async def _refresh_state_async(self) -> None:
        try:
            browser_path = await self._detect_browser_path()
        except Exception as e:
            Logger.warning(f"Browser Manager: failed to refresh browser state: {e}")
            browser_path = None

        self._apply_browser_state(browser_path)
        self._refresh_runtime_notice()

    def _require_services_stopped(self) -> bool:
        if not self._services_locked():
            return True

        self._set_status("Stop everything first before managing the browser install.", "error")
        QMessageBox.warning(
            self,
            "Browser Manager",
            "The API/browser services are already running.\n\n"
            "Stop everything from the main window first, then try again.",
        )
        return False

    def _launch_task(self, coro) -> None:
        if self._busy or self._is_task_running(self._current_task):
            return

        self._current_task = asyncio.create_task(coro)

        def _finalize(task: asyncio.Task) -> None:
            if self._current_task is task:
                self._current_task = None
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                Logger.error(f"Browser Manager task failed unexpectedly: {e}")

        self._current_task.add_done_callback(_finalize)

    def _start_install(self) -> None:
        if not self._require_services_stopped():
            return
        self._launch_task(self._run_install())

    def _start_delete(self) -> None:
        if not self._require_services_stopped():
            return

        if not self._browser_path:
            return

        reply = QMessageBox.question(
            self,
            "Delete Browser",
            "This will remove the local Playwright browser installation used by IntenseRP.\n\n"
            "You can install it again later from this window.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._launch_task(self._run_delete())

    def _start_reinstall(self) -> None:
        if not self._require_services_stopped():
            return

        if not self._browser_path:
            return

        reply = QMessageBox.question(
            self,
            "Reinstall Browser",
            "This will remove the current Playwright browser installation and download a fresh one.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._launch_task(self._run_reinstall())

    def _finalize_operation(self, browser_path: str | None, message: str, tone: str) -> None:
        self._busy = False
        self._apply_browser_state(browser_path, update_status=False)
        self._set_status(message, tone)
        self._refresh_runtime_notice()

    async def _run_install(self) -> None:
        self._busy = True
        self._update_action_buttons()
        total_steps = 2

        try:
            self._set_progress_step(1, total_steps)
            download_host = self._browser_download_mirror_url()
            install_label = (
                "Step 1 of 2: Installing Chromium browser from configured mirror..."
                if download_host
                else "Step 1 of 2: Installing Chromium browser..."
            )
            self._set_status(install_label, "info")
            await install_chromium_browser(download_host=download_host)

            self._set_progress_step(2, total_steps)
            self._set_status("Step 2 of 2: Refreshing browser status...", "info")
            browser_path = await self._detect_browser_path()
            if not browser_path:
                raise RuntimeError("Install finished, but the browser executable could not be found afterward.")

            Logger.success(f"Browser Manager: browser installed at {browser_path}")
            self._finalize_operation(browser_path, "Browser installation complete.", "success")
        except Exception as e:
            Logger.error(f"Browser Manager install failed: {e}")
            browser_path = await self._detect_browser_path()
            self._finalize_operation(browser_path, f"Install failed: {e}", "error")
            QMessageBox.warning(self, "Install Failed", str(e))

    async def _run_delete(self) -> None:
        self._busy = True
        self._update_action_buttons()
        total_steps = 2

        try:
            self._set_progress_step(1, total_steps)
            self._set_status("Step 1 of 2: Removing browser installation...", "info")
            uninstall_result = await uninstall_playwright_browsers()

            self._set_progress_step(2, total_steps)
            self._set_status("Step 2 of 2: Refreshing browser status...", "info")
            browser_path = await self._detect_browser_path()
            if browser_path:
                details = self._format_patchright_output(uninstall_result)
                if uninstall_result.other_installations_detected:
                    remaining_count = uninstall_result.other_installations_browser_count
                    if remaining_count is None:
                        informative = (
                            "Patchright reports that other Playwright installations still have "
                            "browser caches registered, so this shared browser folder was not removed."
                        )
                    else:
                        informative = (
                            f"Patchright reports that {remaining_count} browser cache folder(s) are still "
                            "registered to other Playwright installations, so this shared browser folder "
                            "was not removed."
                        )

                    Logger.warning(
                        "Browser Manager delete: uninstall completed, but the browser executable is still "
                        "present because other Playwright installations still reference browser caches."
                    )
                    self._finalize_operation(
                        browser_path,
                        "Delete completed, but this browser cache is still referenced by another installation.",
                        "warning",
                    )
                    if self._show_delete_incomplete_dialog(
                        informative_text=informative,
                        details=details,
                    ) and self._confirm_delete_all_after_incomplete():
                        await self._run_delete_all()
                    return

                raise RuntimeError(
                    "Patchright reported success, but the browser executable is still present.\n\n"
                    "This usually means Windows still had files locked, or a different installation is "
                    "still holding onto the same browser cache.\n\n"
                    f"Detected executable:\n{browser_path}"
                )

            Logger.success("Browser Manager: browser installation removed.")
            self._finalize_operation(None, "Browser installation removed.", "success")
        except Exception as e:
            Logger.error(f"Browser Manager delete failed: {e}")
            browser_path = await self._detect_browser_path()
            self._finalize_operation(browser_path, f"Delete failed: {e}", "error")
            self._show_details_dialog(
                title="Delete Failed",
                text=str(e),
                icon=QMessageBox.Warning,
            )

    async def _run_delete_all(self) -> None:
        self._busy = True
        self._update_action_buttons()
        total_steps = 2
        uninstall_result: PatchrightCommandResult | None = None

        try:
            self._set_progress_step(1, total_steps)
            self._set_status("Step 1 of 2: Removing browser registrations from all installs...", "info")
            uninstall_result = await uninstall_playwright_browsers_all()

            self._set_progress_step(2, total_steps)
            self._set_status("Step 2 of 2: Refreshing browser status...", "info")
            browser_path = await self._detect_browser_path()
            if browser_path:
                raise RuntimeError(
                    "Patchright uninstall --all completed, but the browser executable is still present.\n\n"
                    "This usually points to file locking or a path/cache mismatch.\n\n"
                    f"Detected executable:\n{browser_path}"
                )

            Logger.success("Browser Manager: browser installation removed with --all.")
            self._finalize_operation(None, "Browser installation removed from all Playwright installs.", "success")
        except Exception as e:
            Logger.error(f"Browser Manager delete --all failed: {e}")
            browser_path = await self._detect_browser_path()
            self._finalize_operation(browser_path, f"Delete all failed: {e}", "error")
            self._show_details_dialog(
                title="Delete All Failed",
                text=str(e),
                icon=QMessageBox.Warning,
                details=self._format_patchright_output(uninstall_result),
            )

    async def _run_reinstall(self) -> None:
        self._busy = True
        self._update_action_buttons()
        total_steps = 3

        try:
            self._set_progress_step(1, total_steps)
            self._set_status("Step 1 of 3: Removing current browser installation...", "info")
            await uninstall_playwright_browsers()

            self._set_progress_step(2, total_steps)
            download_host = self._browser_download_mirror_url()
            install_label = (
                "Step 2 of 3: Installing fresh Chromium browser from configured mirror..."
                if download_host
                else "Step 2 of 3: Installing fresh Chromium browser..."
            )
            self._set_status(install_label, "info")
            await install_chromium_browser(download_host=download_host)

            self._set_progress_step(3, total_steps)
            self._set_status("Step 3 of 3: Refreshing browser status...", "info")
            browser_path = await self._detect_browser_path()
            if not browser_path:
                raise RuntimeError("Reinstall finished, but the browser executable could not be found afterward.")

            Logger.success(f"Browser Manager: browser reinstalled at {browser_path}")
            self._finalize_operation(browser_path, "Browser reinstall complete.", "success")
        except Exception as e:
            Logger.error(f"Browser Manager reinstall failed: {e}")
            browser_path = await self._detect_browser_path()
            self._finalize_operation(browser_path, f"Reinstall failed: {e}", "error")
            QMessageBox.warning(self, "Reinstall Failed", str(e))
