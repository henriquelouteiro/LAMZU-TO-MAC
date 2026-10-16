"""Custom widgets: cards, toggle switch, segmented control, color swatch,
battery glyph, line icons and the interactive mouse diagram."""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence, Tuple

from PySide6.QtCore import (
    Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton, QButtonGroup, QColorDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QSlider, QVBoxLayout, QWidget,
)

from . import theme as T


# ---------------------------------------------------------------------------
# layout helpers
# ---------------------------------------------------------------------------

class Card(QFrame):
    def __init__(self, title: str = "", hint: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 18, 20, 18)
        self.body.setSpacing(14)
        if title:
            head = QVBoxLayout()
            head.setSpacing(3)
            t = QLabel(title)
            t.setObjectName("cardTitle")
            head.addWidget(t)
            if hint:
                h = QLabel(hint)
                h.setObjectName("cardHint")
                h.setWordWrap(True)
                head.addWidget(h)
            self.body.addLayout(head)

    def add(self, widget_or_layout) -> None:
        if isinstance(widget_or_layout, QWidget):
            self.body.addWidget(widget_or_layout)
        else:
            self.body.addLayout(widget_or_layout)


def separator() -> QFrame:
    line = QFrame()
    line.setObjectName("separator")
    return line


def label(text: str, name: str = "rowLabel", wrap: bool = False) -> QLabel:
    w = QLabel(text)
    w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def setting_row(title: str, control: QWidget, hint: str = "") -> QHBoxLayout:
    """Label (and optional hint) on the left, control on the right."""
    row = QHBoxLayout()
    row.setSpacing(16)
    text = QVBoxLayout()
    text.setSpacing(2)
    text.addWidget(label(title))
    if hint:
        text.addWidget(label(hint, "rowHint", wrap=True))
    row.addLayout(text, 1)
    row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
    return row


# ---------------------------------------------------------------------------
# toggle switch
# ---------------------------------------------------------------------------

class ToggleSwitch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 24)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, value: float) -> None:
        self._pos = value
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setChecked(self, checked: bool) -> None:  # noqa: N802 - Qt API
        super().setChecked(checked)
        self._anim.stop()
        self._pos = 1.0 if checked else 0.0
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(44, 24)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        off, on = QColor(T.BORDER_STRONG), QColor(T.ACCENT)
        if not self.isEnabled():
            on = QColor(T.TEXT_FAINT)
        track = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos),
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, 44, 24), 12, 12)
        p.setBrush(QColor("white") if self.isEnabled() else QColor(T.TEXT_DIM))
        p.drawEllipse(QPointF(12 + 20 * self._pos, 12), 9, 9)


# ---------------------------------------------------------------------------
# segmented control
# ---------------------------------------------------------------------------

class Segmented(QFrame):
    """Mutually exclusive buttons; emits the value of the clicked segment."""

    changed = Signal(object)

    def __init__(self, options: Sequence[Tuple[object, str]], parent=None):
        super().__init__(parent)
        self.setObjectName("segmented")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._buttons: Dict[object, QPushButton] = {}
        for value, text in options:
            b = QPushButton(text)
            b.setObjectName("segment")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=value: self.changed.emit(v))
            self._group.addButton(b)
            self._buttons[value] = b
            lay.addWidget(b)

    def set_allowed(self, values) -> None:
        """Show only the segments whose value is in `values`."""
        for value, button in self._buttons.items():
            button.setVisible(value in values)

    def set_value(self, value) -> None:
        b = self._buttons.get(value)
        if b:
            b.setChecked(True)
        else:  # unknown value: clear the selection
            self._group.setExclusive(False)
            for btn in self._buttons.values():
                btn.setChecked(False)
            self._group.setExclusive(True)


# ---------------------------------------------------------------------------
# slider with value label
# ---------------------------------------------------------------------------

class ValueSlider(QWidget):
    """Slider that reports its final value on release (or keyboard step)."""

    committed = Signal(int)

    def __init__(self, minimum: int, maximum: int, fmt: Callable[[int], str] = str, parent=None):
        super().__init__(parent)
        self._fmt = fmt
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setMinimumWidth(220)
        self.value_label = label("", "value")
        self.value_label.setMinimumWidth(52)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.value_label)
        self._debounce = QTimer(self, singleShot=True, interval=350)
        self._debounce.timeout.connect(lambda: self.committed.emit(self.slider.value()))
        self.slider.valueChanged.connect(self._on_change)
        self.slider.sliderReleased.connect(self._commit_now)

    def _on_change(self, v: int) -> None:
        self.value_label.setText(self._fmt(v))
        if not self.slider.isSliderDown():
            self._debounce.start()

    def _commit_now(self) -> None:
        self._debounce.stop()
        self.committed.emit(self.slider.value())

    def set_value(self, v: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(v)
        self.slider.blockSignals(False)
        self.value_label.setText(self._fmt(v))


# ---------------------------------------------------------------------------
# color swatch
# ---------------------------------------------------------------------------

class ColorSwatch(QAbstractButton):
    colorPicked = Signal(tuple)

    def __init__(self, size: int = 26, parent=None):
        super().__init__(parent)
        self._rgb = (255, 255, 255)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Escolher cor")
        self.clicked.connect(self._pick)

    def set_rgb(self, rgb: Optional[Tuple[int, int, int]]) -> None:
        self._rgb = rgb or (80, 80, 80)
        self.update()

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(*self._rgb), self.window(), "Cor do LED")
        if c.isValid():
            self.set_rgb((c.red(), c.green(), c.blue()))
            self.colorPicked.emit(self._rgb)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        alpha = 255 if self.isEnabled() else 70
        p.setPen(QPen(QColor(255, 255, 255, 40 if self.isEnabled() else 15), 1.5))
        p.setBrush(QColor(*self._rgb, alpha))
        p.drawEllipse(r)
        if self.underMouse() and self.isEnabled():
            p.setPen(QPen(QColor(T.TEXT), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(r.adjusted(-1, -1, 1, 1))

    def enterEvent(self, e) -> None:
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self.update()
        super().leaveEvent(e)


# ---------------------------------------------------------------------------
# battery + status dot
# ---------------------------------------------------------------------------

class BatteryGlyph(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.level: Optional[int] = None
        self.charging = False
        self.setFixedSize(30, 15)

    def set_level(self, level: Optional[int], charging: bool = False) -> None:
        self.level, self.charging = level, charging
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRectF(1, 1.5, 24, 12)
        p.setPen(QPen(QColor(T.TEXT_DIM), 1.3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(body, 3, 3)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.TEXT_DIM))
        p.drawRoundedRect(QRectF(26, 5, 2.5, 5), 1, 1)
        if self.level is None:
            return
        color = T.SUCCESS if self.level > 30 else T.WARNING if self.level > 15 else T.DANGER
        p.setBrush(QColor(color))
        p.drawRoundedRect(QRectF(3, 3.5, max(1.5, 20 * self.level / 100), 8), 1.5, 1.5)


class StatusDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = QColor(T.TEXT_FAINT)
        self.setFixedSize(10, 10)

    def set_color(self, color: str) -> None:
        self.color = QColor(color)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        glow = QColor(self.color)
        glow.setAlpha(60)
        p.setBrush(glow)
        p.drawEllipse(QRectF(0, 0, 10, 10))
        p.setBrush(self.color)
        p.drawEllipse(QRectF(2, 2, 6, 6))


# ---------------------------------------------------------------------------
# line icons for the navigation
# ---------------------------------------------------------------------------

def nav_icon(kind: str, color: str = T.TEXT_DIM, size: int = 18) -> QIcon:
    scale = 3
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(scale * size / 24, scale * size / 24)
    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "performance":
        path = QPainterPath()
        path.arcMoveTo(QRectF(3, 5, 18, 18), 200)
        path.arcTo(QRectF(3, 5, 18, 18), 200, -220)
        p.drawPath(path)
        p.drawLine(QPointF(12, 14), QPointF(16, 9.5))
        p.drawEllipse(QPointF(12, 14), 1.2, 1.2)
    elif kind == "buttons":
        p.drawRoundedRect(QRectF(6, 3, 12, 18), 6, 6)
        p.drawLine(QPointF(12, 3.5), QPointF(12, 10))
        p.drawLine(QPointF(6.5, 10), QPointF(17.5, 10))
    elif kind == "lighting":
        path = QPainterPath()
        path.moveTo(9, 16)
        path.cubicTo(9, 13, 5.5, 12, 5.5, 8.5)
        path.cubicTo(5.5, 5, 8.5, 2.5, 12, 2.5)
        path.cubicTo(15.5, 2.5, 18.5, 5, 18.5, 8.5)
        path.cubicTo(18.5, 12, 15, 13, 15, 16)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(9.5, 19), QPointF(14.5, 19))
        p.drawLine(QPointF(10.5, 21.5), QPointF(13.5, 21.5))
    elif kind == "sensor":
        p.drawEllipse(QPointF(12, 12), 7.5, 7.5)
        p.drawEllipse(QPointF(12, 12), 2.5, 2.5)
        for a, b in (((12, 1.5), (12, 4.5)), ((12, 19.5), (12, 22.5)),
                     ((1.5, 12), (4.5, 12)), ((19.5, 12), (22.5, 12))):
            p.drawLine(QPointF(*a), QPointF(*b))
    elif kind == "device":
        p.drawRoundedRect(QRectF(6, 6, 12, 12), 2.5, 2.5)
        p.drawRoundedRect(QRectF(9.5, 9.5, 5, 5), 1, 1)
        for c in (9.5, 14.5):
            for a, b in (((c, 2.5), (c, 6)), ((c, 18), (c, 21.5)),
                         ((2.5, c), (6, c)), ((18, c), (21.5, c))):
                p.drawLine(QPointF(*a), QPointF(*b))
    p.end()
    pm.setDevicePixelRatio(scale)
    return QIcon(pm)


# ---------------------------------------------------------------------------
# mouse diagram
# ---------------------------------------------------------------------------

class MouseDiagram(QWidget):
    """Top view of a symmetrical mouse with clickable, numbered hotspots for
    buttons 0-5 (left, right, wheel, back, forward, DPI on the base)."""

    selected = Signal(int)

    # hotspot centers in a 240 x 360 design space
    HOTSPOTS = {0: (82, 88), 1: (158, 88), 2: (120, 74), 3: (30, 190), 4: (30, 140), 5: (120, 300)}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current = 0
        self.hover: Optional[int] = None
        self.setMouseTracking(True)
        self.setMinimumSize(220, 300)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    def set_current(self, index: int) -> None:
        self.current = index
        self.update()

    def _transform(self) -> Tuple[float, float, float]:
        s = min(self.width() / 240, self.height() / 360)
        return s, (self.width() - 240 * s) / 2, (self.height() - 360 * s) / 2

    def _hit(self, pos) -> Optional[int]:
        s, ox, oy = self._transform()
        for idx, (x, y) in self.HOTSPOTS.items():
            if (pos.x() - (ox + x * s)) ** 2 + (pos.y() - (oy + y * s)) ** 2 < (16 * s) ** 2:
                return idx
        return None

    def mouseMoveEvent(self, e) -> None:
        hit = self._hit(e.position())
        if hit != self.hover:
            self.hover = hit
            self.setCursor(Qt.CursorShape.PointingHandCursor if hit is not None else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, _e) -> None:
        self.hover = None
        self.update()

    def mousePressEvent(self, e) -> None:
        hit = self._hit(e.position())
        if hit is not None:
            self.set_current(hit)
            self.selected.emit(hit)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s, ox, oy = self._transform()
        p.translate(ox, oy)
        p.scale(s, s)

        body = QPainterPath()
        body.moveTo(120, 20)
        body.cubicTo(175, 20, 200, 60, 202, 130)
        body.cubicTo(204, 200, 196, 280, 170, 320)
        body.cubicTo(150, 345, 90, 345, 70, 320)
        body.cubicTo(44, 280, 36, 200, 38, 130)
        body.cubicTo(40, 60, 65, 20, 120, 20)
        p.setPen(QPen(QColor(T.BORDER_STRONG), 2))
        p.setBrush(QColor(T.CARD_HOVER))
        p.drawPath(body)

        # button split and palm line
        p.setPen(QPen(QColor(T.BORDER_STRONG), 1.6))
        p.drawLine(QPointF(120, 21), QPointF(120, 58))
        p.drawLine(QPointF(120, 92), QPointF(120, 140))
        split = QPainterPath()
        split.moveTo(40, 142)
        split.cubicTo(80, 152, 160, 152, 200, 142)
        p.drawPath(split)
        # wheel
        p.setBrush(QColor(T.BG))
        p.drawRoundedRect(QRectF(111, 58, 18, 34), 9, 9)
        # side buttons
        p.setBrush(QColor(T.CARD))
        p.drawRoundedRect(QRectF(31, 118, 12, 42), 5, 5)
        p.drawRoundedRect(QRectF(31, 168, 12, 42), 5, 5)
        # DPI button on the base (dashed: it is underneath)
        dash = QPen(QColor(T.TEXT_FAINT), 1.4, Qt.PenStyle.DashLine)
        p.setPen(dash)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(120, 300), 18, 18)
        p.setPen(QColor(T.TEXT_FAINT))
        f = p.font()
        f.setPixelSize(10)
        p.setFont(f)
        p.drawText(QRectF(70, 322, 100, 16), Qt.AlignmentFlag.AlignCenter, "DPI (base)")

        for idx, (x, y) in self.HOTSPOTS.items():
            active = idx == self.current
            hovered = idx == self.hover
            r = 12 if active else 10.5
            ring = QColor(T.ACCENT)
            ring.setAlpha(70)
            if active:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(ring)
                p.drawEllipse(QPointF(x, y), r + 6, r + 6)
            p.setPen(QPen(QColor(T.ACCENT if (active or hovered) else T.TEXT_FAINT), 1.6))
            p.setBrush(QColor(T.ACCENT) if active else QColor(T.BG))
            p.drawEllipse(QPointF(x, y), r, r)
            f.setPixelSize(11)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("white") if active else QColor(T.TEXT))
            p.drawText(QRectF(x - r, y - r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, str(idx + 1))


# ---------------------------------------------------------------------------
# toast
# ---------------------------------------------------------------------------

class Toast(QLabel):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.hide()
        self._fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fx)
        self._fade = QPropertyAnimation(self._fx, b"opacity", self)
        self._fade.setDuration(220)
        self._fade.finished.connect(self._after_fade)
        self._timer = QTimer(self, singleShot=True)
        self._timer.timeout.connect(self._fade_out)

    def show_message(self, text: str, kind: str = "ok", ms: int = 2200) -> None:
        color = {"ok": T.SUCCESS, "error": T.DANGER, "info": T.ACCENT}[kind]
        mark = {"ok": "✓", "error": "!", "info": "•"}[kind]
        self.setText(f"<span style='color:{color};font-weight:700'>{mark}</span>&nbsp;&nbsp;{text}")
        self.adjustSize()
        par = self.parentWidget()
        self.move(par.width() - self.width() - 28, par.height() - self.height() - 24)
        self.raise_()
        self.show()
        self._fade.stop()
        self._fade.setStartValue(self._fx.opacity() if self.isVisible() else 0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._timer.start(ms)

    def _fade_out(self) -> None:
        self._fade.stop()
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _after_fade(self) -> None:
        if self._fx.opacity() == 0.0:
            self.hide()
