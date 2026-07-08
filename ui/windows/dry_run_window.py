from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import (
    QRegularExpression,
    QRect,
    QSize,
    Qt,
    Signal,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextOption,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.core.brand import BrandColors
from ui.core.icons import IconType, IconUtils
from ui.widgets.smooth_scroll_area import SmoothScrollController


class JsonSyntaxHighlighter(QSyntaxHighlighter):
    """Minimal JSON highlighter. Yes I stole Vscode colors."""

    def __init__(self, document):
        super().__init__(document)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        punctuation = self._format("#d4d4d4")
        number = self._format("#b5cea8")
        literal = self._format("#569cd6", bold=True)
        string = self._format("#ce9178")
        key = self._format("#9cdcfe")

        self._rules.extend(
            [
                (QRegularExpression(r"[{}\[\]:,]"), punctuation),
                (
                    QRegularExpression(
                        r"\b-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?\b"
                    ),
                    number,
                ),
                (QRegularExpression(r"\b(?:true|false|null)\b"), literal),
                (QRegularExpression(r'"(?:\\.|[^"\\])*"'), string),
                (QRegularExpression(r'"(?:\\.|[^"\\])*"(?=\s*:)'), key),
            ]
        )

    @staticmethod
    def _format(color: str, *, bold: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        return fmt

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class _LineNumberArea(QWidget):
    def __init__(self, editor: "_JsonEditor"):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
        self._editor.line_number_area_paint_event(event)


class _SmoothTextEditor(QPlainTextEdit):
    SCROLL_STEP_PX = (12, 36)

    def __init__(self, parent=None, *, shift_wheel_horizontal: bool = False):
        super().__init__(parent)
        self._shift_wheel_horizontal = bool(shift_wheel_horizontal)
        self._smooth_scroll = SmoothScrollController(
            self,
            self,
            scroll_step_px=self.SCROLL_STEP_PX,
        )

    def wheelEvent(self, event) -> None:
        if self._smooth_scroll.handle_wheel_event(
            event,
            shift_wheel_horizontal=self._shift_wheel_horizontal,
        ):
            event.accept()
            return
        super().wheelEvent(event)


class _JsonEditor(_SmoothTextEditor):
    def __init__(self, parent=None):
        super().__init__(parent, shift_wheel_horizontal=True)
        self._line_number_area = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self._configure_editor(wrap=False)
        self._highlighter = JsonSyntaxHighlighter(self.document())
        self._update_line_number_area_width()

    def _configure_editor(self, *, wrap: bool) -> None:
        self.setReadOnly(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth if wrap else QPlainTextEdit.NoWrap)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.document().setDocumentMargin(12)
        font = QFont(BrandColors.FONT_FAMILY)
        font.setPointSize(11)
        self.setFont(font)
        self.setStyleSheet(_editor_stylesheet())

    def line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 18 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_area_width(self) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        contents_rect = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(
                contents_rect.left(),
                contents_rect.top(),
                self.line_number_area_width(),
                contents_rect.height(),
            )
        )

    def line_number_area_paint_event(self, event) -> None:
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor("#202020"))
        painter.setPen(QColor("#858585"))
        painter.setFont(self.font())

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 8,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    number,
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1


class _FormattedTextEditor(_SmoothTextEditor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.document().setDocumentMargin(16)
        font = QFont(BrandColors.FONT_FAMILY)
        font.setPointSize(12)
        self.setFont(font)
        self.setStyleSheet(_editor_stylesheet())


class DryRunWindow(QMainWindow):
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._allow_close_without_stop = False
        self._last_raw_text = ""
        self._last_formatted_text = ""

        self.setWindowTitle("Dry Run Display")
        self.resize(1180, 720)
        self.setMinimumSize(860, 520)
        self.setStyleSheet(f"background-color: {BrandColors.WINDOW_BG};")

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 26, 28, 24)
        root.setSpacing(18)

        header = self._build_header()
        root.addWidget(header)
        root.addSpacing(8)

        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(18)

        self.raw_editor = _JsonEditor()
        self.formatted_editor = _FormattedTextEditor()
        content_layout.addWidget(self._build_panel("Raw Request JSON", self.raw_editor), 1)

        arrow = QLabel()
        arrow.setAlignment(Qt.AlignCenter)
        arrow.setFixedWidth(42)
        arrow.setStyleSheet("background-color: transparent;")
        pixmap = IconUtils.get_pixmap(
            "arrow-right.svg",
            color=BrandColors.TEXT_SECONDARY,
            size=34,
            dpr=float(self.devicePixelRatioF()),
        )
        if not pixmap.isNull():
            arrow.setPixmap(pixmap)
        else:
            arrow.setText("->")
            arrow.setStyleSheet(
                f"color: {BrandColors.TEXT_SECONDARY}; font-size: 28px; background: transparent;"
            )
        content_layout.addWidget(arrow, 0, Qt.AlignVCenter)

        content_layout.addWidget(
            self._build_panel("Formatted Generation", self.formatted_editor),
            1,
        )
        root.addWidget(content, 1)

        buttons = self._build_buttons()
        root.addWidget(buttons)

        self.show_waiting()

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Dry Run Display")
        title.setStyleSheet(
            f"""
            color: {BrandColors.TEXT_PRIMARY};
            font-size: 28px;
            font-weight: 800;
            background-color: transparent;
            """
        )
        layout.addWidget(title)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            f"""
            color: {BrandColors.TEXT_SOFT};
            font-size: {BrandColors.FONT_SIZE_LARGE};
            background-color: transparent;
            """
        )
        layout.addWidget(self.status_label)
        return header

    def _build_panel(self, title: str, editor: QPlainTextEdit) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        label = QLabel(title)
        label.setStyleSheet(
            f"""
            color: {BrandColors.TEXT_PRIMARY};
            font-size: {BrandColors.FONT_SIZE_XLARGE};
            font-weight: 700;
            background-color: transparent;
            """
        )
        layout.addWidget(label)

        frame = QFrame()
        frame.setObjectName("dryRunEditorFrame")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        frame.setStyleSheet(
            f"""
            QFrame#dryRunEditorFrame {{
                background-color: #202020;
                border: 1px solid {BrandColors.INPUT_BORDER};
                border-radius: 8px;
            }}
            """
        )
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(1, 1, 1, 1)
        frame_layout.setSpacing(0)
        frame_layout.addWidget(editor)
        layout.addWidget(frame, 1)
        return panel

    def _build_buttons(self) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background-color: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        self.copy_raw_btn = self._make_button("Copy Raw", "copy.svg", accent=True)
        self.copy_raw_btn.clicked.connect(lambda: self._copy_text(self._last_raw_text, self.copy_raw_btn))
        layout.addWidget(self.copy_raw_btn, 1)

        close_btn = self._make_button("Close", IconType.CANCEL, accent=False)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, 1)

        self.copy_formatted_btn = self._make_button("Copy Formatted", "copy.svg", accent=True)
        self.copy_formatted_btn.clicked.connect(
            lambda: self._copy_text(self._last_formatted_text, self.copy_formatted_btn)
        )
        layout.addWidget(self.copy_formatted_btn, 1)
        return row

    def _make_button(self, text: str, icon: IconType | str, *, accent: bool) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumHeight(46)
        button.setIconSize(QSize(18, 18))
        if accent:
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {BrandColors.ACCENT};
                    color: {BrandColors.TEXT_PRIMARY};
                    border: 1px solid {BrandColors.ACCENT};
                    border-radius: 6px;
                    padding: 10px 18px;
                    font-size: {BrandColors.FONT_SIZE_LARGE};
                    font-weight: 800;
                }}
                QPushButton:hover {{
                    background-color: #6aa2ff;
                    border-color: #6aa2ff;
                }}
                QPushButton:pressed {{
                    background-color: #4077d9;
                    border-color: #4077d9;
                }}
                QPushButton:disabled {{
                    background-color: {BrandColors.SIDEBAR_BG};
                    color: {BrandColors.TEXT_DISABLED};
                    border-color: {BrandColors.INPUT_BORDER};
                }}
                """
            )
        else:
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: transparent;
                    color: {BrandColors.TEXT_PRIMARY};
                    border: 1px solid {BrandColors.INPUT_BORDER};
                    border-radius: 6px;
                    padding: 10px 18px;
                    font-size: {BrandColors.FONT_SIZE_LARGE};
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {BrandColors.ITEM_HOVER};
                    border-color: {BrandColors.ACCENT};
                }}
                QPushButton:pressed {{
                    background-color: {BrandColors.SIDEBAR_BG};
                }}
                """
            )
        IconUtils.apply_icon(button, icon, BrandColors.TEXT_PRIMARY, size=18, include_disabled=True)
        return button

    def show_waiting(self) -> None:
        self._last_raw_text = ""
        self._last_formatted_text = ""
        self.raw_editor.clear()
        self.formatted_editor.clear()
        self.raw_editor.setPlaceholderText("Send a request to show the raw request JSON here.")
        self.formatted_editor.setPlaceholderText("The formatted generation will appear after capture.")
        self.status_label.setText(
            "Dry Run Mode is active. Send a request and the request JSON plus formatted generation will appear here."
        )
        self.copy_raw_btn.setEnabled(False)
        self.copy_formatted_btn.setEnabled(False)

    def set_capture(self, capture: Any) -> None:
        raw_text = str(getattr(capture, "raw_json", "") or "")
        formatted_text = str(getattr(capture, "formatted_text", "") or "")
        self._last_raw_text = raw_text
        self._last_formatted_text = formatted_text
        self.raw_editor.setPlainText(raw_text)
        self.formatted_editor.setPlainText(formatted_text)
        self.copy_raw_btn.setEnabled(bool(raw_text.strip()))
        self.copy_formatted_btn.setEnabled(bool(formatted_text.strip()))

        captured_at = float(getattr(capture, "captured_at", 0.0) or 0.0)
        when = datetime.fromtimestamp(captured_at).strftime("%H:%M:%S") if captured_at else "now"
        request_type = str(getattr(capture, "request_type", "") or "request")
        model = str(getattr(capture, "model", "") or "<empty>")
        self.status_label.setText(
            f"Captured {request_type} request for {model} at {when}. New requests replace this capture."
        )

    def _copy_text(self, text: str, button: QPushButton) -> None:
        if not text:
            return
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

        previous_text = button.text()
        button.setText("Copied")

        def restore_text() -> None:
            try:
                button.setText(previous_text)
            except RuntimeError:
                pass

        QTimer.singleShot(1100, restore_text)

    def present(self) -> None:
        self.show()
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def force_close(self) -> None:
        self._allow_close_without_stop = True
        self.close()

    def closeEvent(self, event) -> None:
        if not self._allow_close_without_stop:
            self.stop_requested.emit()
        event.accept()


def _editor_stylesheet() -> str:
    return f"""
    QPlainTextEdit {{
        background-color: #202020;
        color: {BrandColors.TEXT_PRIMARY};
        border: none;
        selection-background-color: {BrandColors.ACCENT};
        selection-color: {BrandColors.TEXT_PRIMARY};
    }}
    QPlainTextEdit:disabled {{
        color: {BrandColors.TEXT_DISABLED};
    }}
    QScrollBar:vertical {{
        background-color: #202020;
        width: 12px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background-color: #666666;
        border-radius: 5px;
        min-height: 28px;
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background-color: #202020;
        height: 12px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background-color: #666666;
        border-radius: 5px;
        min-width: 28px;
    }}
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    """
