from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QEvent, Qt, Signal, QSize
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from drivers.providers import DriverProvider
from ece.manager import EceManager
from ece.models import CredentialPair
from ui.core.brand import BrandColors
from ui.core.icons import IconType, IconUtils
from ui.widgets.components import StyledLineEdit
from ui.widgets.icon_option_menu import IconOptionMenu, IconOptionMenuItem
from utils.logger import Logger


@dataclass(frozen=True)
class _ProviderEntry:
    label: str
    provider: DriverProvider


class _CredentialRow(QWidget):
    changed = Signal()
    deleteRequested = Signal()
    pinRequested = Signal()
    unpinRequested = Signal()
    disableRequested = Signal()
    enableRequested = Signal()

    def __init__(self, number: int, pair: Optional[CredentialPair] = None, parent=None) -> None:
        super().__init__(parent)
        self._pinned = bool(getattr(pair, "pinned", False))
        self._disabled = bool(getattr(pair, "disabled", False))
        if self._disabled:
            self._pinned = False
        self._menu_toggle_suppressed = False
        self.setStyleSheet("background-color: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

        number_host = QWidget()
        number_host.setFixedWidth(22)
        number_stack = QStackedLayout(number_host)
        number_stack.setContentsMargins(0, 0, 0, 0)
        number_stack.setStackingMode(QStackedLayout.StackOne)

        self.number_label = QLabel(str(number))
        self.number_label.setFixedSize(22, 22)
        self.number_label.setAlignment(Qt.AlignCenter)
        self.number_label.setStyleSheet(
            f"color: {BrandColors.TEXT_DISABLED}; font-size: {BrandColors.FONT_SIZE_SMALL};"
        )
        number_stack.addWidget(self.number_label)

        self.pin_badge = QLabel()
        self.pin_badge.setFixedSize(22, 22)
        self.pin_badge.setAlignment(Qt.AlignCenter)
        self.pin_badge.setStyleSheet(
            f"""
            background-color: {BrandColors.SUCCESS};
            border-radius: 6px;
            """
        )
        pin_pixmap = IconUtils.get_pixmap(
            "pin.svg",
            color="#1d5a17",
            size=12,
            dpr=self.devicePixelRatioF(),
        )
        if not pin_pixmap.isNull():
            self.pin_badge.setPixmap(pin_pixmap)
        number_stack.addWidget(self.pin_badge)

        self.disabled_badge = QLabel()
        self.disabled_badge.setFixedSize(22, 22)
        self.disabled_badge.setAlignment(Qt.AlignCenter)
        self.disabled_badge.setStyleSheet(
            f"""
            background-color: {BrandColors.WARNING};
            border-radius: 6px;
            """
        )
        disabled_pixmap = IconUtils.get_pixmap(
            "flag-off.svg",
            color="#3b2a00",
            size=12,
            dpr=self.devicePixelRatioF(),
        )
        if not disabled_pixmap.isNull():
            self.disabled_badge.setPixmap(disabled_pixmap)
        number_stack.addWidget(self.disabled_badge)

        self._number_stack = number_stack
        layout.addWidget(number_host, 0, Qt.AlignVCenter)

        self.email_input = StyledLineEdit()
        self.email_input.setPlaceholderText("Email")
        self.email_input.setText(pair.email if pair else "")
        self.email_input.textChanged.connect(lambda *_: self.changed.emit())
        layout.addWidget(self.email_input, 1)

        self.password_input = StyledLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setText(pair.password if pair else "")
        self.password_input.textChanged.connect(lambda *_: self.changed.emit())
        layout.addWidget(self.password_input, 1)

        self.more_button = QPushButton()
        self.more_button.setCursor(Qt.PointingHandCursor)
        self.more_button.setFixedSize(30, 30)
        self.more_button.setIconSize(QSize(14, 14))
        self.more_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {BrandColors.INPUT_BORDER};
                border-radius: 6px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {BrandColors.ITEM_HOVER};
                border: 1px solid {BrandColors.CATEGORY_ACTIVE_BORDER};
            }}
            """
        )
        self.more_button.installEventFilter(self)
        self._refresh_more_button_icon(hovered=False)
        self.more_button.pressed.connect(self._handle_more_button_pressed)
        self.more_button.clicked.connect(self._toggle_action_menu)
        layout.addWidget(self.more_button, 0)

        self._action_menu = IconOptionMenu(self.more_button)
        self._action_menu.actionTriggered.connect(self._handle_action_triggered)

        self._sync_index_display()

    def set_number(self, number: int) -> None:
        self.number_label.setText(str(int(number)))
        self._sync_index_display()

    def is_pinned(self) -> bool:
        return self._pinned

    def set_pinned(self, pinned: bool) -> None:
        self._pinned = bool(pinned) and not self._disabled
        self._sync_index_display()

    def is_disabled(self) -> bool:
        return self._disabled

    def set_disabled(self, disabled: bool) -> None:
        self._disabled = bool(disabled)
        if self._disabled:
            self._pinned = False
        self._sync_index_display()

    def set_dimmed(self, dimmed: bool) -> None:
        if self._disabled:
            self._opacity_effect.setOpacity(0.42)
        else:
            self._opacity_effect.setOpacity(0.58 if dimmed else 1.0)

    def get_pair(self) -> CredentialPair:
        return CredentialPair(
            email=str(self.email_input.text() or ""),
            password=str(self.password_input.text() or ""),
            pinned=self._pinned,
            disabled=self._disabled,
        )

    def close_action_menu(self) -> None:
        if self._action_menu.isVisible():
            self._action_menu.animate_hide()

    def eventFilter(self, obj, event):
        if obj is self.more_button:
            if event.type() in {QEvent.Enter, QEvent.HoverEnter, QEvent.FocusIn}:
                self._refresh_more_button_icon(hovered=True)
            elif event.type() in {QEvent.Leave, QEvent.HoverLeave, QEvent.FocusOut}:
                self._refresh_more_button_icon(hovered=False)
        return super().eventFilter(obj, event)

    def _refresh_more_button_icon(self, *, hovered: bool) -> None:
        IconUtils.apply_icon(
            self.more_button,
            "ellipsis.svg",
            BrandColors.ACCENT if hovered else BrandColors.TEXT_PRIMARY,
            size=14,
            include_disabled=True,
        )

    def _sync_index_display(self) -> None:
        if self._disabled:
            self._number_stack.setCurrentWidget(self.disabled_badge)
        elif self._pinned:
            self._number_stack.setCurrentWidget(self.pin_badge)
        else:
            self._number_stack.setCurrentWidget(self.number_label)

    def _handle_more_button_pressed(self) -> None:
        self._menu_toggle_suppressed = False
        if self._action_menu.isVisible():
            self._menu_toggle_suppressed = True
            self._action_menu.animate_hide()

    def _toggle_action_menu(self) -> None:
        if self._menu_toggle_suppressed:
            self._menu_toggle_suppressed = False
            return
        self._action_menu.set_items(
            [
                IconOptionMenuItem(
                    key="pin",
                    label="Unpin" if self._pinned else "Pin",
                    icon_file="pin-off.svg" if self._pinned else "pin.svg",
                ),
                IconOptionMenuItem(
                    key="toggle_disabled",
                    label="Enable" if self._disabled else "Disable",
                    icon_file="flag.svg" if self._disabled else "flag-off.svg",
                    warning=not self._disabled,
                ),
                IconOptionMenuItem(
                    key="delete",
                    label="Delete",
                    icon_file="x.svg",
                    danger=True,
                ),
            ]
        )
        self._action_menu.popup_for(self.more_button)

    def _handle_action_triggered(self, action_key: str) -> None:
        if action_key == "delete":
            self.deleteRequested.emit()
            return
        if action_key == "toggle_disabled":
            if self._disabled:
                self.enableRequested.emit()
            else:
                self.disableRequested.emit()
            return
        if self._disabled:
            return
        if self._pinned:
            self.unpinRequested.emit()
            return
        self.pinRequested.emit()


class _ProviderPage(QWidget):
    changed = Signal()

    def __init__(self, provider_label: str, parent=None) -> None:
        super().__init__(parent)
        self._rows: List[_CredentialRow] = []
        self._pinned_row: _CredentialRow | None = None

        self.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(provider_label)
        title.setStyleSheet(
            f"""
            font-size: {BrandColors.FONT_SIZE_TITLE};
            font-weight: 700;
            color: {BrandColors.TEXT_PRIMARY};
            background-color: transparent;
            """
        )
        layout.addWidget(title, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet(
            f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 12px;
                margin: 0px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: #555555;
                min-height: 20px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #666666;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            """
        )

        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(8)
        self._content_layout.setAlignment(Qt.AlignTop)

        self.placeholder = QLabel("No credential pairs yet. Click Add New to add one.")
        self.placeholder.setWordWrap(True)
        self.placeholder.setStyleSheet(
            f"color: {BrandColors.TEXT_SECONDARY}; font-size: {BrandColors.FONT_SIZE_REGULAR}; padding: 10px 0;"
        )
        self._content_layout.addWidget(self.placeholder, 0)

        self.add_button = QPushButton("Add New")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setIconSize(QSize(14, 14))
        self.add_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.add_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {BrandColors.ACCENT};
                border: 1px solid {BrandColors.ACCENT};
                padding: 10px 14px;
                border-radius: 6px;
                font-size: {BrandColors.FONT_SIZE_REGULAR};
                font-weight: 700;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: {BrandColors.ITEM_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {BrandColors.SIDEBAR_BG};
            }}
            """
        )
        IconUtils.apply_icon(self.add_button, IconType.PLUS, BrandColors.ACCENT, size=14)
        self.add_button.clicked.connect(self.add_row)
        self._content_layout.addWidget(self.add_button, 0)

        self.scroll.setWidget(content)
        layout.addWidget(self.scroll, 1)

    def set_pairs(self, pairs: List[CredentialPair]) -> None:
        # Clear existing rows.
        for row in self._rows:
            self._content_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self._rows = []
        self._pinned_row = None

        for idx, pair in enumerate(pairs, start=1):
            self._insert_row(idx, pair)

        self._sync_pinned_state()
        self._sync_placeholder()

    def _insert_row(self, number: int, pair: Optional[CredentialPair] = None) -> None:
        row = _CredentialRow(number=number, pair=pair, parent=self)
        row.changed.connect(self.changed.emit)
        row.deleteRequested.connect(lambda r=row: self._delete_row(r))
        row.pinRequested.connect(lambda r=row: self._pin_row(r))
        row.unpinRequested.connect(lambda r=row: self._unpin_row(r))
        row.disableRequested.connect(lambda r=row: self._disable_row(r))
        row.enableRequested.connect(lambda r=row: self._enable_row(r))

        if row.is_pinned() and not row.is_disabled():
            if self._pinned_row is None:
                self._pinned_row = row
            else:
                row.set_pinned(False)

        # Insert above the Add New button (which is always last in the content layout).
        insert_at = max(0, self._content_layout.indexOf(self.add_button))
        self._content_layout.insertWidget(insert_at, row)
        self._rows.append(row)
        self.changed.emit()
        self._sync_pinned_state()
        self._sync_placeholder()

    def add_row(self) -> None:
        self._insert_row(len(self._rows) + 1, None)

    def _delete_row(self, row: _CredentialRow) -> None:
        if row not in self._rows:
            return
        row.close_action_menu()
        self._content_layout.removeWidget(row)
        self._rows.remove(row)
        if self._pinned_row is row:
            self._pinned_row = None
        row.setParent(None)
        row.deleteLater()
        self._renumber()
        self.changed.emit()
        self._sync_pinned_state()
        self._sync_placeholder()

    def _pin_row(self, row: _CredentialRow) -> None:
        if row not in self._rows:
            return
        if row.is_disabled():
            return
        if self._pinned_row is row and row.is_pinned():
            return

        if self._pinned_row is not None:
            self._pinned_row.set_pinned(False)

        row.set_pinned(True)
        self._pinned_row = row
        self.changed.emit()
        self._sync_pinned_state()

    def _unpin_row(self, row: _CredentialRow) -> None:
        if row not in self._rows or (not row.is_pinned()):
            return
        row.set_pinned(False)
        if self._pinned_row is row:
            self._pinned_row = None
        self.changed.emit()
        self._sync_pinned_state()

    def _disable_row(self, row: _CredentialRow) -> None:
        if row not in self._rows or row.is_disabled():
            return
        if self._pinned_row is row:
            self._pinned_row = None
        row.set_disabled(True)
        self.changed.emit()
        self._sync_pinned_state()

    def _enable_row(self, row: _CredentialRow) -> None:
        if row not in self._rows or not row.is_disabled():
            return
        row.set_disabled(False)
        self.changed.emit()
        self._sync_pinned_state()

    def _renumber(self) -> None:
        for idx, row in enumerate(self._rows, start=1):
            row.set_number(idx)

    def _sync_pinned_state(self) -> None:
        has_pinned_row = self._pinned_row is not None and self._pinned_row in self._rows
        for row in self._rows:
            row.set_dimmed(row.is_disabled() or (has_pinned_row and row is not self._pinned_row))

    def _sync_placeholder(self) -> None:
        self.placeholder.setVisible(len(self._rows) == 0)

    def get_pairs(self) -> List[CredentialPair]:
        return [row.get_pair() for row in self._rows]


class CredentialManagerDialog(QDialog):
    saved = Signal()

    def __init__(self, config_manager, parent=None) -> None:
        super().__init__(parent)
        self._config_manager = config_manager
        self._ece = EceManager(getattr(config_manager, "config_dir", "config_data"))

        self._unsaved_changes = False
        self._loaded_snapshot: Dict[str, List[Tuple[str, str, bool, bool]]] = {}

        self.setWindowTitle("Credential Manager")
        self.setModal(True)
        self.resize(860, 620)
        self.setStyleSheet(f"background-color: {BrandColors.WINDOW_BG}; color: {BrandColors.TEXT_PRIMARY};")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 16)
        root_layout.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        title = QLabel("Credential Manager")
        title.setStyleSheet(
            "font-size: 22px; font-weight: 700; background-color: transparent;"
        )
        header.addWidget(title, 1)

        self.unsaved_label = QLabel("Unsaved changes")
        self.unsaved_label.setVisible(False)
        self.unsaved_label.setStyleSheet(
            f"color: {BrandColors.WARNING}; font-size: {BrandColors.FONT_SIZE_SMALL}; font-weight: 700;"
        )
        header.addWidget(self.unsaved_label, 0, Qt.AlignRight)

        root_layout.addLayout(header)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(14)
        root_layout.addLayout(content_row, 1)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(220)
        self.sidebar.setSpacing(4)
        self.sidebar.setIconSize(QSize(18, 18))
        self.sidebar.setStyleSheet(
            f"""
            QListWidget {{
                background-color: {BrandColors.SIDEBAR_BG};
                border: 1px solid {BrandColors.INPUT_BORDER};
                outline: none;
                padding: 8px;
                border-radius: 10px;
                font-size: {BrandColors.FONT_SIZE_REGULAR};
                font-family: {BrandColors.FONT_FAMILY};
            }}
            QListWidget::item {{
                padding: 10px 12px;
                color: {BrandColors.TEXT_SECONDARY};
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
            }}
            QListWidget::item:selected {{
                background-color: {BrandColors.CATEGORY_ACTIVE_BG};
                color: {BrandColors.TEXT_PRIMARY};
                border: 1px solid {BrandColors.CATEGORY_ACTIVE_BORDER};
                font-weight: 600;
            }}
            QListWidget::item:selected:hover {{
                background-color: {BrandColors.CATEGORY_ACTIVE_BG};
                color: {BrandColors.TEXT_PRIMARY};
                border: 1px solid {BrandColors.CATEGORY_ACTIVE_BORDER};
            }}
            QListWidget::item:hover {{
                background-color: {BrandColors.ITEM_HOVER};
                color: {BrandColors.TEXT_PRIMARY};
            }}
            """
        )
        content_row.addWidget(self.sidebar, 0)

        self.pages = QStackedWidget()
        self.pages.setStyleSheet(
            f"""
            QStackedWidget {{
                background-color: {BrandColors.SIDEBAR_BG};
                border: 1px solid {BrandColors.INPUT_BORDER};
                border-radius: 10px;
            }}
            """
        )
        content_row.addWidget(self.pages, 1)

        self._provider_entries: List[_ProviderEntry] = [
            _ProviderEntry(label="DeepSeek", provider=DriverProvider.DEEPSEEK),
            _ProviderEntry(label="GLM", provider=DriverProvider.GLM_CHAT),
            _ProviderEntry(label="Moonshot", provider=DriverProvider.MOONSHOT),
            _ProviderEntry(label="QwenLM", provider=DriverProvider.QWEN_LM),
            _ProviderEntry(label="Perplexity", provider=DriverProvider.PERPLEXITY),
            _ProviderEntry(label="HuggingChat", provider=DriverProvider.HUGGINGCHAT),
            _ProviderEntry(label="AI Studio", provider=DriverProvider.AI_STUDIO),
            _ProviderEntry(label="Xiaomi MiMo", provider=DriverProvider.MIMO),
        ]

        provider_icon_map: Dict[DriverProvider, str] = {
            DriverProvider.DEEPSEEK: "providers/deepseek.svg",
            DriverProvider.GLM_CHAT: "providers/zai.svg",
            DriverProvider.MOONSHOT: "providers/moonshot.svg",
            DriverProvider.QWEN_LM: "providers/qwen.svg",
            DriverProvider.PERPLEXITY: "providers/perplexity.svg",
            DriverProvider.HUGGINGCHAT: "providers/huggingface.svg",
            DriverProvider.AI_STUDIO: "providers/aistudio.svg",
            DriverProvider.MIMO: "providers/xiaomi.svg",
        }

        initial_provider = DriverProvider.from_setting(
            self._config_manager.get_setting("providers_credentials", "provider")
        )
        initial_row = 0

        self._page_by_provider_key: Dict[str, _ProviderPage] = {}
        for idx, entry in enumerate(self._provider_entries):
            item = QListWidgetItem(entry.label)
            item.setData(Qt.UserRole, entry.provider.value)

            icon_file = provider_icon_map.get(entry.provider)
            if icon_file:
                item.setData(Qt.UserRole + 1, icon_file)
                item.setIcon(self._get_sidebar_icon(icon_file, BrandColors.TEXT_SECONDARY, size=18))
            self.sidebar.addItem(item)

            page = _ProviderPage(entry.label)
            page.changed.connect(self._mark_dirty)
            self.pages.addWidget(page)
            self._page_by_provider_key[entry.provider.key] = page

        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sidebar.currentItemChanged.connect(self._on_sidebar_selection_changed)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {BrandColors.SIDEBAR_BG};
                color: {BrandColors.TEXT_PRIMARY};
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: {BrandColors.FONT_SIZE_REGULAR};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {BrandColors.ITEM_HOVER};
            }}
            """
        )
        IconUtils.apply_icon(self.cancel_button, IconType.CANCEL, BrandColors.TEXT_PRIMARY, size=16)
        self.cancel_button.setIconSize(QSize(16, 16))
        self.cancel_button.clicked.connect(self._on_cancel)
        bottom.addWidget(self.cancel_button)

        self.save_button = QPushButton("Save")
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {BrandColors.ACCENT};
                color: {BrandColors.TEXT_PRIMARY};
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: {BrandColors.FONT_SIZE_REGULAR};
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #4a80e0;
            }}
            """
        )
        IconUtils.apply_icon(self.save_button, IconType.CONFIRM, BrandColors.TEXT_PRIMARY, size=16)
        self.save_button.setIconSize(QSize(16, 16))
        self.save_button.clicked.connect(self._on_save)
        bottom.addWidget(self.save_button)

        root_layout.addLayout(bottom)

        try:
            from utils.account_migration import migrate_legacy_credentials_to_accounts

            migrate_legacy_credentials_to_accounts(self._config_manager)
        except Exception as exc:
            Logger.debug(f"Legacy credential import: skipped due to error: {exc}")

        self._load()
        for idx, entry in enumerate(self._provider_entries):
            if entry.provider == initial_provider:
                initial_row = idx
                break
        self.sidebar.setCurrentRow(initial_row)
        self._apply_sidebar_item_icon(self.sidebar.currentItem(), active=True)

    def _get_sidebar_icon(self, icon_file: str, color: str, size: int = 18):
        use_sidebar_subdir = ("/" not in icon_file) and ("\\" not in icon_file)
        return IconUtils.get_icon(
            icon_file,
            color=color,
            size=size,
            widget=self.sidebar,
            subdir="sidebar" if use_sidebar_subdir else None,
        )

    def _apply_sidebar_item_icon(self, item: Optional[QListWidgetItem], *, active: bool) -> None:
        if not item:
            return

        icon_file = item.data(Qt.UserRole + 1)
        if not icon_file:
            return

        color = BrandColors.TEXT_PRIMARY if active else BrandColors.TEXT_SECONDARY
        item.setIcon(self._get_sidebar_icon(icon_file, color, size=18))

    def _on_sidebar_selection_changed(
        self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]
    ) -> None:
        self._apply_sidebar_item_icon(previous, active=False)
        self._apply_sidebar_item_icon(current, active=True)

    def _snapshot_from_pages(self) -> Dict[str, List[Tuple[str, str, bool, bool]]]:
        snap: Dict[str, List[Tuple[str, str, bool, bool]]] = {}
        for entry in self._provider_entries:
            page = self._page_by_provider_key.get(entry.provider.key)
            if not page:
                continue
            snap[entry.provider.key] = [
                (p.email, p.password, bool(p.pinned), bool(getattr(p, "disabled", False)))
                for p in page.get_pairs()
            ]
        return snap

    def _load(self) -> None:
        for entry in self._provider_entries:
            pairs = self._ece.get_provider_pairs(entry.provider)
            page = self._page_by_provider_key.get(entry.provider.key)
            if page:
                page.set_pairs(pairs)

        self._loaded_snapshot = self._snapshot_from_pages()
        self._set_dirty(False)

    def _mark_dirty(self) -> None:
        self._set_dirty(self._snapshot_from_pages() != self._loaded_snapshot)

    def _set_dirty(self, dirty: bool) -> None:
        dirty = bool(dirty)
        self._unsaved_changes = dirty
        self.unsaved_label.setVisible(dirty)

    def _confirm_discard(self) -> bool:
        if not self._unsaved_changes:
            return True

        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _on_cancel(self) -> None:
        if not self._confirm_discard():
            return
        self.reject()

    def closeEvent(self, event) -> None:
        if not self._confirm_discard():
            event.ignore()
            return
        event.accept()

    def _collect_provider_pairs(self) -> Dict[DriverProvider, List[CredentialPair]]:
        collected: Dict[DriverProvider, List[CredentialPair]] = {}
        for entry in self._provider_entries:
            page = self._page_by_provider_key.get(entry.provider.key)
            collected[entry.provider] = page.get_pairs() if page else []
        return collected

    def _on_save(self) -> None:
        collected = self._collect_provider_pairs()

        all_errors: List[str] = []
        for provider, pairs in collected.items():
            ok, errors = self._ece.set_provider_pairs(provider, pairs)
            if not ok:
                if errors:
                    all_errors.extend([f"{provider.value}: {err}" for err in errors])
                else:
                    all_errors.append(f"{provider.value}: failed to save.")

        if all_errors:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please fix the following issues:\n\n" + "\n".join(all_errors),
            )
            return

        # Best-effort usage cleanup
        for provider in collected.keys():
            try:
                self._ece.prune_usage(provider)
            except Exception:
                pass

        self._loaded_snapshot = self._snapshot_from_pages()
        self._set_dirty(False)
        self.saved.emit()
        self.accept()
