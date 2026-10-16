"""Main window and entry point: python -m lamzu_mac.gui [--demo FILE] [--screenshot DIR]."""
from __future__ import annotations

import argparse
import os
import sys
from typing import Callable, List, Optional

from PySide6.QtCore import QMetaObject, QSize, Qt, QThread, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from .. import __version__
from .. import protocol as P
from ..device import Battery
from . import theme as T
from .icon import app_icon
from .pages import ButtonsPage, DevicePage, LightingPage, PerformancePage, SensorPage
from .widgets import BatteryGlyph, StatusDot, Toast, label, nav_icon
from .worker import DeviceWorker, Snapshot, load_snapshot, poll_status

POLL_MS = 2500
BATTERY_EVERY = 12   # polls (~30 s)

NAV = [("performance", "Desempenho"), ("buttons", "Botões"), ("lighting", "Iluminação"),
       ("sensor", "Sensor"), ("device", "Dispositivo")]


class MainWindow(QMainWindow):
    def __init__(self, demo: Optional[bytes] = None):
        super().__init__()
        self.setWindowTitle("LAMZU Configurator")
        self.resize(1200, 800)
        self.setMinimumSize(1040, 700)
        self.snapshot: Optional[Snapshot] = None
        self.image: Optional[P.FlashImage] = None
        self.battery: Optional[Battery] = None
        self.state = "searching"           # searching | absent | offline | online
        self._busy = False
        self._polls = 0
        self._on_loaded: List[Callable[[], None]] = []

        self.thread = QThread(self)
        self.worker = DeviceWorker(demo)
        self.worker.moveToThread(self.thread)
        self.worker.finished.connect(self._job_finished, Qt.ConnectionType.QueuedConnection)
        self.thread.start()

        self._build()
        self._set_state("searching")
        self.timer = QTimer(self, interval=POLL_MS)
        self.timer.timeout.connect(self._poll)
        self.timer.start()
        QTimer.singleShot(0, self.reload)

    # -- layout -------------------------------------------------------------
    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(250)
        s = QVBoxLayout(side)
        s.setContentsMargins(18, 22, 18, 18)
        s.setSpacing(4)
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(nav_icon("buttons", T.ACCENT, 26).pixmap(26, 26))
        brand.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(label("LAMZU", "brand"))
        names.addWidget(label(f"Configurador  ·  v{__version__}", "brandSub"))
        brand.addLayout(names, 1)
        s.addLayout(brand)
        s.addSpacing(22)

        self.nav_group = QButtonGroup(self)
        self.nav_buttons = {}
        for i, (key, text) in enumerate(NAV):
            b = QPushButton(f"   {text}")
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setIcon(nav_icon(key))
            b.setIconSize(QSize(18, 18))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=i: self._go(idx))
            self.nav_group.addButton(b)
            self.nav_buttons[key] = b
            s.addWidget(b)
        s.addStretch(1)

        card = QFrame()
        card.setObjectName("deviceCard")
        c = QVBoxLayout(card)
        c.setContentsMargins(14, 12, 14, 12)
        c.setSpacing(6)
        top = QHBoxLayout()
        self.dot = StatusDot()
        top.addWidget(self.dot)
        self.dev_name = label("Procurando…", "deviceName")
        top.addWidget(self.dev_name, 1)
        c.addLayout(top)
        bottom = QHBoxLayout()
        self.dev_meta = label("", "deviceMeta")
        bottom.addWidget(self.dev_meta, 1)
        self.battery_glyph = BatteryGlyph()
        bottom.addWidget(self.battery_glyph)
        c.addLayout(bottom)
        s.addWidget(card)
        lay.addWidget(side)

        content = QWidget()
        content.setObjectName("content")
        v = QVBoxLayout(content)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.banner = QFrame()
        self.banner.setObjectName("banner")
        b = QHBoxLayout(self.banner)
        b.setContentsMargins(16, 12, 16, 12)
        self.banner_text = label("", "rowLabel", wrap=True)
        self.banner_text.setStyleSheet(f"color: {T.WARNING};")
        b.addWidget(self.banner_text, 1)
        wrap = QHBoxLayout()
        wrap.setContentsMargins(36, 20, 36, 0)
        wrap.addWidget(self.banner)
        v.addLayout(wrap)

        self.stack = QStackedWidget()
        self.pages = [PerformancePage(self), ButtonsPage(self), LightingPage(self),
                      SensorPage(self), DevicePage(self)]
        self.lighting_page, self.sensor_page = self.pages[2], self.pages[3]
        for p in self.pages:
            self.stack.addWidget(p)
        v.addWidget(self.stack, 1)
        lay.addWidget(content, 1)
        self.toast = Toast(content)
        self._go(0)

    def _go(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, (key, _) in enumerate(NAV):
            b = self.nav_buttons[key]
            b.setChecked(i == index)
            b.setIcon(nav_icon(key, T.TEXT if i == index else T.TEXT_DIM))

    # -- state --------------------------------------------------------------
    def _set_state(self, state: str) -> None:
        self.state = state
        ready = state == "online" and self.image is not None
        for p in self.pages:
            p.setEnabled(ready)
        messages = {
            "searching": "Procurando o mouse…",
            "absent": "Nenhum dispositivo LAMZU encontrado. Conecte o receptor ou o cabo USB. "
                      "No Windows, feche o app oficial “Mouse Drive Beta”.",
            "offline": "O receptor está conectado, mas o mouse está em suspensão. Mexa o mouse para reconectar.",
        }
        if ready and not (self.snapshot.identity and self.snapshot.identity.model):
            messages["online"] = ("Modelo não reconhecido: todas as opções estão visíveis, mas algumas podem "
                                  "não existir no seu mouse. Considere abrir uma issue no GitHub com a saída "
                                  "de `lamzu info`.")
        self.banner.setVisible(state in messages)
        self.banner_text.setText(messages.get(state, ""))
        color = {"online": T.SUCCESS, "offline": T.WARNING}.get(state, T.TEXT_FAINT)
        self.dot.set_color(color)
        if state == "absent":
            self.dev_name.setText("Desconectado")
            self.dev_meta.setText("")
            self.battery_glyph.set_level(None)
        elif self.snapshot:
            ident = self.snapshot.identity
            self.dev_name.setText(ident.model.name if ident and ident.model
                                  else self.snapshot.info.product.replace(" (demo)", "") or "LAMZU")
            if state == "offline":
                self.dev_meta.setText("Mouse em suspensão")
                self.battery_glyph.set_level(None)
            else:
                self._show_battery()

    def _show_battery(self) -> None:
        if self.battery:
            charging = "  ⚡" if self.battery.charging else ""
            self.dev_meta.setText(f"Conectado  ·  {self.battery.level}%{charging}")
            self.battery_glyph.set_level(self.battery.level, self.battery.charging)
        else:
            self.dev_meta.setText("Conectado")

    # -- jobs ---------------------------------------------------------------
    def _job_finished(self, callback, result, error) -> None:
        if callback:
            callback(result, error)

    def run_job(self, fn, on_success: Callable[[object], None]) -> None:
        """Run fn(worker) on the HID thread; report errors as a toast."""
        if self.state != "online":
            self.toast.show_message("Mouse indisponível", "error")
            return

        def done(result, error):
            if error is None:
                on_success(result)
            else:
                self._report(error)
        self.worker.submit(fn, done)

    def commit(self, patches: List[P.Patch], message: str = "Salvo no mouse") -> None:
        if not patches:
            return
        self.run_job(lambda w: w.device.apply(patches), lambda _: self.toast.show_message(message))

    def _report(self, error: BaseException) -> None:
        if isinstance(error, TimeoutError):
            self.toast.show_message("O mouse não respondeu. Mexa o mouse e tente de novo.", "error", 4000)
        else:
            self.toast.show_message(f"Erro: {error}", "error", 5000)
        self.reload()

    def reload(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.worker.submit(load_snapshot, self._loaded)

    def _loaded(self, snap: Optional[Snapshot], error) -> None:
        self._busy = False
        if error is not None or snap is None:
            self._set_state("absent")
            return
        self.snapshot = snap
        if not snap.online:
            self._set_state("offline")
            return
        self.image = snap.image
        self.battery = snap.battery
        self._set_state("online")
        for p in self.pages:
            p.load()
        has_lighting = self.lighting_page.has_content
        self.nav_buttons["lighting"].setVisible(has_lighting)
        if not has_lighting and self.stack.currentWidget() is self.lighting_page:
            self._go(0)
        for cb in self._on_loaded:
            cb()
        self._on_loaded.clear()

    def _poll(self) -> None:
        if self._busy:
            return
        if self.state != "online":
            self.reload()
            return
        self._polls += 1
        self._busy = True
        self.worker.submit(lambda w: poll_status(w, self._polls % BATTERY_EVERY == 0), self._polled)

    def _polled(self, snap: Optional[Snapshot], error) -> None:
        self._busy = False
        if error is not None or snap is None:
            self._set_state("absent")
        elif not snap.online:
            self._set_state("offline")
        elif snap.battery:
            self.battery = snap.battery
            self._show_battery()

    def closeEvent(self, e) -> None:
        if self.thread.isRunning():
            self.timer.stop()
            self.worker.finished.disconnect(self._job_finished)
            # Close the HID device on its own thread and wait for it. QThread.quit()
            # drops queued jobs, which left the device open until interpreter
            # teardown, where macOS crashed ("Python quit unexpectedly").
            QMetaObject.invokeMethod(self.worker, "shutdown", Qt.ConnectionType.BlockingQueuedConnection)
            self.thread.quit()
            self.thread.wait()
        super().closeEvent(e)

    # -- screenshots --------------------------------------------------------
    def capture_pages(self, directory: str) -> None:
        os.makedirs(directory, exist_ok=True)
        for i, (key, _) in enumerate(NAV):
            if self.nav_buttons[key].isHidden():
                continue
            self._go(i)
            QApplication.processEvents()
            self.grab().save(os.path.join(directory, f"{i + 1}-{key}.png"))
        self.close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="lamzu-gui")
    ap.add_argument("--demo", metavar="FILE", help="use a flash dump instead of a real device")
    ap.add_argument("--screenshot", metavar="DIR", help="save every page as PNG and exit")
    args = ap.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("LAMZU Configurator")
    app.setStyle("Fusion")
    app.setFont(QFont(T.FONT, 10))
    app.setStyleSheet(T.STYLE)
    app.setWindowIcon(app_icon())
    demo = open(args.demo, "rb").read() if args.demo else None
    win = MainWindow(demo)
    win.show()
    if args.screenshot:
        win._on_loaded.append(lambda: QTimer.singleShot(400, lambda: win.capture_pages(args.screenshot)))
        QTimer.singleShot(20000, lambda: win.capture_pages(args.screenshot))
    code = app.exec()
    del win   # destroy the window (and its HID thread) before the QApplication
    sys.exit(code)


if __name__ == "__main__":
    main()
