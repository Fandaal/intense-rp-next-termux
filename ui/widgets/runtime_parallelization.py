from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor, QIntValidator
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from drivers.providers import DriverProvider
from ui.core.animation_settings import animations_disabled
from ui.core.brand import BrandColors
from ui.core.icons import IconType, IconUtils
from ui.widgets.smooth_scroll_area import SmoothScrollArea


def _blend_hex_colors(color_a: str, color_b: str, ratio: float) -> str:
    ratio = max(0.0, min(float(ratio), 1.0))
    inv = 1.0 - ratio
    first = QColor(color_a)
    second = QColor(color_b)
    return QColor(
        int(round(first.red() * inv + second.red() * ratio)),
        int(round(first.green() * inv + second.green() * ratio)),
        int(round(first.blue() * inv + second.blue() * ratio)),
        int(round(first.alpha() * inv + second.alpha() * ratio)),
    ).name()


class _RuntimeProviderLaneRow(QFrame):
    toggled = Signal(str)
    instanceChanged = Signal(str, int)

    def __init__(
        self,
        provider: DriverProvider,
        *,
        icon_file: str | None,
        selected: bool,
        locked: bool,
        full_mode: bool,
        instance_count: int,
        max_instances: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._provider = provider
        self._icon_file = icon_file
        self._selected = bool(selected)
        self._locked = bool(locked)
        self._full_mode = bool(full_mode)
        self._max_instances = max(1, int(max_instances or 1))
        self.setObjectName("runtimeProviderLaneRow")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(46)

        if self._locked:
            self.setToolTip("Forced on because it's your current provider")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self._icon_label = QLabel()
        self._icon_label.setStyleSheet("background-color: transparent;")
        self._icon_label.setFixedSize(18, 18)
        if self._icon_file:
            pixmap = IconUtils.get_pixmap(
                self._icon_file,
                color=BrandColors.TEXT_PRIMARY,
                size=16,
                dpr=self.devicePixelRatioF(),
            )
            if not pixmap.isNull():
                self._icon_label.setPixmap(pixmap)
        layout.addWidget(self._icon_label, 0, Qt.AlignVCenter)

        self._text_label = QLabel(provider.value)
        self._text_label.setStyleSheet(
            f"""
            color: {BrandColors.TEXT_PRIMARY};
            background-color: transparent;
            font-size: {BrandColors.FONT_SIZE_REGULAR};
            font-family: {BrandColors.FONT_FAMILY};
            font-weight: 500;
            """
        )
        layout.addWidget(self._text_label, 1, Qt.AlignVCenter)

        self._instance_input = QLineEdit()
        self._instance_input.setAlignment(Qt.AlignCenter)
        self._instance_input.setMaxLength(3)
        self._instance_input.setFixedWidth(58)
        self._instance_input.setValidator(QIntValidator(1, self._max_instances, self._instance_input))
        self._instance_input.setText(str(self._clamp_count(instance_count)))
        self._instance_input.setToolTip("Browser instances to launch for this provider")
        self._instance_input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {BrandColors.INPUT_BG};
                color: {BrandColors.TEXT_PRIMARY};
                border: 1px solid {BrandColors.INPUT_BORDER};
                border-radius: 6px;
                padding: 5px 6px;
                font-size: {BrandColors.FONT_SIZE_REGULAR};
                font-family: {BrandColors.FONT_FAMILY};
            }}
            QLineEdit:focus {{
                border: 1px solid {BrandColors.ACCENT};
            }}
            """
        )
        self._instance_input.textEdited.connect(self._on_instance_text_edited)
        self._instance_input.editingFinished.connect(self._normalize_instance_text)
        layout.addWidget(self._instance_input, 0, Qt.AlignVCenter)

        self._check_label = QLabel()
        self._check_label.setStyleSheet("background-color: transparent;")
        self._check_label.setFixedSize(18, 18)
        self._check_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._check_label, 0, Qt.AlignVCenter)

        self._refresh()

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected) or self._locked
        self._refresh()

    def set_full_mode(self, full_mode: bool) -> None:
        self._full_mode = bool(full_mode)
        self._refresh()

    def instance_count(self) -> int:
        return self._clamp_count(self._instance_input.text())

    def _clamp_count(self, value) -> int:
        try:
            count = int(value)
        except (TypeError, ValueError):
            count = 1
        return max(1, min(self._max_instances, count))

    def _on_instance_text_edited(self, text: str) -> None:
        if not str(text or "").strip():
            return
        count = self._clamp_count(text)
        if str(count) != str(text):
            self._instance_input.blockSignals(True)
            self._instance_input.setText(str(count))
            self._instance_input.blockSignals(False)
        self.instanceChanged.emit(self._provider.value, count)

    def _normalize_instance_text(self) -> None:
        count = self._clamp_count(self._instance_input.text())
        if self._instance_input.text() != str(count):
            self._instance_input.setText(str(count))
        self.instanceChanged.emit(self._provider.value, count)

    def _refresh_check_icon(self) -> None:
        if not self._selected:
            self._check_label.clear()
            return

        pixmap = IconUtils.get_pixmap(
            IconType.CONFIRM,
            color=BrandColors.WARNING if self._locked else BrandColors.TEXT_PRIMARY,
            size=16,
            dpr=self.devicePixelRatioF(),
        )
        if not pixmap.isNull():
            self._check_label.setPixmap(pixmap)

    def _refresh(self) -> None:
        self._instance_input.setVisible(self._selected and self._full_mode)
        self._refresh_check_icon()
        self._apply_style()

    def _apply_style(self) -> None:
        if self._locked:
            background = _blend_hex_colors(BrandColors.INPUT_BG, BrandColors.WARNING, 0.18)
            border = BrandColors.WARNING
            hover = _blend_hex_colors(BrandColors.INPUT_BG, BrandColors.WARNING, 0.28)
        elif self._selected:
            background = BrandColors.CATEGORY_ACTIVE_BG
            border = BrandColors.CATEGORY_ACTIVE_BORDER
            hover = _blend_hex_colors(BrandColors.CATEGORY_ACTIVE_BG, BrandColors.ACCENT, 0.26)
        else:
            background = BrandColors.INPUT_BG
            border = BrandColors.INPUT_BORDER
            hover = BrandColors.ITEM_HOVER

        self.setStyleSheet(
            f"""
            QFrame#runtimeProviderLaneRow {{
                background-color: {background};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QFrame#runtimeProviderLaneRow:hover {{
                background-color: {hover};
                border: 1px solid {border if self._locked else BrandColors.CATEGORY_ACTIVE_BORDER};
            }}
            """
        )

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton or not self.rect().contains(event.position().toPoint()):
            super().mouseReleaseEvent(event)
            return

        clicked_child = self.childAt(event.position().toPoint())
        if clicked_child is self._instance_input:
            super().mouseReleaseEvent(event)
            return

        if not self._locked:
            self.toggled.emit(self._provider.value)
        event.accept()


class _RuntimeProviderLanePopup(QFrame):
    stateChanged = Signal(object, object)

    def __init__(self, parent=None, *, max_instances: int = 32) -> None:
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self._providers: list[DriverProvider] = []
        self._selected: set[DriverProvider] = set()
        self._counts: dict[DriverProvider, int] = {}
        self._current_provider: DriverProvider | None = None
        self._full_mode = False
        self._icon_for_provider = None
        self._max_instances = max(1, int(max_instances or 1))

        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.hide()

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self._panel = QFrame(self)
        self._panel.setObjectName("runtimeProviderLanePopupPanel")
        self._panel.setAttribute(Qt.WA_StyledBackground, True)
        self._panel.setStyleSheet(
            f"""
            QFrame#runtimeProviderLanePopupPanel {{
                background-color: {BrandColors.WINDOW_BG};
                border: 1px solid {BrandColors.INPUT_BORDER};
                border-radius: 10px;
            }}
            """
        )
        outer_layout.addWidget(self._panel)

        self._pending_hide = False
        self._pos_anim = QPropertyAnimation(self, b"pos")
        self._pos_anim.setDuration(150)
        self._pos_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_anim.setDuration(150)
        self._opacity_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._anim_group = QParallelAnimationGroup(self)
        self._anim_group.addAnimation(self._pos_anim)
        self._anim_group.addAnimation(self._opacity_anim)
        self._anim_group.finished.connect(self._on_animation_finished)

        layout = QVBoxLayout(self._panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Providers in Parallel")
        title.setStyleSheet(
            f"""
            color: {BrandColors.TEXT_PRIMARY};
            background-color: transparent;
            font-size: {BrandColors.FONT_SIZE_LARGE};
            font-family: {BrandColors.FONT_FAMILY};
            font-weight: 800;
            padding: 0px 2px 4px 2px;
            """
        )
        layout.addWidget(title)

        self._scroll = SmoothScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            """
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            """
        )

        self._content = QWidget()
        self._content.setStyleSheet("background-color: transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 10, 0)
        self._content_layout.setSpacing(8)
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll)

    def animate_show(self, final_pos: QPoint) -> None:
        self._anim_group.stop()
        self._pending_hide = False
        self.setEnabled(True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        if animations_disabled():
            self.setWindowOpacity(1.0)
            self.move(final_pos)
            self.show()
            self.raise_()
            return

        start_pos = QPoint(final_pos.x(), final_pos.y() - 8)
        self.setWindowOpacity(0.0)
        self.move(start_pos)
        self.show()
        self.raise_()
        self.repaint()
        QApplication.processEvents()

        self._pos_anim.setStartValue(start_pos)
        self._pos_anim.setEndValue(final_pos)
        self._opacity_anim.setStartValue(0.0)
        self._opacity_anim.setEndValue(1.0)
        self._anim_group.start()

    def animate_hide(self) -> None:
        if not self.isVisible():
            return

        self._anim_group.stop()
        self.setEnabled(False)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        if animations_disabled():
            self.hide()
            self.setEnabled(True)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            self.setWindowOpacity(1.0)
            return

        current_pos = self.pos()
        end_pos = QPoint(current_pos.x(), current_pos.y() - 8)
        self._pending_hide = True
        self._pos_anim.setStartValue(current_pos)
        self._pos_anim.setEndValue(end_pos)
        self._opacity_anim.setStartValue(float(self.windowOpacity()))
        self._opacity_anim.setEndValue(0.0)
        self._anim_group.start()

    def _on_animation_finished(self) -> None:
        if not self._pending_hide:
            return
        self._pending_hide = False
        self.hide()
        self.setEnabled(True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setWindowOpacity(1.0)

    def set_state(
        self,
        *,
        providers: Iterable[DriverProvider],
        selected: Iterable[DriverProvider],
        counts: dict[DriverProvider, int],
        current_provider: DriverProvider | None,
        full_mode: bool,
        icon_for_provider,
    ) -> None:
        self._providers = list(providers or [])
        self._selected = {provider for provider in selected or [] if provider in self._providers}
        self._counts = {
            provider: self._clamp_count(counts.get(provider, 1))
            for provider in self._providers
        }
        self._current_provider = current_provider if current_provider in self._providers else None
        if self._current_provider is not None:
            self._selected.add(self._current_provider)
        self._full_mode = bool(full_mode)
        self._icon_for_provider = icon_for_provider
        self._rebuild_rows()

    def _clamp_count(self, value) -> int:
        try:
            count = int(value)
        except (TypeError, ValueError):
            count = 1
        return max(1, min(self._max_instances, count))

    def _emit_state(self) -> None:
        ordered_selected = [provider.value for provider in self._providers if provider in self._selected]
        counts = {
            provider.value: self._clamp_count(self._counts.get(provider, 1))
            for provider in self._providers
        }
        self.stateChanged.emit(ordered_selected, counts)

    def _rebuild_rows(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for provider in self._providers:
            row = _RuntimeProviderLaneRow(
                provider,
                icon_file=self._icon_for_provider(provider) if callable(self._icon_for_provider) else None,
                selected=provider in self._selected,
                locked=provider == self._current_provider,
                full_mode=self._full_mode,
                instance_count=self._counts.get(provider, 1),
                max_instances=self._max_instances,
            )
            row.toggled.connect(self._toggle_provider)
            row.instanceChanged.connect(self._change_instance_count)
            self._content_layout.addWidget(row)

        self._content_layout.addStretch(1)

    def _toggle_provider(self, provider_value: str) -> None:
        provider = DriverProvider.from_setting(provider_value)
        if provider is None or provider == self._current_provider:
            return
        if provider in self._selected:
            self._selected.remove(provider)
        else:
            self._selected.add(provider)
        self._rebuild_rows()
        self._emit_state()

    def _change_instance_count(self, provider_value: str, count: int) -> None:
        provider = DriverProvider.from_setting(provider_value)
        if provider is None:
            return
        self._counts[provider] = self._clamp_count(count)
        self._emit_state()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.animate_hide()
            event.accept()
            return
        super().keyPressEvent(event)


class RuntimeProviderLaneDropdown(QFrame):
    stateChanged = Signal()

    def __init__(self, parent=None, *, max_instances: int = 32) -> None:
        super().__init__(parent)
        self._providers: list[DriverProvider] = []
        self._selected: set[DriverProvider] = set()
        self._counts: dict[DriverProvider, int] = {}
        self._current_provider: DriverProvider | None = None
        self._full_mode = False
        self._consume_release = False
        self._popup: _RuntimeProviderLanePopup | None = None
        self._max_instances = max(1, int(max_instances or 1))

        self.setObjectName("runtimeProviderLaneDropdown")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"""
            QFrame#runtimeProviderLaneDropdown {{
                background-color: {BrandColors.INPUT_BG};
                border: 2px solid {BrandColors.INPUT_BORDER};
                border-radius: 8px;
            }}
            QFrame#runtimeProviderLaneDropdown:hover {{
                border: 2px solid {BrandColors.ACCENT};
            }}
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self._icon_label = QLabel()
        self._icon_label.setStyleSheet("background-color: transparent;")
        self._icon_label.setFixedSize(18, 18)
        layout.addWidget(self._icon_label, 0, Qt.AlignVCenter)

        self._text_label = QLabel()
        self._text_label.setMinimumWidth(0)
        self._text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self._text_label, 1, Qt.AlignVCenter)

        self._chevron_label = QLabel()
        self._chevron_label.setStyleSheet("background-color: transparent;")
        self._chevron_label.setFixedSize(16, 16)
        chevron = IconUtils.get_pixmap(
            "chevron-down.svg",
            color=BrandColors.TEXT_SECONDARY,
            size=16,
            dpr=self.devicePixelRatioF(),
        )
        if not chevron.isNull():
            self._chevron_label.setPixmap(chevron)
        layout.addWidget(self._chevron_label, 0, Qt.AlignVCenter)

        self._refresh_display()

    def set_providers(self, providers: Iterable[DriverProvider]) -> None:
        normalized: list[DriverProvider] = []
        seen: set[DriverProvider] = set()
        for provider in providers or []:
            if provider is None or provider in seen:
                continue
            normalized.append(provider)
            seen.add(provider)
        self._providers = normalized
        self._selected = {provider for provider in self._selected if provider in seen}
        self._counts = {
            provider: self._clamp_count(self._counts.get(provider, 1))
            for provider in normalized
        }
        if self._current_provider in seen:
            self._selected.add(self._current_provider)
        self._refresh_display()
        self._sync_popup_state()

    def set_current_provider(self, provider: DriverProvider | None) -> None:
        self._current_provider = provider if provider in self._providers else None
        if self._current_provider is not None:
            self._selected.add(self._current_provider)
        self._refresh_display()
        self._sync_popup_state()

    def set_full_mode(self, full_mode: bool) -> None:
        self._full_mode = bool(full_mode)
        self._refresh_display()
        self._sync_popup_state()

    def set_state(
        self,
        *,
        selected: Iterable[DriverProvider],
        counts: dict[DriverProvider, int],
    ) -> None:
        provider_set = set(self._providers)
        self._selected = {provider for provider in selected or [] if provider in provider_set}
        if self._current_provider is not None:
            self._selected.add(self._current_provider)
        self._counts = {
            provider: self._clamp_count(counts.get(provider, self._counts.get(provider, 1)))
            for provider in self._providers
        }
        self._refresh_display()
        self._sync_popup_state()

    def selected_providers(self) -> list[DriverProvider]:
        if self._current_provider is not None:
            self._selected.add(self._current_provider)
        return [provider for provider in self._providers if provider in self._selected]

    def instance_counts(self) -> dict[DriverProvider, int]:
        return {
            provider: self._clamp_count(self._counts.get(provider, 1))
            for provider in self._providers
        }

    def _clamp_count(self, value) -> int:
        try:
            count = int(value)
        except (TypeError, ValueError):
            count = 1
        return max(1, min(self._max_instances, count))

    def _summary_text(self) -> str:
        selected = self.selected_providers()
        count = len(selected)
        if count <= 0:
            return "Select providers"

        if self._full_mode:
            lanes = sum(self._clamp_count(self._counts.get(provider, 1)) for provider in selected)
            provider_label = "provider" if count == 1 else "providers"
            lane_label = "lane" if lanes == 1 else "lanes"
            return f"{count} {provider_label}, {lanes} {lane_label}"

        provider_label = "provider" if count == 1 else "providers"
        return f"{count} {provider_label} selected"

    def _refresh_display(self) -> None:
        count = len(self.selected_providers())
        self._text_label.setText(self._summary_text())
        self._text_label.setStyleSheet(
            f"""
            color: {BrandColors.TEXT_PRIMARY if count else BrandColors.TEXT_SECONDARY};
            background-color: transparent;
            font-size: {BrandColors.FONT_SIZE_REGULAR};
            font-family: {BrandColors.FONT_FAMILY};
            font-weight: 500;
            """
        )

        pixmap = IconUtils.get_pixmap(
            "circle-gauge.svg",
            color=BrandColors.TEXT_PRIMARY if count else BrandColors.TEXT_SECONDARY,
            size=16,
            dpr=self.devicePixelRatioF(),
            subdir="sidebar",
        )
        if not pixmap.isNull():
            self._icon_label.setPixmap(pixmap)
        else:
            self._icon_label.clear()

    def _provider_icon_file(self, provider: DriverProvider | None) -> str | None:
        return {
            DriverProvider.DEEPSEEK: "providers/deepseek.svg",
            DriverProvider.GLM_CHAT: "providers/zai.svg",
            DriverProvider.MOONSHOT: "providers/moonshot.svg",
            DriverProvider.QWEN_LM: "providers/qwen.svg",
            DriverProvider.PERPLEXITY: "providers/perplexity.svg",
            DriverProvider.HUGGINGCHAT: "providers/huggingface.svg",
            DriverProvider.AI_STUDIO: "providers/aistudio.svg",
            DriverProvider.MIMO: "providers/xiaomi.svg",
        }.get(provider)

    def _ensure_popup(self) -> _RuntimeProviderLanePopup:
        if self._popup is None:
            self._popup = _RuntimeProviderLanePopup(self, max_instances=self._max_instances)
            self._popup.stateChanged.connect(self._on_popup_state_changed)
        return self._popup

    def _sync_popup_state(self) -> None:
        if self._popup is None:
            return
        self._popup.set_state(
            providers=self._providers,
            selected=self.selected_providers(),
            counts=self.instance_counts(),
            current_provider=self._current_provider,
            full_mode=self._full_mode,
            icon_for_provider=self._provider_icon_file,
        )

    def mouseReleaseEvent(self, event) -> None:
        if self._consume_release:
            self._consume_release = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self._consume_release = True
            self.toggle_popup()
            event.accept()
            return
        super().mousePressEvent(event)

    def toggle_popup(self) -> None:
        popup = self._ensure_popup()
        if popup.isVisible():
            popup.animate_hide()
            return

        self._sync_popup_state()
        popup_width = max(self.width(), 330)
        visible_rows = max(3, min(max(len(self._providers), 0), 6))
        popup_height = 64 + (visible_rows * 54)
        popup.resize(popup_width, min(420, max(232, popup_height)))
        popup_pos = self.mapToGlobal(QPoint(0, self.height() + 6))

        app = QApplication.instance()
        if app is not None:
            screen = app.screenAt(popup_pos) or app.primaryScreen()
            if screen is not None:
                available = screen.availableGeometry()
                if popup_pos.x() + popup_width > available.right():
                    popup_pos.setX(max(available.left(), available.right() - popup_width))
                if popup_pos.y() + popup.height() > available.bottom():
                    popup_pos.setY(max(available.top(), self.mapToGlobal(QPoint(0, -popup.height() - 6)).y()))

        popup.animate_show(popup_pos)

    def _on_popup_state_changed(self, selected_values, count_values) -> None:
        provider_set = set(self._providers)
        selected: set[DriverProvider] = set()
        for value in selected_values or []:
            provider = DriverProvider.from_setting(value)
            if provider in provider_set:
                selected.add(provider)
        if self._current_provider is not None:
            selected.add(self._current_provider)

        counts: dict[DriverProvider, int] = {}
        if isinstance(count_values, dict):
            for value, count in count_values.items():
                provider = DriverProvider.from_setting(value)
                if provider in provider_set:
                    counts[provider] = self._clamp_count(count)

        self._selected = selected
        self._counts.update(counts)
        self._refresh_display()
        self.stateChanged.emit()
