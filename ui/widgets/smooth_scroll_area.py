from PySide6.QtWidgets import QAbstractScrollArea, QScrollArea
from PySide6.QtCore import QObject, Qt, Property, QPropertyAnimation, QEasingCurve, QPoint


class SmoothScrollController(QObject):
    """Shared smooth wheel-scrolling helper for Qt scroll area widgets."""

    SCROLL_DURATION_MS = 350
    SCROLL_STEP_PX = 80  # base pixels per wheel notch (120 delta units)

    def __init__(
        self,
        scroll_area: QAbstractScrollArea,
        parent=None,
        *,
        scroll_step_px: int | tuple[int, int] | None = None,
        scroll_duration_ms: int | None = None,
    ):
        super().__init__(parent)
        self._scroll_area = scroll_area
        vertical_step_px, horizontal_step_px = self._normalize_scroll_steps(scroll_step_px)
        duration_ms = self.SCROLL_DURATION_MS if scroll_duration_ms is None else scroll_duration_ms
        self._vscroll_step_px = vertical_step_px
        self._hscroll_step_px = horizontal_step_px
        self._scroll_duration_ms = max(0, int(duration_ms))
        self._vscroll_animation = QPropertyAnimation(self, b"vscroll_pos")
        self._vscroll_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._vscroll_animation.setDuration(self._scroll_duration_ms)
        self._hscroll_animation = QPropertyAnimation(self, b"hscroll_pos")
        self._hscroll_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._hscroll_animation.setDuration(self._scroll_duration_ms)
        self._target_vscroll = 0
        self._target_hscroll = 0

    @classmethod
    def _normalize_scroll_steps(
        cls,
        scroll_step_px: int | tuple[int, int] | None,
    ) -> tuple[int, int]:
        if scroll_step_px is None:
            vertical_step_px = horizontal_step_px = cls.SCROLL_STEP_PX
        elif isinstance(scroll_step_px, tuple):
            if len(scroll_step_px) != 2:
                raise ValueError("scroll_step_px tuple must be (vertical_px, horizontal_px)")
            vertical_step_px, horizontal_step_px = scroll_step_px
        else:
            vertical_step_px = horizontal_step_px = scroll_step_px

        return max(1, int(vertical_step_px)), max(1, int(horizontal_step_px))

    def _scroll_bar(self, orientation: Qt.Orientation):
        if orientation == Qt.Horizontal:
            return self._scroll_area.horizontalScrollBar()
        return self._scroll_area.verticalScrollBar()

    def smooth_scroll_to(
        self,
        target_value: int,
        *,
        duration_ms: int | None = None,
        orientation: Qt.Orientation = Qt.Vertical,
    ) -> bool:
        scroll_bar = self._scroll_bar(orientation)
        target_value = int(target_value)
        target_value = max(scroll_bar.minimum(), min(target_value, scroll_bar.maximum()))

        start_value = int(scroll_bar.value())
        if start_value == target_value:
            return False

        if orientation == Qt.Horizontal:
            self._target_hscroll = target_value
            animation = self._hscroll_animation
        else:
            self._target_vscroll = target_value
            animation = self._vscroll_animation

        animation.stop()
        duration_ms = self._scroll_duration_ms if duration_ms is None else max(0, int(duration_ms))
        animation.setDuration(duration_ms)
        animation.setStartValue(start_value)
        animation.setEndValue(target_value)
        animation.start()
        return True

    def smooth_scroll_by_delta(
        self,
        delta: int,
        *,
        duration_ms: int | None = None,
        orientation: Qt.Orientation = Qt.Vertical,
    ) -> bool:
        if not delta:
            return False

        scroll_bar = self._scroll_bar(orientation)
        if scroll_bar.maximum() <= scroll_bar.minimum():
            return False

        if orientation == Qt.Horizontal:
            animation = self._hscroll_animation
            if animation.state() != QPropertyAnimation.Running:
                self._target_hscroll = int(scroll_bar.value())
            target = self._target_hscroll + int(delta)
            self._target_hscroll = max(scroll_bar.minimum(), min(target, scroll_bar.maximum()))
            target = self._target_hscroll
        else:
            animation = self._vscroll_animation
            if animation.state() != QPropertyAnimation.Running:
                self._target_vscroll = int(scroll_bar.value())
            target = self._target_vscroll + int(delta)
            self._target_vscroll = max(scroll_bar.minimum(), min(target, scroll_bar.maximum()))
            target = self._target_vscroll

        return self.smooth_scroll_to(
            target,
            duration_ms=duration_ms,
            orientation=orientation,
        )

    def handle_wheel_event(
        self,
        event,
        *,
        shift_wheel_horizontal: bool = False,
        duration_ms: int | None = None,
    ) -> bool:
        angle_delta = event.angleDelta()
        y_delta = int(angle_delta.y())
        x_delta = int(angle_delta.x())

        if shift_wheel_horizontal and (event.modifiers() & Qt.ShiftModifier):
            delta = x_delta if x_delta else y_delta
            pixels = -int(delta / 120.0 * self._hscroll_step_px)
            return self.smooth_scroll_by_delta(
                pixels,
                duration_ms=duration_ms,
                orientation=Qt.Horizontal,
            )

        if not y_delta:
            return False

        pixels = -int(y_delta / 120.0 * self._vscroll_step_px)
        return self.smooth_scroll_by_delta(
            pixels,
            duration_ms=duration_ms,
            orientation=Qt.Vertical,
        )

    def smooth_ensure_widget_visible(
        self,
        child_widget,
        *,
        y_margin: int = 50,
        duration_ms: int | None = None,
    ) -> bool:
        if child_widget is None:
            return False

        viewport = self._scroll_area.viewport()
        v_bar = self._scroll_area.verticalScrollBar()
        current = int(v_bar.value())

        top_left = child_widget.mapTo(viewport, QPoint(0, 0))
        top = int(top_left.y())

        height = int(child_widget.height())
        if height <= 0:
            try:
                height = int(child_widget.sizeHint().height())
            except Exception:
                height = 0

        bottom = top + height
        view_h = int(viewport.height())
        y_margin = max(0, int(y_margin))

        target = current
        if top < y_margin:
            target = current + top - y_margin
        elif bottom > view_h - y_margin:
            target = current + bottom - (view_h - y_margin)

        target = max(v_bar.minimum(), min(int(target), v_bar.maximum()))
        return self.smooth_scroll_to(target, duration_ms=duration_ms)

    def _get_vscroll_pos(self) -> int:
        return self._scroll_area.verticalScrollBar().value()

    def _set_vscroll_pos(self, value: int):
        self._scroll_area.verticalScrollBar().setValue(int(value))

    vscroll_pos = Property(int, _get_vscroll_pos, _set_vscroll_pos)

    def _get_hscroll_pos(self) -> int:
        return self._scroll_area.horizontalScrollBar().value()

    def _set_hscroll_pos(self, value: int):
        self._scroll_area.horizontalScrollBar().setValue(int(value))

    hscroll_pos = Property(int, _get_hscroll_pos, _set_hscroll_pos)


class SmoothScrollArea(QScrollArea):
    """
    QScrollArea with interpolated (smooth) scrolling.

    Should now be more global-ish and reusable
    Mainly so that it now fits text areas as well (used in dry-run)
    """

    def __init__(
        self,
        parent=None,
        *,
        scroll_step_px: int | tuple[int, int] | None = None,
        scroll_duration_ms: int | None = None,
    ):
        super().__init__(parent)
        self._smooth_scroll = SmoothScrollController(
            self,
            self,
            scroll_step_px=scroll_step_px,
            scroll_duration_ms=scroll_duration_ms,
        )

    def smooth_scroll_to(self, target_value: int, *, duration_ms: int | None = None) -> bool:
        return self._smooth_scroll.smooth_scroll_to(target_value, duration_ms=duration_ms)

    def smooth_ensure_widget_visible(
        self,
        child_widget,
        *,
        y_margin: int = 50,
        duration_ms: int | None = None,
    ) -> bool:
        return self._smooth_scroll.smooth_ensure_widget_visible(
            child_widget,
            y_margin=y_margin,
            duration_ms=duration_ms,
        )

    def wheelEvent(self, event):
        if self._smooth_scroll.handle_wheel_event(event):
            event.accept()
            return
        super().wheelEvent(event)
