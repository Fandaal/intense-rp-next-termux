from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from drivers.providers import provider_options
from ui.core.brand import BrandColors
from ui.core.icons import IconType, IconUtils


PROVIDER_ICON_MAP: dict[str, str] = {
    "DeepSeek": "providers/deepseek.svg",
    "GLM Chat": "providers/zai.svg",
    "Moonshot": "providers/moonshot.svg",
    "QwenLM": "providers/qwen.svg",
    "Perplexity": "providers/perplexity.svg",
    "HuggingChat": "providers/huggingface.svg",
    "Google AI Studio": "providers/aistudio.svg",
}

ALL_PROVIDERS: list[str] = provider_options()


class ProviderTile(QFrame):
    clicked = Signal(str)
    TILE_WIDTH = 136
    TILE_HEIGHT = 104

    def __init__(self, provider_name: str, parent=None):
        super().__init__(parent)
        self._provider_name = provider_name
        self.setAccessibleName(provider_name)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.setStyleSheet(f"""
            ProviderTile {{
                background-color: {BrandColors.SIDEBAR_BG};
                border-radius: 8px;
                border: 1px solid transparent;
            }}
            ProviderTile:hover {{
                background-color: {BrandColors.ITEM_HOVER};
                border: 1px solid {BrandColors.ACCENT};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(10, 16, 10, 12)
        layout.setSpacing(8)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("background-color: transparent;")
        icon_file = PROVIDER_ICON_MAP.get(provider_name)
        if icon_file:
            pixmap = IconUtils.get_pixmap(
                icon_file,
                color=BrandColors.TEXT_PRIMARY,
                size=36,
                dpr=self.devicePixelRatioF(),
            )
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label)

        text_label = QLabel(provider_name)
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setWordWrap(True)
        text_label.setStyleSheet(f"""
            font-size: {BrandColors.FONT_SIZE_SMALL};
            font-weight: 600;
            color: {BrandColors.TEXT_PRIMARY};
            background-color: transparent;
        """)
        layout.addWidget(text_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._provider_name)
        super().mousePressEvent(event)

    def sizeHint(self):
        return QSize(self.TILE_WIDTH, self.TILE_HEIGHT)

    def minimumSizeHint(self):
        return self.sizeHint()


class HotswapDialog(QDialog):
    """Small modal that lets the user pick one of the other providers."""

    def __init__(
        self,
        current_provider: str,
        parent=None,
        providers: list[str] | None = None,
    ):
        super().__init__(parent)
        self._selected: Optional[str] = None

        self.setWindowTitle("Hotswap Provider")
        self.setModal(True)
        self.setFixedWidth(500)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("hotswapCard")
        card.setStyleSheet(
            f"""
            QFrame#hotswapCard {{
                background-color: {BrandColors.WINDOW_BG};
                border: none;
            }}
            """
        )
        root_layout.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 16, 22, 18)
        layout.setSpacing(8)

        title = QLabel("Switch Provider")
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

        desc = QLabel(f"Currently using <b>{current_provider}</b>. Pick a provider to switch to:")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setTextFormat(Qt.RichText)
        desc.setStyleSheet(
            f"""
            font-size: {BrandColors.FONT_SIZE_REGULAR};
            color: {BrandColors.TEXT_SECONDARY};
            background-color: transparent;
            padding: 2px 4px;
            """
        )
        layout.addWidget(desc)

        provider_names = providers if providers is not None else ALL_PROVIDERS
        others = [p for p in provider_names if p != current_provider]
        tile_grid = QGridLayout()
        tile_grid.setContentsMargins(0, 0, 0, 0)
        tile_grid.setHorizontalSpacing(12)
        tile_grid.setVerticalSpacing(12)
        tile_grid.setAlignment(Qt.AlignCenter)

        columns = 3
        for index, provider_name in enumerate(others):
            tile = ProviderTile(provider_name, parent=card)
            tile.clicked.connect(self._pick)
            row = index // columns
            column = index % columns
            tile_grid.addWidget(tile, row, column)
        layout.addLayout(tile_grid)
        layout.addSpacing(24)

        # Cancel button
        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.setStyleSheet(
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
        IconUtils.apply_icon(cancel, IconType.CANCEL, BrandColors.TEXT_PRIMARY, size=14)
        cancel.setIconSize(QSize(14, 14))
        cancel.setMinimumWidth(210)
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel, 0, Qt.AlignCenter)

    def _pick(self, provider_name: str) -> None:
        self._selected = provider_name
        self.accept()

    @property
    def selected_provider(self) -> Optional[str]:
        return self._selected
