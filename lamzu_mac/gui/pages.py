"""The five configuration pages."""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QRadioButton, QScrollArea, QSlider,
    QSpinBox, QStackedWidget, QVBoxLayout, QWidget, QButtonGroup,
)

from .. import protocol as P
from ..selftest import FULL_SIZE, run_selftest
from . import theme as T
from .widgets import (
    BatteryGlyph, Card, ColorSwatch, MouseDiagram, Segmented, ToggleSwitch, ValueSlider,
    label, separator, setting_row,
)

if TYPE_CHECKING:
    from .app import MainWindow


def _combo(items: List[Tuple[object, str]], width: int = 200) -> QComboBox:
    c = QComboBox()
    for value, text in items:
        c.addItem(text, value)
    c.setMinimumWidth(width)
    return c


def _select(combo: QComboBox, value) -> None:
    i = combo.findData(value)
    combo.setCurrentIndex(i if i >= 0 else -1)


def model_name(snap) -> str:
    ident = snap.identity
    if ident is None:
        return "LAMZU (modelo não identificado)"
    if ident.model:
        return ident.model.name
    return f"Modelo não reconhecido (CID {ident.cid}, MID {ident.mid})"


def _seconds(units: int) -> str:
    s = units * 10
    return f"{s} s" if s < 60 else f"{s // 60} min"


class Page(QWidget):
    title = ""
    subtitle = ""

    def __init__(self, app: "MainWindow"):
        super().__init__()
        self.app = app
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        inner = QWidget()
        scroll.setWidget(inner)
        self.layout_ = QVBoxLayout(inner)
        self.layout_.setContentsMargins(36, 30, 36, 36)
        self.layout_.setSpacing(18)
        head = QVBoxLayout()
        head.setSpacing(4)
        head.addWidget(label(self.title, "pageTitle"))
        head.addWidget(label(self.subtitle, "pageSubtitle", wrap=True))
        self.layout_.addLayout(head)
        self.layout_.addSpacing(4)
        self.build()
        self.layout_.addStretch(1)

    @property
    def img(self) -> P.FlashImage:
        return self.app.image

    def build(self) -> None:
        raise NotImplementedError

    def load(self) -> None:
        raise NotImplementedError


# ===========================================================================
# Performance: polling rate and DPI stages
# ===========================================================================

class StageRow(QWidget):
    def __init__(self, index: int, page: "PerformancePage"):
        super().__init__()
        self.index, self.page = index, page
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(14)
        self.radio = QRadioButton()
        self.radio.setToolTip("Tornar este estágio o ativo")
        self.radio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.swatch = ColorSwatch(22)
        self.name = label(f"Estágio {index + 1}")
        self.name.setMinimumWidth(70)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(P.DPI_MIN // 50, P.DPI_MAX // 50)
        self.spin = QSpinBox()
        self.spin.setRange(P.DPI_MIN, P.DPI_MAX)
        self.spin.setSingleStep(P.DPI_STEP)
        self.spin.setSuffix("  DPI")
        self.spin.setFixedWidth(118)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        for w in (self.radio, self.swatch, self.name):
            lay.addWidget(w)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)

        self.slider.valueChanged.connect(lambda v: self.spin.setValue(v * 50))
        self.slider.sliderReleased.connect(self._commit)
        self.spin.editingFinished.connect(self._commit)
        self.radio.clicked.connect(lambda: page.set_active(index))
        self.swatch.colorPicked.connect(lambda rgb: page.app.commit(
            [page.img.set_dpi_color(index, rgb)], f"Cor do estágio {index + 1} atualizada"))

    def _commit(self) -> None:
        dpi = round(self.spin.value() / 50) * 50
        self.spin.setValue(dpi)
        if self.page.img.dpi_stage(self.index).dpi != dpi:
            self.page.app.commit([self.page.img.set_dpi(self.index, dpi)],
                                 f"Estágio {self.index + 1}: {dpi} DPI")
        self.page.refresh_summary()

    def load(self, stage: P.DpiStage, enabled: bool, active: bool) -> None:
        for w in (self.slider, self.spin):
            w.blockSignals(True)
        if stage.dpi:
            self.slider.setValue(stage.dpi // 50)
            self.spin.setValue(stage.dpi)
        for w in (self.slider, self.spin):
            w.blockSignals(False)
        self.swatch.set_rgb(stage.color)
        self.radio.setChecked(active)
        for w in (self.slider, self.spin, self.swatch, self.radio):
            w.setEnabled(enabled)
        self.name.setStyleSheet(f"color: {T.TEXT if enabled else T.TEXT_FAINT};")


class PerformancePage(Page):
    title = "Desempenho"
    subtitle = "Taxa de polling e estágios de DPI. As mudanças são gravadas direto na memória do mouse."

    def build(self) -> None:
        top = QHBoxLayout()
        top.setSpacing(18)

        summary = Card("DPI ativo")
        self.big_dpi = label("—", "bigValue")
        self.big_meta = label("", "hint")
        summary.add(self.big_dpi)
        summary.add(self.big_meta)
        summary.setFixedWidth(260)
        top.addWidget(summary)

        rate = Card("Taxa de polling", "Com que frequência o mouse envia a posição ao computador. "
                    "As opções dependem do modelo e do receptor.")
        self.rate = Segmented([(hz, f"{hz} Hz") for hz in sorted(P.REPORT_RATE_CODES)])
        self.rate.changed.connect(self._set_rate)
        rate.add(self.rate)
        top.addWidget(rate, 1)
        self.layout_.addLayout(top)

        stages = Card("Estágios de DPI", "O botão de DPI percorre os estágios ativos. "
                      "Marque o círculo para definir o estágio em uso e clique na cor para trocar o LED.")
        count_row = QHBoxLayout()
        count_row.addWidget(label("Estágios ativos"))
        count_row.addStretch(1)
        self.count = Segmented([(n, str(n)) for n in range(1, P.DPI_STAGES + 1)])
        self.count.changed.connect(self._set_count)
        count_row.addWidget(self.count)
        stages.add(count_row)
        stages.add(separator())
        self.radio_group = QButtonGroup(self)
        self.rows = []
        for i in range(P.DPI_STAGES):
            row = StageRow(i, self)
            self.radio_group.addButton(row.radio)
            self.rows.append(row)
            stages.add(row)
        self.layout_.addWidget(stages)

    def load(self) -> None:
        img = self.img
        rate = img.setting("report-rate")
        ident = self.app.snapshot.identity
        allowed = set(ident.rates() if ident else [125, 250, 500, 1000])
        allowed.add(P.REPORT_RATES.get(rate))   # never hide what is already stored
        self.rate.set_allowed(allowed)
        self.rate.set_value(P.REPORT_RATES.get(rate))
        count = img.setting("dpi-stages") or 1
        active = img.setting("dpi-active") or 0
        self.count.set_value(count)
        for i, row in enumerate(self.rows):
            row.load(img.dpi_stage(i), i < count, i == active)
        self.refresh_summary()

    def refresh_summary(self) -> None:
        img = self.img
        active = img.setting("dpi-active") or 0
        dpi = img.dpi_stage(active).dpi
        self.big_dpi.setText(f"{dpi} DPI" if dpi else "—")
        self.big_meta.setText(f"Estágio {active + 1} de {img.setting('dpi-stages') or 1}")

    def _set_rate(self, hz: int) -> None:
        self.app.commit([self.img.set_setting("report-rate", P.REPORT_RATE_CODES[hz])],
                        f"Taxa de polling: {hz} Hz")
        self.app.sensor_page.load()   # the sensor mode depends on the rate

    def _set_count(self, n: int) -> None:
        patches = [self.img.set_setting("dpi-stages", n)]
        if (self.img.setting("dpi-active") or 0) >= n:
            patches.append(self.img.set_setting("dpi-active", n - 1))
        self.app.commit(patches, f"{n} estágio(s) de DPI ativo(s)")
        self.load()

    def set_active(self, index: int) -> None:
        self.app.commit([self.img.set_setting("dpi-active", index)], f"Estágio {index + 1} ativo")
        self.refresh_summary()


# ===========================================================================
# Buttons
# ===========================================================================

BUTTON_NAMES = ["Botão esquerdo", "Botão direito", "Botão do meio (roda)",
                "Lateral traseiro", "Lateral dianteiro", "Botão de DPI (base)"]
DEFAULT_BINDINGS = ["left", "right", "middle", "back", "forward", "dpi-cycle"]

MOUSE_LABELS = [("left", "Clique esquerdo"), ("right", "Clique direito"), ("middle", "Clique do meio"),
                ("back", "Voltar"), ("forward", "Avançar")]
DPI_LABELS = [("dpi-cycle", "Ciclar estágios"), ("dpi-up", "DPI +"), ("dpi-down", "DPI −")]
SCROLL_LABELS = [("scroll-up", "Rolar para cima"), ("scroll-down", "Rolar para baixo"),
                 ("scroll-left", "Rolar para a esquerda"), ("scroll-right", "Rolar para a direita")]
LED_LABELS = [("lights-toggle", "Ligar/desligar todas as luzes"), ("lightbar-toggle", "Ligar/desligar a faixa de LED"),
              ("light-effect-cycle", "Alternar efeitos de luz")]
MEDIA_LABELS = [
    ("play", "Reproduzir/pausar"), ("next", "Próxima faixa"), ("prev", "Faixa anterior"),
    ("stop", "Parar"), ("mute", "Mudo"), ("vol-up", "Aumentar volume"), ("vol-down", "Diminuir volume"),
    ("media-player", "Player de mídia"), ("email", "E-mail"), ("calculator", "Calculadora"),
    ("my-computer", "Meu computador"), ("browser-search", "Navegador: pesquisar"),
    ("browser-home", "Navegador: página inicial"), ("browser-back", "Navegador: voltar"),
    ("browser-forward", "Navegador: avançar"), ("browser-refresh", "Navegador: atualizar"),
    ("browser-stop", "Navegador: parar"), ("browser-favorites", "Navegador: favoritos"),
]
CATEGORIES = [
    ("mouse", "Clique do mouse"), ("dpi", "Controle de DPI"), ("scroll", "Rolagem"),
    ("media", "Tecla de mídia"), ("shortcut", "Atalho de teclado"), ("fire", "Tiro rápido"),
    ("dpilock", "Trava de DPI"), ("led", "Iluminação"), ("rate", "Alternar taxa de polling"),
    ("profile", "Alternar perfil"), ("disabled", "Desativado"),
]
_SIMPLE_LABELS = dict(MOUSE_LABELS + DPI_LABELS + SCROLL_LABELS + LED_LABELS)


def _qt_to_hid():
    k = Qt.Key
    table = {getattr(k, f"Key_{chr(c)}"): 0x04 + c - ord("A") for c in range(ord("A"), ord("Z") + 1)}
    table.update({getattr(k, f"Key_{d}"): 0x1E + d - 1 for d in range(1, 10)})
    table.update({getattr(k, f"Key_F{i}"): 0x3A + i - 1 for i in range(1, 13)})
    named = {
        "0": 0x27, "Return": 0x28, "Enter": 0x28, "Escape": 0x29, "Backspace": 0x2A, "Tab": 0x2B,
        "Space": 0x2C, "Minus": 0x2D, "Equal": 0x2E, "BracketLeft": 0x2F, "BracketRight": 0x30,
        "Backslash": 0x31, "Semicolon": 0x33, "Apostrophe": 0x34, "QuoteLeft": 0x35, "Comma": 0x36,
        "Period": 0x37, "Slash": 0x38, "CapsLock": 0x39, "Print": 0x46, "ScrollLock": 0x47,
        "Pause": 0x48, "Insert": 0x49, "Home": 0x4A, "PageUp": 0x4B, "Delete": 0x4C, "End": 0x4D,
        "PageDown": 0x4E, "Right": 0x4F, "Left": 0x50, "Down": 0x51, "Up": 0x52,
        # shifted symbols on a US layout map to their base key
        "Exclam": 0x1E, "At": 0x1F, "NumberSign": 0x20, "Dollar": 0x21, "Percent": 0x22,
        "AsciiCircum": 0x23, "Ampersand": 0x24, "Asterisk": 0x25, "ParenLeft": 0x26,
        "ParenRight": 0x27, "Underscore": 0x2D, "Plus": 0x2E, "BraceLeft": 0x2F, "BraceRight": 0x30,
        "Bar": 0x31, "Colon": 0x33, "QuoteDbl": 0x34, "AsciiTilde": 0x35, "Less": 0x36,
        "Greater": 0x37, "Question": 0x38,
    }
    table.update({getattr(k, f"Key_{n}"): v for n, v in named.items()})
    return table


QT_TO_HID = _qt_to_hid()
_MODIFIER_KEYS = {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta}


class KeyCapture(QLineEdit):
    """Read-only field that records the next key combination (up to 3 keys)."""

    captured = Signal(list)

    def __init__(self):
        super().__init__()
        self.setObjectName("capture")
        self.setReadOnly(True)
        self.setPlaceholderText("Clique aqui e pressione a combinação…")
        self.events: List[P.ShortcutEvent] = []

    def set_events(self, events: List[P.ShortcutEvent]) -> None:
        self.events = list(events)
        self.setText(P.format_shortcut(events) if events else "")

    def keyPressEvent(self, e) -> None:  # noqa: N802 - Qt API
        mods = e.modifiers()
        mac = sys.platform == "darwin"
        # Qt swaps Command/Control on macOS: ControlModifier is Cmd there.
        mapping = [
            (Qt.KeyboardModifier.ControlModifier, 0x08 if mac else 0x01),
            (Qt.KeyboardModifier.MetaModifier, 0x01 if mac else 0x08),
            (Qt.KeyboardModifier.ShiftModifier, 0x02),
            (Qt.KeyboardModifier.AltModifier, 0x04),
        ]
        presses: List[Tuple[int, int]] = [(P.HidCodeType.MODIFIER, bit) for m, bit in mapping if mods & m]
        key = Qt.Key(e.key())
        if key not in _MODIFIER_KEYS:
            usage = QT_TO_HID.get(key)
            if usage is None:
                self.setText("Tecla não suportada")
                return
            presses.append((P.HidCodeType.KEY, usage))
        if not presses or len(presses) > 3:
            self.setText("Use no máximo 3 teclas")
            return
        events = [(P.KEY_DOWN, t, v) for t, v in presses] + [(P.KEY_UP, t, v) for t, v in reversed(presses)]
        self.set_events(events)
        self.captured.emit(events)


class ButtonsPage(Page):
    title = "Botões"
    subtitle = "Clique em um botão no desenho ou na lista e escolha a nova função."

    def build(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(18)

        left = Card()
        left.setFixedWidth(330)
        self.diagram = MouseDiagram()
        self.diagram.selected.connect(self._select)
        left.add(self.diagram)
        self.list = QListWidget()
        self.list.setFixedHeight(6 * 42)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentRowChanged.connect(self._select)
        left.add(self.list)
        row.addWidget(left)

        right = Card()
        self.editor_title = label("", "cardTitle")
        right.add(self.editor_title)
        self.editor_current = label("", "cardHint")
        right.add(self.editor_current)
        right.add(separator())

        self.category = _combo(CATEGORIES, 260)
        self.category.activated.connect(lambda _: self._show_category())
        right.add(setting_row("Função", self.category))

        self.stack = QStackedWidget()
        self.editors: Dict[str, QWidget] = {}
        self.sub: Dict[str, QComboBox] = {}
        for key, items in (("mouse", MOUSE_LABELS), ("dpi", DPI_LABELS), ("scroll", SCROLL_LABELS),
                           ("media", MEDIA_LABELS), ("led", LED_LABELS)):
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            self.sub[key] = _combo(items, 260)
            lay.addLayout(setting_row("Ação", self.sub[key]))
            lay.addStretch(1)
            self._add_editor(key, w)

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.capture = KeyCapture()
        clear = QPushButton("Limpar")
        clear.clicked.connect(lambda: self.capture.set_events([]))
        cap_row = QHBoxLayout()
        cap_row.addWidget(self.capture, 1)
        cap_row.addWidget(clear)
        lay.addLayout(cap_row)
        lay.addWidget(label("Até 3 teclas, por exemplo Ctrl+Shift+T. No Mac, ⌘ é gravado como a "
                            "tecla Command/Windows.", "rowHint", wrap=True))
        lay.addStretch(1)
        self._add_editor("shortcut", w)

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.fire_interval = QSpinBox()
        self.fire_interval.setRange(*P.FIRE_INTERVAL)
        self.fire_interval.setSuffix("  ms")
        self.fire_interval.setFixedWidth(120)
        self.fire_times = QSpinBox()
        self.fire_times.setRange(*P.FIRE_TIMES)
        self.fire_times.setFixedWidth(120)
        lay.addLayout(setting_row("Intervalo entre cliques", self.fire_interval))
        lay.addLayout(setting_row("Repetições", self.fire_times,
                                  "0 repete enquanto o botão estiver pressionado."))
        lay.addStretch(1)
        self._add_editor("fire", w)

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self.lock_dpi = QSpinBox()
        self.lock_dpi.setRange(100, 12800)
        self.lock_dpi.setSingleStep(50)
        self.lock_dpi.setSuffix("  DPI")
        self.lock_dpi.setFixedWidth(130)
        lay.addLayout(setting_row("DPI enquanto pressionado", self.lock_dpi,
                                  "Útil como botão de mira (sniper)."))
        lay.addStretch(1)
        self._add_editor("dpilock", w)

        for key in ("rate", "profile", "disabled", "macro"):
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            text = {"rate": "Cada clique alterna para a próxima taxa de polling.",
                    "profile": "Cada clique alterna para o próximo perfil salvo no mouse.",
                    "disabled": "O botão não fará nada.",
                    "macro": "Este botão tem uma macro gravada pelo app oficial. Edição de macros "
                             "ainda não é suportada; escolher outra função substitui a macro."}[key]
            lay.addWidget(label(text, "hint", wrap=True))
            lay.addStretch(1)
            self._add_editor(key, w)
        right.add(self.stack)

        self.warning = label("", "warning", wrap=True)
        self.warning.hide()
        right.add(self.warning)

        actions = QHBoxLayout()
        actions.addStretch(1)
        reset = QPushButton("Restaurar padrão")
        reset.clicked.connect(self._restore_default)
        apply = QPushButton("Aplicar ao mouse")
        apply.setObjectName("primary")
        apply.clicked.connect(self._apply)
        actions.addWidget(reset)
        actions.addWidget(apply)
        right.body.addStretch(1)
        right.add(actions)
        row.addWidget(right, 1)
        self.layout_.addLayout(row)
        self.current = 0

    def _add_editor(self, key: str, widget: QWidget) -> None:
        self.editors[key] = widget
        self.stack.addWidget(widget)

    # -- model <-> editor ---------------------------------------------------
    def _decode(self, index: int) -> Tuple[str, object]:
        b = self.img.binding(index)
        if b is None:
            return "disabled", None
        t = b.type
        if t == P.KeyClass.SHORTCUT:
            events = self.img.shortcut(index) or []
            if len(events) == 2 and events[0][1] == P.HidCodeType.MEDIA:
                return "media", P.MEDIA_NAMES.get(events[0][2])
            return "shortcut", events
        if t == P.KeyClass.FIRE:
            return "fire", (b.param1, b.param2)
        if t == P.KeyClass.DPI_LOCK:
            return "dpilock", (b.param1 + 1) * 50
        if t == P.KeyClass.MACRO:
            return "macro", None
        name = b.describe()
        for cat, table in (("mouse", MOUSE_LABELS), ("dpi", DPI_LABELS), ("scroll", SCROLL_LABELS),
                           ("led", LED_LABELS)):
            if name in dict(table):
                return cat, name
        simple = {P.KeyClass.REPORT_RATE_CYCLE: "rate", P.KeyClass.PROFILE_SWITCH: "profile"}
        return simple.get(t, "disabled"), None

    def _describe(self, index: int) -> str:
        cat, value = self._decode(index)
        if cat in ("mouse", "dpi", "scroll", "led"):
            return _SIMPLE_LABELS[value]
        if cat == "media":
            return dict(MEDIA_LABELS).get(value, "Tecla de mídia")
        if cat == "shortcut":
            return f"Atalho: {P.format_shortcut(value) or '—'}"
        if cat == "fire":
            return f"Tiro rápido ({value[0]} ms × {value[1] or '∞'})"
        if cat == "dpilock":
            return f"Trava de DPI ({value})"
        if cat == "macro":
            return "Macro"
        return dict(CATEGORIES)[cat]

    def load(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for i, name in enumerate(BUTTON_NAMES):
            item = QListWidgetItem()
            w = QWidget()
            lay = QHBoxLayout(w)
            lay.setContentsMargins(12, 4, 12, 4)
            num = label(str(i + 1), "value")
            num.setFixedWidth(16)
            lay.addWidget(num)
            text = QVBoxLayout()
            text.setSpacing(0)
            text.addWidget(label(name))
            text.addWidget(label(self._describe(i), "rowHint"))
            lay.addLayout(text, 1)
            item.setSizeHint(w.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, w)
        self.list.setCurrentRow(self.current)
        self.list.blockSignals(False)
        self._select(self.current)

    def _select(self, index: int) -> None:
        if index < 0:
            return
        self.current = index
        self.diagram.set_current(index)
        self.list.blockSignals(True)
        self.list.setCurrentRow(index)
        self.list.blockSignals(False)
        self.editor_title.setText(f"{index + 1}. {BUTTON_NAMES[index]}")
        self.editor_current.setText(f"Função atual: {self._describe(index)}")
        cat, value = self._decode(index)
        self.warning.hide()
        if cat == "macro":
            self.category.setCurrentIndex(-1)
        else:
            _select(self.category, cat)
        if cat in self.sub and value is not None:
            _select(self.sub[cat], value)
        if cat == "shortcut":
            self.capture.set_events(value)
        else:
            self.capture.set_events([])
        if cat == "fire":
            self.fire_interval.setValue(value[0])
            self.fire_times.setValue(value[1])
        if cat == "dpilock":
            self.lock_dpi.setValue(value)
        self.stack.setCurrentWidget(self.editors[cat])

    def _show_category(self) -> None:
        cat = self.category.currentData()
        self.stack.setCurrentWidget(self.editors[cat])
        if cat == "shortcut":
            self.capture.setFocus()

    def _build_patches(self) -> List[P.Patch]:
        cat = self.category.currentData()
        i = self.current
        if cat in ("mouse", "dpi", "scroll", "led"):
            return [self.img.set_binding(i, P.parse_binding(self.sub[cat].currentData()))]
        if cat == "media":
            return self.img.set_shortcut(i, P.parse_shortcut(self.sub["media"].currentData()))
        if cat == "shortcut":
            if not self.capture.events:
                raise ValueError("Pressione a combinação de teclas antes de aplicar.")
            return self.img.set_shortcut(i, self.capture.events)
        if cat == "fire":
            return [self.img.set_binding(i, P.fire_binding(self.fire_interval.value(), self.fire_times.value()))]
        if cat == "dpilock":
            dpi = round(self.lock_dpi.value() / 50) * 50
            return [self.img.set_binding(i, P.dpi_lock_binding(dpi))]
        return [self.img.set_binding(i, P.parse_binding({"rate": "rate-cycle", "profile": "profile-switch",
                                                         "disabled": "disabled"}[cat]))]

    def _keeps_left_click(self, index: int, binding: Optional[P.Binding]) -> bool:
        left = P.Binding(P.KeyClass.MOUSE, P.MOUSE_BUTTONS["left"])
        others = [self.img.binding(j) for j in range(len(BUTTON_NAMES)) if j != index]
        return binding == left or left in others

    def _apply(self) -> None:
        if self.category.currentData() is None:
            return
        snapshot = bytes(self.img.buf)
        try:
            patches = self._build_patches()
        except ValueError as exc:
            self.warning.setText(str(exc))
            self.warning.show()
            return
        if not self._keeps_left_click(self.current, self.img.binding(self.current)):
            self.img.buf[:] = snapshot  # undo the in-memory change
            self.warning.setText("Pelo menos um botão precisa continuar como clique esquerdo.")
            self.warning.show()
            return
        self.app.commit(patches, f"{BUTTON_NAMES[self.current]}: {self._describe(self.current)}")
        self.load()

    def _restore_default(self) -> None:
        if self.current >= len(DEFAULT_BINDINGS):
            return
        self.app.commit([self.img.set_binding(self.current, P.parse_binding(DEFAULT_BINDINGS[self.current]))],
                        f"{BUTTON_NAMES[self.current]} restaurado")
        self.load()


# ===========================================================================
# Lighting
# ===========================================================================

LED_MODE_LABELS = [(0, "Desligado"), (1, "Arco-íris em movimento"), (2, "Cor única"),
                   (3, "Arco-íris fixo"), (4, "Neon"), (5, "Arco-íris piscante"), (6, "Multicolorido fixo")]
DPI_EFFECT_LABELS = [(0, "Desligado"), (1, "Fixo"), (2, "Piscando")]


class LightingPage(Page):
    title = "Iluminação"
    subtitle = "Faixa de LED, indicador de DPI e economia de bateria."

    def build(self) -> None:
        bar = self.bar_card = Card("Faixa de LED")
        self.bar_mode = _combo(LED_MODE_LABELS, 230)
        self.bar_mode.activated.connect(lambda _: self._commit_bar("Efeito da faixa atualizado"))
        bar.add(setting_row("Efeito", self.bar_mode))
        self.bar_color = ColorSwatch(28)
        self.bar_color.colorPicked.connect(lambda _: self._commit_bar("Cor da faixa atualizada"))
        bar.add(setting_row("Cor", self.bar_color, "Usada pelo efeito “Cor única”."))
        self.bar_brightness = ValueSlider(1, 10)
        self.bar_brightness.committed.connect(lambda _: self._commit_bar("Brilho da faixa atualizado"))
        bar.add(setting_row("Brilho", self.bar_brightness))
        self.bar_speed = ValueSlider(1, 10)
        self.bar_speed.committed.connect(lambda _: self._commit_bar("Velocidade da faixa atualizada"))
        bar.add(setting_row("Velocidade", self.bar_speed))
        self.layout_.addWidget(bar)

        dpi = self.dpi_card = Card("Indicador de DPI", "LED que mostra a cor do estágio de DPI.")
        self.dpi_effect = _combo(DPI_EFFECT_LABELS, 230)
        self.dpi_effect.activated.connect(lambda _: self._commit_dpi_effect())
        dpi.add(setting_row("Efeito", self.dpi_effect))
        self.dpi_brightness = ValueSlider(1, 10)
        self.dpi_brightness.committed.connect(lambda v: self.app.commit(
            [self.img.set_setting("dpi-led-brightness", P.DPI_LED_BRIGHTNESS[v - 1])], "Brilho do indicador atualizado"))
        dpi.add(setting_row("Brilho", self.dpi_brightness))
        self.dpi_speed = ValueSlider(1, 5)
        self.dpi_speed.committed.connect(lambda v: self.app.commit(
            [self.img.set_setting("dpi-led-speed", v)], "Velocidade do indicador atualizada"))
        dpi.add(setting_row("Velocidade", self.dpi_speed))
        self.layout_.addWidget(dpi)

        power = self.power_card = Card("Economia de energia")
        self.move_off = ToggleSwitch()
        self.move_off.clicked.connect(lambda on: self.app.commit(
            [self.img.set_setting("move-led-off", int(on))], "Ajuste salvo"))
        power.add(setting_row("Apagar LEDs ao mover", self.move_off, "Economiza bateria durante o jogo."))
        self.off_time = _combo([(v, _seconds(v)) for v in P.LED_OFF_TIMES], 160)
        self.off_time.activated.connect(lambda _: self.app.commit(
            [self.img.set_setting("led-off-time", self.off_time.currentData())], "Tempo de desligamento salvo"))
        power.add(setting_row("Apagar LEDs após inatividade", self.off_time))
        self.layout_.addWidget(power)

    @property
    def has_content(self) -> bool:
        return any(not c.isHidden() for c in (self.bar_card, self.dpi_card, self.power_card))

    def apply_capabilities(self, model: Optional[P.Model]) -> None:
        """Show only what the official app shows for this model (all if unknown)."""
        bar = model is None or model.led_bar
        dpi = model is None or model.dpi_led
        self.bar_card.setVisible(bar)
        self.dpi_card.setVisible(dpi)
        self.power_card.setVisible(bar or dpi)

    def load(self) -> None:
        img = self.img
        snap = self.app.snapshot
        self.apply_capabilities(snap.identity.model if snap.identity else None)
        led = img.led_bar() or P.LedBar(0, (255, 255, 255), 0, 9)
        _select(self.bar_mode, led.mode if img.setting("led-bar-enable") else 0)
        self.bar_color.set_rgb(led.color)
        self.bar_brightness.set_value(led.brightness + 1)
        self.bar_speed.set_value(led.speed + 1)
        enabled = img.setting("dpi-led-enable")
        _select(self.dpi_effect, img.setting("dpi-led-mode") if enabled else 0)
        raw = img.setting("dpi-led-brightness") or 128
        level = min(range(10), key=lambda i: abs(P.DPI_LED_BRIGHTNESS[i] - raw)) + 1
        self.dpi_brightness.set_value(level)
        self.dpi_speed.set_value(min(5, max(1, img.setting("dpi-led-speed") or 3)))
        self.move_off.setChecked(bool(img.setting("move-led-off")))
        _select(self.off_time, img.setting("led-off-time"))
        self._sync_enabled()

    def _sync_enabled(self) -> None:
        bar_on = bool(self.bar_mode.currentData())
        for w in (self.bar_color, self.bar_brightness, self.bar_speed):
            w.setEnabled(bar_on)
        dpi_on = bool(self.dpi_effect.currentData())
        for w in (self.dpi_brightness, self.dpi_speed):
            w.setEnabled(dpi_on)

    def _commit_bar(self, message: str) -> None:
        self._sync_enabled()
        mode = self.bar_mode.currentData() or 0
        old = self.img.led_bar() or P.LedBar(0, (255, 255, 255), 0, 9)
        bar = P.LedBar(mode, self.bar_color._rgb, self.bar_speed.slider.value() - 1,
                       self.bar_brightness.slider.value() - 1)
        # FormMain::customComboBox_LEDMode: mode 0 also clears LedBar.enable.
        patches = [self.img.set_led_bar(bar), self.img.set_setting("led-bar-enable", int(mode > 0))]
        if bar == old:
            patches = patches[1:]
        self.app.commit(patches, message)

    def _commit_dpi_effect(self) -> None:
        self._sync_enabled()
        effect = self.dpi_effect.currentData()
        patches = [self.img.set_setting("dpi-led-enable", int(effect > 0))]
        if effect:
            patches.append(self.img.set_setting("dpi-led-mode", effect))
        self.app.commit(patches, "Efeito do indicador atualizado")


# ===========================================================================
# Sensor
# ===========================================================================

class SensorPage(Page):
    title = "Sensor"
    subtitle = "Ajustes do sensor PAW3395 e do tempo de resposta dos botões."

    def build(self) -> None:
        tracking = Card("Rastreamento")
        self.toggles = {}
        for key, title, hint in (
            ("motion-sync", "Motion Sync", "Sincroniza a leitura do sensor com o polling. Movimento mais "
                                           "consistente, com ~1 ms a mais de latência."),
            ("angle-snap", "Correção de ângulo", "Endireita movimentos quase retos. Normalmente desligado em jogos."),
            ("ripple-control", "Controle de ripple", "Suaviza o tremor em DPI alto."),
        ):
            t = ToggleSwitch()
            t.clicked.connect(lambda on, k=key, n=title: self.app.commit(
                [self.img.set_setting(k, int(on))], f"{n} {'ligado' if on else 'desligado'}"))
            self.toggles[key] = t
            tracking.add(setting_row(title, t, hint))
        tracking.add(separator())
        self.lod = Segmented([(3, "0,7 mm"), (1, "1 mm"), (2, "2 mm")])
        self.lod.changed.connect(lambda v: self.app.commit([self.img.set_setting("lod", v)], "LOD atualizado"))
        tracking.add(setting_row("Distância de levantamento (LOD)", self.lod,
                                 "Altura em que o sensor para de rastrear ao levantar o mouse."))
        self.layout_.addWidget(tracking)

        perf = Card("Modo de operação")
        self.mode = Segmented([(0, "Baixo consumo (LP)"), (1, "Alto desempenho (HP)")])
        self.mode.changed.connect(lambda v: self.app.commit(
            [self.img.set_setting("sensor-mode", v)], "Modo do sensor atualizado"))
        self.mode_hint = label("", "rowHint", wrap=True)
        mode_row = setting_row("Modo do sensor", self.mode)
        perf.add(mode_row)
        perf.add(self.mode_hint)
        self.peak = ToggleSwitch()
        self.peak.clicked.connect(self._commit_peak)
        perf.add(setting_row("Desempenho máximo", self.peak,
                             "Mantém o sensor no modo de maior desempenho pelo tempo escolhido."))
        self.peak_time = _combo([(v, _seconds(v)) for v in P.PEAK_TIMES], 140)
        self.peak_time.activated.connect(lambda _: self.app.commit(
            [self.img.set_setting("peak-time", self.peak_time.currentData())], "Duração salva"))
        perf.add(setting_row("Duração", self.peak_time))
        self.layout_.addWidget(perf)

        buttons = Card("Botões")
        self.debounce = ValueSlider(*P.DEBOUNCE_RANGE, fmt=lambda v: f"{v} ms")
        self.debounce.committed.connect(lambda v: self.app.commit(
            [self.img.set_setting("debounce", v)], f"Debounce: {v} ms"))
        buttons.add(setting_row("Tempo de debounce", self.debounce))
        buttons.add(label("Valores baixos deixam o clique mais rápido, mas podem causar clique duplo. "
                          "Se acontecer, aumente até parar.", "rowHint", wrap=True))
        self.layout_.addWidget(buttons)

    def load(self) -> None:
        img = self.img
        for key, t in self.toggles.items():
            t.setChecked(bool(img.setting(key)))
        self.lod.set_value(img.setting("lod"))
        # _3In1::UpdateModeSelect: on a cable or at >= 2000 Hz the official app
        # shows "Corded" and locks the selector.
        ident = self.app.snapshot.identity
        wired = ident is not None and not ident.link[1]
        corded = wired or (img.setting("report-rate") or 0) >= P.CORDED_MODE_RATE
        self.mode.setEnabled(not corded)
        self.mode.set_value(None if corded else img.setting("sensor-mode"))
        self.mode_hint.setText("Com cabo ou em 2000 Hz ou mais, o sensor usa o modo Corded (jogo) automaticamente."
                               if corded else "")
        self.mode_hint.setVisible(corded)
        self.peak.setChecked(bool(img.setting("peak-performance")))
        _select(self.peak_time, img.setting("peak-time"))
        self.peak_time.setEnabled(self.peak.isChecked())
        self.debounce.set_value(img.setting("debounce") or 0)

    def _commit_peak(self, on: bool) -> None:
        self.peak_time.setEnabled(on)
        patches = [self.img.set_setting("peak-performance", int(on))]
        if on and self.peak_time.currentData() is None:
            _select(self.peak_time, 3)
            patches.append(self.img.set_setting("peak-time", 3))
        self.app.commit(patches, f"Desempenho máximo {'ligado' if on else 'desligado'}")


# ===========================================================================
# Device
# ===========================================================================

class DevicePage(Page):
    title = "Dispositivo"
    subtitle = "Informações, conexão sem fio, backup e manutenção."

    def build(self) -> None:
        info = Card("Informações")
        grid = QGridLayout()
        grid.setHorizontalSpacing(30)
        grid.setVerticalSpacing(12)
        self.fields = {}
        for i, (key, title) in enumerate((("model", "Modelo"), ("product", "Receptor / cabo"),
                                          ("link", "Conexão"), ("firmware", "Firmware do mouse"),
                                          ("battery", "Bateria"), ("sensor", "Sensor"))):
            grid.addWidget(label(title, "hint"), (i // 3) * 2, i % 3)
            value = label("—", "value")
            self.fields[key] = value
            grid.addWidget(value, (i // 3) * 2 + 1, i % 3)
        info.add(grid)
        self.layout_.addWidget(info)

        wireless = Card("Conexão sem fio")
        self.long_range = ToggleSwitch()
        self.long_range.clicked.connect(self._set_long_range)
        wireless.add(setting_row("Modo longa distância", self.long_range,
                                 "Mais alcance e resistência a interferência, com consumo maior de bateria."))
        self.layout_.addWidget(wireless)

        backup = Card("Backup", "Salve a configuração do mouse em um arquivo e restaure quando quiser.")
        row = QHBoxLayout()
        export = QPushButton("Exportar configuração…")
        export.clicked.connect(self._export)
        restore = QPushButton("Importar configuração…")
        restore.clicked.connect(self._import)
        row.addWidget(export)
        row.addWidget(restore)
        row.addStretch(1)
        backup.add(row)
        self.layout_.addWidget(backup)

        maint = Card("Manutenção")
        test = QPushButton("Executar autoteste")
        test.clicked.connect(self._selftest)
        maint.add(setting_row("Autoteste", test, "Grava e restaura um estágio e um botão não usados "
                                                  "para confirmar que a comunicação funciona."))
        self.selftest_result = label("", "rowHint", wrap=True)
        self.selftest_result.hide()
        maint.add(self.selftest_result)
        maint.add(separator())
        reset = QPushButton("Restaurar padrões de fábrica")
        reset.setObjectName("danger")
        reset.clicked.connect(self._factory_reset)
        maint.add(setting_row("Padrões de fábrica", reset, "Apaga DPI, botões e iluminação personalizados."))
        self.layout_.addWidget(maint)

    def load(self) -> None:
        snap = self.app.snapshot
        ident = snap.identity
        model = ident.model if ident else None
        self.fields["model"].setText(model_name(snap))
        self.fields["product"].setText(f"{snap.info.product or 'LAMZU'}  ·  0x{snap.info.product_id:04X}")
        if ident:
            wireless = ident.link[1]
            self.fields["link"].setText(f"{'Sem fio' if wireless else 'Cabo'}  ·  até {ident.max_rate} Hz")
        else:
            self.fields["link"].setText("—")
        self.fields["firmware"].setText(snap.firmware or "—")
        bat = self.app.battery
        if bat:
            self.fields["battery"].setText(f"{bat.level}%  ·  {bat.millivolts / 1000:.2f} V"
                                           f"{'  (carregando)' if bat.charging else ''}")
        self.fields["sensor"].setText(model.sensor if model else "PixArt PAW3395 (presumido)")
        self.long_range.setEnabled(snap.long_range is not None)
        self.long_range.setChecked(bool(snap.long_range))

    def _set_long_range(self, on: bool) -> None:
        def job(w):
            w.device.set_long_range(on)
            return w.device.long_range()
        self.app.run_job(job, lambda r: self.app.toast.show_message(
            f"Longa distância {'ligada' if r else 'desligada'}"))

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar configuração", "lamzu-config.bin",
                                              "Configuração LAMZU (*.bin)")
        if not path:
            return

        def done(data: bytes) -> None:
            with open(path, "wb") as fh:
                fh.write(data)
            self.app.toast.show_message("Configuração exportada")
        self.app.run_job(lambda w: w.device.read_flash(0, FULL_SIZE), done)

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar configuração", "", "Configuração LAMZU (*.bin)")
        if not path:
            return
        with open(path, "rb") as fh:
            data = fh.read()
        img = P.FlashImage(data)
        if len(data) not in (P.CONFIG_SIZE, FULL_SIZE) or img.setting("report-rate") is None \
                or img.dpi_stage(0).dpi is None:
            QMessageBox.warning(self, "Importar configuração", "O arquivo não parece ser uma "
                                "configuração LAMZU válida.")
            return
        if QMessageBox.question(self, "Importar configuração",
                                "Substituir toda a configuração do mouse por este arquivo?") \
                != QMessageBox.StandardButton.Yes:
            return
        patches = [P.Patch(0, data[:P.CONFIG_SIZE])]
        if len(data) == FULL_SIZE:
            patches.append(P.Patch(P.SHORTCUTS, data[P.SHORTCUTS:]))
        self.app.run_job(lambda w: w.device.apply(patches),
                         lambda _: (self.app.toast.show_message("Configuração importada"), self.app.reload()))

    def _selftest(self) -> None:
        self.selftest_result.setText("Executando…")
        self.selftest_result.show()

        def done(results) -> None:
            ok = all(r for _, r in results)
            lines = "  ·  ".join(f"{'✓' if r else '✗'} {name}" for name, r in results)
            color = T.SUCCESS if ok else T.DANGER
            self.selftest_result.setText(f"<span style='color:{color}'>{'Tudo certo' if ok else 'Falhou'}</span>"
                                         f" — {lines}")
            self.app.toast.show_message("Autoteste concluído" if ok else "Autoteste falhou",
                                        "ok" if ok else "error")
        self.app.run_job(lambda w: run_selftest(w.device), done)

    def _factory_reset(self) -> None:
        if QMessageBox.question(self, "Padrões de fábrica",
                                "Restaurar todas as configurações do mouse para o padrão de fábrica?") \
                != QMessageBox.StandardButton.Yes:
            return
        self.app.run_job(lambda w: w.device.reset_settings(),
                         lambda _: (self.app.toast.show_message("Padrões de fábrica restaurados"),
                                    self.app.reload()))
