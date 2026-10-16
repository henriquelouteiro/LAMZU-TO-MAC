"""Application icon, drawn in code so no binary asset is needed.

    python -m lamzu_mac.gui.icon out.ico             # Windows icon (256 px)
    python -m lamzu_mac.gui.icon --iconset app.iconset  # PNGs for macOS iconutil
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap

from . import theme as T


def app_pixmap(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 256, size / 256)
    bg = QLinearGradient(0, 0, 0, 256)
    bg.setColorAt(0, QColor("#1d2430"))
    bg.setColorAt(1, QColor(T.BG))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(QRectF(8, 8, 240, 240), 56, 56)

    pen = QPen(QColor(T.ACCENT), 14)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(78, 48, 100, 160), 50, 50)
    p.drawLine(QPointF(128, 52), QPointF(128, 108))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(T.ACCENT))
    p.drawRoundedRect(QRectF(119, 78, 18, 30), 9, 9)
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(size))
    return icon


def write_iconset(directory: str) -> None:
    """File names expected by `iconutil -c icns`."""
    import os
    os.makedirs(directory, exist_ok=True)
    for base in (16, 32, 128, 256, 512):
        for scale, suffix in ((1, ""), (2, "@2x")):
            path = os.path.join(directory, f"icon_{base}x{base}{suffix}.png")
            if not app_pixmap(base * scale).save(path):
                sys.exit(f"could not write {path}")


if __name__ == "__main__":
    from PySide6.QtGui import QGuiApplication
    QGuiApplication(sys.argv[:1])
    if sys.argv[1] == "--iconset":
        write_iconset(sys.argv[2])
    elif not app_pixmap(256).save(sys.argv[1]):
        sys.exit("could not write icon")
