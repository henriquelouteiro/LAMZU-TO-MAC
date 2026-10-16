"""LAMZU configuration protocol (pure encoding/decoding, no I/O).

Recovered from LAMZU "Mouse Drive Beta" 1.6.0.43 for Windows: the .NET UI
(Mouse Drive Beta.exe) and its embedded native layer HIDUsb.dll.
Every constant below is traced in docs/PROTOCOL.md.

Wire format (one HID report, ID 0x08, 17 bytes in both directions):

    [0] 0x08 report id      [3] address hi     [6..15] payload (10 bytes)
    [1] command             [4] address lo     [16]    checksum
    [2] status (0)          [5] length

    checksum = (0x55 - sum(bytes[0..15])) & 0xFF
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional, Sequence, Tuple

VENDOR_ID = 0x3554
REPORT_ID = 0x08
REPORT_LEN = 17
PAYLOAD_LEN = 10

# The command channel is the vendor collection on interface 1 (UP 0xFF02, U 0x02).
CONFIG_INTERFACE = 1
CONFIG_USAGE_PAGE = 0xFF02
CONFIG_USAGE = 0x02

# Product IDs from Config.ini (M_PID / D_PID, base64-decoded).
PRODUCT_IDS: Dict[int, str] = {
    0xF50F: "wired",
    0xF50D: "receiver",
    0xF510: "4K receiver",
    0xF517: "receiver",
}


class Cmd(IntEnum):
    """DriverLib.UsbCommandID (values match the opcodes HIDUsb.dll emits)."""

    ENCRYPTION_DATA = 0x01
    PC_DRIVER_STATUS = 0x02
    DEVICE_ONLINE = 0x03
    BATTERY_LEVEL = 0x04
    DONGLE_ENTER_PAIR = 0x05
    GET_PAIR_STATE = 0x06
    WRITE_FLASH = 0x07
    READ_FLASH = 0x08
    CLEAR_SETTING = 0x09
    STATUS_CHANGED = 0x0A
    SET_VID_PID = 0x0B
    SET_DESCRIPTOR_STRING = 0x0C
    ENTER_USB_UPDATE_MODE = 0x0D
    GET_CURRENT_CONFIG = 0x0E
    SET_CURRENT_CONFIG = 0x0F
    READ_CID_MID = 0x10
    ENTER_MTK_MODE = 0x11
    READ_VERSION = 0x12
    SET_DONGLE_RGB = 0x14
    GET_DONGLE_RGB = 0x15
    SET_LONG_RANGE_MODE = 0x16
    GET_LONG_RANGE_MODE = 0x17


class ProtocolError(Exception):
    pass


def checksum(data: Sequence[int]) -> int:
    return (0x55 - sum(data)) & 0xFF


@dataclass(frozen=True)
class Report:
    cmd: int
    status: int
    address: int
    length: int
    payload: bytes
    raw: bytes


def build_report(cmd: int, address: int = 0, length: int = 0, payload: bytes = b"") -> bytes:
    if len(payload) > PAYLOAD_LEN:
        raise ValueError("payload is limited to 10 bytes per report")
    buf = bytearray(REPORT_LEN)
    buf[0] = REPORT_ID
    buf[1] = cmd
    buf[3] = (address >> 8) & 0xFF
    buf[4] = address & 0xFF
    buf[5] = length
    buf[6:6 + len(payload)] = payload
    buf[16] = checksum(buf[:16])
    return bytes(buf)


def parse_report(raw: Sequence[int]) -> Report:
    raw = bytes(raw)
    if len(raw) < REPORT_LEN or raw[0] != REPORT_ID:
        raise ProtocolError(f"unexpected report: {raw.hex(' ')}")
    raw = raw[:REPORT_LEN]
    if checksum(raw[:16]) != raw[16]:
        raise ProtocolError(f"bad checksum: {raw.hex(' ')}")
    return Report(raw[1], raw[2], (raw[3] << 8) | raw[4], raw[5], raw[6:16], raw)


def read_flash_requests(address: int, length: int) -> List[bytes]:
    """UsbServer_ReadFalshData: split into reads of at most 10 bytes."""
    out = []
    while length > 0:
        n = min(PAYLOAD_LEN, length)
        out.append(build_report(Cmd.READ_FLASH, address, n))
        address += n
        length -= n
    return out


def write_flash_requests(address: int, data: bytes) -> List[bytes]:
    """ProtocolDataUpdate / 0x180007830: split into writes of at most 10 bytes."""
    return [
        build_report(Cmd.WRITE_FLASH, address + off, len(data[off:off + PAYLOAD_LEN]),
                     data[off:off + PAYLOAD_LEN])
        for off in range(0, len(data), PAYLOAD_LEN)
    ]


# --------------------------------------------------------------------------
# Flash layout (addresses in the mouse's configuration flash)
# --------------------------------------------------------------------------

CONFIG_SIZE = 0xC0           # UsbServer_ReadAllFlashData reads 0x00..0xBF
DPI_VALUES = 0x0C            # 8 x [x, y, ex, chk]
DPI_COLORS = 0x2C            # 8 x [r, g, b, chk]
DPI_STAGES = 8
KEYS = 0x60                  # 16 x [type, param1, param2, chk]
KEY_COUNT = 16
LED_BAR = 0xA0               # [mode, r, g, b, speed, brightness, chk]
SHORTCUTS = 0x100            # 16 x 0x20 bytes
SHORTCUT_STRIDE = 0x20
MACROS = 0x300               # 16 x 0x180 bytes (not implemented)
MACRO_STRIDE = 0x180


@dataclass(frozen=True)
class Setting:
    key: str          # CLI name
    address: int
    field: str        # DriverLib.MouseConfig / DPILed / LedBar field name
    help: str


# Single-byte values stored as [value, 0x55 - value] (MouseConfigParser,
# ProtocolDataParser). Order follows DriverLib.MouseConfig.
SETTINGS: List[Setting] = [
    Setting("report-rate", 0x00, "reportRate", "polling-rate code (see REPORT_RATES)"),
    Setting("dpi-stages", 0x02, "maxDPI", "number of enabled DPI stages (1-8)"),
    Setting("dpi-active", 0x04, "currentDPI", "active DPI stage index (0-based)"),
    Setting("spindown-x", 0x06, "xSpindown", "not exposed by the official UI"),
    Setting("spindown-y", 0x08, "ySpindown", "not exposed by the official UI"),
    Setting("lod", 0x0A, "silenceHeight", "lift-off distance: 3 = 0.7 mm, 1 = 1 mm, 2 = 2 mm"),
    Setting("dpi-led-mode", 0x4C, "DPILed.mode", "DPI LED effect: 1 fixed, 2 flicker"),
    Setting("dpi-led-brightness", 0x4E, "DPILed.brightness", "DPI LED brightness (see DPI_LED_BRIGHTNESS)"),
    Setting("dpi-led-speed", 0x50, "DPILed.breathSpeed", "DPI LED speed 1-5"),
    Setting("dpi-led-enable", 0x52, "DPILed.enable", "DPI LED on/off"),
    Setting("led-bar-enable", 0xA7, "LedBar.enable", "LED bar on/off"),
    Setting("debounce", 0xA9, "keyDebounceTime", "button debounce 0-20 ms"),
    Setting("motion-sync", 0xAB, "motionSyncEnable", "motion sync on/off"),
    Setting("led-off-time", 0xAD, "allLedOffTime", "LEDs off after idle, in 10 s units"),
    Setting("angle-snap", 0xAF, "linearCorrectionEnable", "angle snapping on/off"),
    Setting("ripple-control", 0xB1, "rippleControlEnable", "ripple control on/off"),
    Setting("move-led-off", 0xB3, "moveOffLedEnable", "LEDs off while moving"),
    Setting("peak-performance", 0xB5, "sensorCustomSleepTimeEnable", "peak performance on/off"),
    Setting("peak-time", 0xB7, "sensorSleepTime", "peak performance duration, in 10 s units"),
    Setting("sensor-mode", 0xB9, "sensorPowerSavingModeEnable", "sensor mode: 0 LP, 1 HP"),
]
SETTINGS_BY_KEY = {s.key: s for s in SETTINGS}

# Option values offered by the official UI (Language/0-English.xml ComboBox items,
# mapped to fields through the _3In1 / FormMain handlers).
LOD_VALUES = (3, 1, 2)                              # 0.7 mm, 1 mm, 2 mm
SENSOR_MODES = (0, 1)                               # LP, HP
PEAK_TIMES = (3, 6, 12, 30, 60, 90)                 # x 10 s
LED_OFF_TIMES = (1, 3, 6, 30, 60, 90, 120, 150, 180, 210, 240)   # x 10 s
LED_BAR_MODES = (0, 1, 2, 3, 4, 5, 6)               # 0 = off (LedBar.enable = 0)
DPI_LED_EFFECTS = (0, 1, 2)                         # off, fixed, flicker
DEBOUNCE_RANGE = (0, 20)
# ValueConvert::DPIIndexToBrightness: slider level 1..10 -> stored byte.
DPI_LED_BRIGHTNESS = (16, 30, 60, 90, 128, 150, 180, 210, 230, 255)

# Tags of the _3In1 report-rate radio buttons (DriverLib.REPORT_RATE lacks 8000).
REPORT_RATES: Dict[int, int] = {1: 1000, 2: 500, 4: 250, 8: 125, 0x10: 2000, 0x20: 4000, 0x40: 8000}
REPORT_RATE_CODES = {hz: code for code, hz in REPORT_RATES.items()}
CORDED_MODE_RATE = 0x10   # _3In1::UpdateReportRateUI: >= 2000 Hz forces "Corded" sensor mode


# --------------------------------------------------------------------------
# Device identification (CS_UsbFinder_GetDeviceInfo -> EncryptionData reply)
# --------------------------------------------------------------------------

LAMZU_CID = 11   # Config.ini CID=TEFNWlUxMQ== -> "LAMZU11"

# Mouse_Drive_Beta.DeviceType -> (label, wireless, max polling rate of the link)
DEVICE_TYPES: Dict[int, Tuple[str, bool, int]] = {
    0: ("receiver 1K", True, 1000),
    1: ("receiver 4K", True, 4000),
    2: ("cable 1K", False, 1000),
    3: ("cable 8K", False, 8000),
    4: ("receiver 2K", True, 2000),
    5: ("receiver 8K", True, 8000),
}


@dataclass(frozen=True)
class Model:
    mid: int
    name: str
    max_rate: int        # SensorUI[0]: 6 -> up to 4000 Hz, 7 -> up to 8000 Hz
    dpi_led: bool        # SensorUI[2]: DPI LED effect panel shown
    led_bar: bool        # DisplayLight: lighting section shown
    sensor: str = "PixArt PAW3395"


# Config.ini [Device1..6] of Mouse Drive Beta 1.6.0.43.
MODELS: Dict[int, Model] = {m.mid: m for m in (
    Model(1, "Atlantis OG V2", 8000, False, False),
    Model(2, "Atlantis Mini", 8000, False, False),
    Model(3, "Thorn", 8000, True, False),
    Model(4, "Maya", 8000, False, False),
    Model(5, "Paro", 4000, False, False),
    Model(9, "Atlantis Nordic-R'lyeh", 4000, False, False),
)}


@dataclass(frozen=True)
class Identity:
    cid: int
    mid: int
    device_type: int

    @property
    def is_lamzu(self) -> bool:
        return self.cid == LAMZU_CID

    @property
    def model(self) -> Optional[Model]:
        return MODELS.get(self.mid) if self.is_lamzu else None

    @property
    def link(self) -> Tuple[str, bool, int]:
        return DEVICE_TYPES.get(self.device_type, (f"type {self.device_type}", True, 1000))

    @property
    def max_rate(self) -> int:
        model = self.model
        return min(self.link[2], model.max_rate if model else 8000)

    def rates(self) -> List[int]:
        return sorted(hz for hz in REPORT_RATE_CODES if hz <= self.max_rate)


def identify_request(challenge: bytes) -> bytes:
    """0x18000f160: length 8 and a 4-byte random challenge."""
    return build_report(Cmd.ENCRYPTION_DATA, length=8, payload=challenge[:4])


def parse_identity(reply: Report) -> Identity:
    """GetDeviceInfo (0x180006fa0) reads CID, MID and DeviceType at payload 4..6."""
    return Identity(reply.payload[4], reply.payload[5], reply.payload[6])


# --------------------------------------------------------------------------
# DPI value codec (DPIControl::ValueToDPI / UpdateUI, sensor 3395 path)
# --------------------------------------------------------------------------

DPI_MIN, DPI_MAX, DPI_STEP = 50, 26000, 50   # Config.ini DPIRange


def encode_dpi(dpi: int) -> Tuple[int, int, int]:
    if not DPI_MIN <= dpi <= DPI_MAX or dpi % DPI_STEP:
        raise ValueError(f"DPI must be {DPI_MIN}-{DPI_MAX} in steps of {DPI_STEP}")
    raw = dpi // 50 - 1
    hi = raw >> 8
    return raw & 0xFF, raw & 0xFF, ((hi << 2) | (hi << 6)) & 0xFF


def decode_dpi(x: int, ex: int) -> int:
    raw = x | (((ex >> 6) & 0x03) << 8)
    dpi = (raw + 1) * (100 if ex & 0x22 else 50)
    return dpi * 2 if ex & 0x11 else dpi


# --------------------------------------------------------------------------
# Button bindings (DriverLib.KEY_CLASS and KeyFunMapDriver setters)
# --------------------------------------------------------------------------

class KeyClass(IntEnum):
    DISABLED = 0
    MOUSE = 1
    DPI = 2
    HSCROLL = 3
    FIRE = 4
    SHORTCUT = 5
    MACRO = 6
    REPORT_RATE_CYCLE = 7
    LED_SWITCH = 8
    PROFILE_SWITCH = 9
    DPI_LOCK = 10
    VSCROLL = 11       # absent from KEY_CLASS; Language/*.xml KeyFunction type "0B"


MOUSE_BUTTONS = {"left": 0x01, "right": 0x02, "middle": 0x04, "back": 0x08, "forward": 0x10}
DPI_ACTIONS = {"dpi-cycle": 1, "dpi-up": 2, "dpi-down": 3}
HSCROLL_ACTIONS = {"scroll-left": 1, "scroll-right": 2}
VSCROLL_ACTIONS = {"scroll-up": 1, "scroll-down": 2}
LED_ACTIONS = {"lights-toggle": 0, "lightbar-toggle": 3, "light-effect-cycle": 4}

FIRE_INTERVAL = (10, 255)   # Dialog/FireKeyInterval
FIRE_TIMES = (0, 3)         # Dialog/FireKeyTimes; 0 = repeat while held


@dataclass(frozen=True)
class Binding:
    type: int
    param1: int = 0
    param2: int = 0

    def describe(self) -> str:
        t, p1, p2 = self.type, self.param1, self.param2
        for name, p in _ACTION_TABLES.get(t, {}).items():
            if p == p1:
                return name
        if t in _SIMPLE_ACTIONS:
            return _SIMPLE_ACTIONS[t]
        if t == KeyClass.FIRE:
            return f"fire:{p1}:{p2}"
        if t == KeyClass.DPI_LOCK:
            return f"dpi-lock:{(p1 + 1) * 50}"
        try:
            name = KeyClass(t).name.lower().replace("_", "-")
        except ValueError:
            name = f"type{t}"
        return f"{name}({p1},{p2})"


_ACTION_TABLES = {
    KeyClass.MOUSE: MOUSE_BUTTONS,
    KeyClass.DPI: DPI_ACTIONS,
    KeyClass.HSCROLL: HSCROLL_ACTIONS,
    KeyClass.VSCROLL: VSCROLL_ACTIONS,
    KeyClass.LED_SWITCH: LED_ACTIONS,
}
_SIMPLE_ACTIONS = {
    KeyClass.DISABLED: "disabled",
    KeyClass.SHORTCUT: "shortcut",
    KeyClass.REPORT_RATE_CYCLE: "rate-cycle",
    KeyClass.PROFILE_SWITCH: "profile-switch",
}


def parse_binding(spec: str) -> Binding:
    """Parse a CLI action such as 'back', 'dpi-up', 'fire:10:3', 'disabled'."""
    for key_class, table in _ACTION_TABLES.items():
        if spec in table:
            return Binding(key_class, table[spec])
    for key_class, name in _SIMPLE_ACTIONS.items():
        if spec == name and key_class != KeyClass.SHORTCUT:
            return Binding(key_class)
    if spec.startswith("fire:"):
        _, interval, times = spec.split(":")
        return fire_binding(int(interval, 0), int(times, 0))
    if spec.startswith("dpi-lock:"):
        return dpi_lock_binding(int(spec.split(":")[1], 0))
    raise ValueError(f"unknown action: {spec}")


def fire_binding(interval: int, times: int) -> Binding:
    if not FIRE_INTERVAL[0] <= interval <= FIRE_INTERVAL[1]:
        raise ValueError("fire interval must be 10-255")
    if not FIRE_TIMES[0] <= times <= FIRE_TIMES[1]:
        raise ValueError("fire repeat count must be 0-3")
    return Binding(KeyClass.FIRE, interval, times)


def dpi_lock_binding(dpi: int) -> Binding:
    """SubKeyFunction type 0A: 100 -> 1, 200 -> 3, ... i.e. dpi / 50 - 1."""
    encode_dpi(dpi)
    if dpi // 50 - 1 > 0xFF:
        raise ValueError("DPI lock supports up to 12800 DPI")
    return Binding(KeyClass.DPI_LOCK, dpi // 50 - 1)


# --------------------------------------------------------------------------
# Keyboard shortcuts (ShortcutKeyToBuffer / ShortCutKeyDriver::AddShortCutKey)
# --------------------------------------------------------------------------

class HidCodeType(IntEnum):
    MODIFIER = 0     # value is a modifier bitmask
    KEY = 1          # value is a HID keyboard usage
    MEDIA = 2        # value is a HID consumer usage


KEY_DOWN, KEY_UP = 0x80, 0x40

MODIFIERS = {
    "ctrl": 0x01, "shift": 0x02, "alt": 0x04, "opt": 0x04, "cmd": 0x08, "win": 0x08, "gui": 0x08,
    "rctrl": 0x10, "rshift": 0x20, "ralt": 0x40, "rcmd": 0x80,
}
# Consumer usages offered by the official app (Language/*.xml SubKeyFunction type 05).
MEDIA_KEYS = {
    "play": 0xCD, "next": 0xB5, "prev": 0xB6, "stop": 0xB7,
    "mute": 0xE2, "vol-up": 0xE9, "vol-down": 0xEA, "media-player": 0x183,
    "email": 0x18A, "calculator": 0x192, "my-computer": 0x194,
    "browser-search": 0x221, "browser-home": 0x223, "browser-back": 0x224,
    "browser-forward": 0x225, "browser-stop": 0x226, "browser-refresh": 0x227,
    "browser-favorites": 0x22A,
}
MEDIA_NAMES = {v: k for k, v in MEDIA_KEYS.items()}
_NAMED_KEYS = {
    "enter": 0x28, "esc": 0x29, "backspace": 0x2A, "tab": 0x2B, "space": 0x2C,
    "minus": 0x2D, "equal": 0x2E, "lbracket": 0x2F, "rbracket": 0x30, "backslash": 0x31,
    "semicolon": 0x33, "quote": 0x34, "grave": 0x35, "comma": 0x36, "period": 0x37,
    "slash": 0x38, "capslock": 0x39, "printscreen": 0x46, "scrolllock": 0x47, "pause": 0x48,
    "insert": 0x49, "home": 0x4A, "pageup": 0x4B, "delete": 0x4C, "end": 0x4D,
    "pagedown": 0x4E, "right": 0x4F, "left": 0x50, "down": 0x51, "up": 0x52,
}


def keyboard_usage(name: str) -> int:
    name = name.lower()
    if len(name) == 1 and "a" <= name <= "z":
        return 0x04 + ord(name) - ord("a")
    if len(name) == 1 and "1" <= name <= "9":
        return 0x1E + ord(name) - ord("1")
    if name == "0":
        return 0x27
    if name.startswith("f") and name[1:].isdigit() and 1 <= int(name[1:]) <= 12:
        return 0x3A + int(name[1:]) - 1
    if name in _NAMED_KEYS:
        return _NAMED_KEYS[name]
    raise ValueError(f"unknown key: {name}")


ShortcutEvent = Tuple[int, int, int]  # (KEY_DOWN|KEY_UP, HidCodeType, value)


def parse_shortcut(spec: str) -> List[ShortcutEvent]:
    """'cmd+c' -> press modifiers and key in order, release in reverse order."""
    parts = [p for p in spec.lower().split("+") if p]
    if len(parts) == 1 and parts[0] in MEDIA_KEYS:
        code = MEDIA_KEYS[parts[0]]
        return [(KEY_DOWN, HidCodeType.MEDIA, code), (KEY_UP, HidCodeType.MEDIA, code)]
    presses: List[Tuple[int, int]] = []
    for p in parts:
        if p in MODIFIERS:
            presses.append((HidCodeType.MODIFIER, MODIFIERS[p]))
        else:
            presses.append((HidCodeType.KEY, keyboard_usage(p)))
    if not 1 <= len(presses) <= 3:
        raise ValueError("a shortcut holds 1-3 keys (6 events)")
    return [(KEY_DOWN, t, v) for t, v in presses] + [(KEY_UP, t, v) for t, v in reversed(presses)]


_MODIFIER_LABELS = {0x01: "Ctrl", 0x02: "Shift", 0x04: "Alt", 0x08: "Cmd",
                    0x10: "RCtrl", 0x20: "RShift", 0x40: "RAlt", 0x80: "RCmd"}
_KEY_LABELS = {v: k.capitalize() for k, v in _NAMED_KEYS.items()}
_KEY_LABELS.update({0x04 + i: chr(ord("A") + i) for i in range(26)})
_KEY_LABELS.update({0x1E + i: str(i + 1) for i in range(9)})
_KEY_LABELS.update({0x27: "0"})
_KEY_LABELS.update({0x3A + i: f"F{i + 1}" for i in range(12)})


def format_shortcut(events: Sequence[ShortcutEvent]) -> str:
    """Human-readable form of the pressed keys, e.g. 'Ctrl+Shift+T' or 'mute'."""
    parts = []
    for state, kind, value in events:
        if state != KEY_DOWN:
            continue
        if kind == HidCodeType.MEDIA:
            parts.append(MEDIA_NAMES.get(value, f"media 0x{value:03x}"))
        elif kind == HidCodeType.MODIFIER:
            parts.extend(label for bit, label in _MODIFIER_LABELS.items() if value & bit)
        else:
            parts.append(_KEY_LABELS.get(value, f"key 0x{value:02x}"))
    return "+".join(parts)


def encode_shortcut(events: Sequence[ShortcutEvent]) -> bytes:
    if not 2 <= len(events) <= 6:
        raise ValueError("shortcut must contain 2-6 events")
    buf = bytearray([len(events)])
    for state, kind, value in events:
        buf += bytes([state | (kind & 0x0F), value & 0xFF, (value >> 8) & 0xFF])
    buf.append(checksum(buf))
    return bytes(buf)


def decode_shortcut(buf: bytes) -> Optional[List[ShortcutEvent]]:
    n = buf[0]
    if not 2 <= n <= 6 or checksum(buf[:1 + 3 * n]) != buf[1 + 3 * n]:
        return None
    events = []
    for i in range(n):
        flag, lo, hi = buf[1 + 3 * i:4 + 3 * i]
        events.append((flag & 0xC0, flag & 0x0F, lo | (hi << 8)))
    return events


# --------------------------------------------------------------------------
# Flash image with checksum-aware accessors
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Patch:
    address: int
    data: bytes


@dataclass(frozen=True)
class DpiStage:
    dpi: Optional[int]
    color: Optional[Tuple[int, int, int]]


@dataclass(frozen=True)
class LedBar:
    mode: int
    color: Tuple[int, int, int]
    speed: int
    brightness: int


class FlashImage:
    """In-memory copy of the configuration flash. Setters return the Patch
    that must be written to the device and keep the image in sync."""

    def __init__(self, data: bytes):
        self.buf = bytearray(data)

    # -- primitive encodings -------------------------------------------------
    def get_pair(self, address: int) -> Optional[int]:
        v, c = self.buf[address], self.buf[address + 1]
        return v if (v + c) & 0xFF == 0x55 else None

    def set_pair(self, address: int, value: int) -> Patch:
        if not 0 <= value <= 0xFF:
            raise ValueError("value must fit in one byte")
        return self._store(address, bytes([value, (0x55 - value) & 0xFF]))

    def get_block(self, address: int, size: int) -> Optional[bytes]:
        data = bytes(self.buf[address:address + size])
        return data if checksum(data) == self.buf[address + size] else None

    def set_block(self, address: int, data: bytes) -> Patch:
        return self._store(address, bytes(data) + bytes([checksum(data)]))

    def _store(self, address: int, data: bytes) -> Patch:
        end = address + len(data)
        if end > len(self.buf):
            self.buf.extend(bytes(end - len(self.buf)))
        self.buf[address:end] = data
        return Patch(address, data)

    # -- typed accessors -----------------------------------------------------
    def setting(self, key: str) -> Optional[int]:
        return self.get_pair(SETTINGS_BY_KEY[key].address)

    def set_setting(self, key: str, value: int) -> Patch:
        return self.set_pair(SETTINGS_BY_KEY[key].address, value)

    def dpi_stage(self, index: int) -> DpiStage:
        v = self.get_block(DPI_VALUES + 4 * index, 3)
        c = self.get_block(DPI_COLORS + 4 * index, 3)
        return DpiStage(decode_dpi(v[0], v[2]) if v else None, tuple(c) if c else None)

    def set_dpi(self, index: int, dpi: int) -> Patch:
        self._check_stage(index)
        return self.set_block(DPI_VALUES + 4 * index, bytes(encode_dpi(dpi)))

    def set_dpi_color(self, index: int, rgb: Tuple[int, int, int]) -> Patch:
        self._check_stage(index)
        return self.set_block(DPI_COLORS + 4 * index, bytes(rgb))

    def binding(self, index: int) -> Optional[Binding]:
        b = self.get_block(KEYS + 4 * index, 3)
        return Binding(*b) if b else None

    def set_binding(self, index: int, binding: Binding) -> Patch:
        if not 0 <= index < KEY_COUNT:
            raise ValueError(f"button index must be 0-{KEY_COUNT - 1}")
        return self.set_block(KEYS + 4 * index, bytes([binding.type, binding.param1, binding.param2]))

    def led_bar(self) -> Optional[LedBar]:
        b = self.get_block(LED_BAR, 6)
        return LedBar(b[0], (b[1], b[2], b[3]), b[4], b[5]) if b else None

    def set_led_bar(self, bar: LedBar) -> Patch:
        return self.set_block(LED_BAR, bytes([bar.mode, *bar.color, bar.speed, bar.brightness]))

    def shortcut(self, index: int) -> Optional[List[ShortcutEvent]]:
        start = SHORTCUTS + SHORTCUT_STRIDE * index
        if len(self.buf) < start + SHORTCUT_STRIDE:
            return None
        return decode_shortcut(bytes(self.buf[start:start + SHORTCUT_STRIDE]))

    def set_shortcut(self, index: int, events: Sequence[ShortcutEvent]) -> List[Patch]:
        return [
            self._store(SHORTCUTS + SHORTCUT_STRIDE * index, encode_shortcut(events)),
            self.set_binding(index, Binding(KeyClass.SHORTCUT)),
        ]

    @staticmethod
    def _check_stage(index: int) -> None:
        if not 0 <= index < DPI_STAGES:
            raise ValueError(f"DPI stage must be 0-{DPI_STAGES - 1}")


def patch_requests(patches: Sequence[Patch]) -> List[bytes]:
    out: List[bytes] = []
    for p in patches:
        out += write_flash_requests(p.address, p.data)
    return out
