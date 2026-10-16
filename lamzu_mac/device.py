"""hidapi transport for the LAMZU configuration channel.

Mirrors the request loop in HIDUsb.dll (thread at 0x180012190): one request in
flight, >= 8 ms between writes, up to 5 attempts, 1 s timeout (5 s for
CLEAR_SETTING), and a write is acknowledged only by an identical echo.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

from .protocol import (
    CONFIG_INTERFACE, CONFIG_SIZE, CONFIG_USAGE, CONFIG_USAGE_PAGE, KEY_COUNT, PRODUCT_IDS,
    SHORTCUT_STRIDE, SHORTCUTS, VENDOR_ID,
    Cmd, FlashImage, Identity, Patch, ProtocolError, Report, build_report, identify_request,
    parse_identity, parse_report, patch_requests, read_flash_requests,
)

MIN_GAP_S = 0.008
ATTEMPTS = 5


def _hid():
    try:
        import hid  # provided by the "hidapi" package
    except ImportError as exc:  # pragma: no cover - environment specific
        raise SystemExit("hidapi is missing: python3 -m pip install hidapi") from exc
    return hid


@dataclass(frozen=True)
class DeviceInfo:
    path: bytes
    product_id: int
    product: str
    serial: str

    @property
    def known(self) -> bool:
        return self.product_id in PRODUCT_IDS

    @property
    def kind(self) -> str:
        return PRODUCT_IDS.get(self.product_id, "unknown PID")


@dataclass(frozen=True)
class Battery:
    level: int
    charging: bool
    millivolts: int


def find_devices() -> List[DeviceInfo]:
    """Config channels of VID 0x3554 devices, known LAMZU PIDs first.

    VID 0x3554 belongs to the chip vendor (Compx) and other brands use it too,
    so devices with an unknown PID must be confirmed with identify() before
    being configured."""
    found = []
    for d in _hid().enumerate(VENDOR_ID):
        # macOS and Windows report the usage page; fall back to the interface
        # number on platforms where hidapi leaves it at zero.
        if d["usage_page"]:
            if (d["usage_page"], d["usage"]) != (CONFIG_USAGE_PAGE, CONFIG_USAGE):
                continue
        elif d["interface_number"] != CONFIG_INTERFACE:
            continue
        found.append(DeviceInfo(d["path"], d["product_id"], d["product_string"] or "",
                                d["serial_number"] or ""))
    return sorted(found, key=lambda info: not info.known)


class LamzuDevice:
    def __init__(self, info: DeviceInfo, dry_run: bool = False,
                 log: Optional[Callable[[str], None]] = None):
        self.info = info
        self.dry_run = dry_run
        self.log = log
        self.status_events: List[Report] = []
        self._dev = None
        self._last_write = 0.0

    def __enter__(self) -> "LamzuDevice":
        self._dev = _hid().device()
        self._dev.open_path(self.info.path)
        return self

    def __exit__(self, *exc) -> None:
        if self._dev is not None:
            self._dev.close()
            self._dev = None

    # -- transport ---------------------------------------------------------
    def request(self, report: bytes, timeout_s: float = 1.0) -> Report:
        for _ in range(ATTEMPTS):
            self._write(report)
            reply = self._await_reply(report, timeout_s)
            if reply is not None:
                return reply
        raise TimeoutError(f"no reply to command 0x{report[1]:02x}")

    def _write(self, report: bytes) -> None:
        wait = self._last_write + MIN_GAP_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        if self.log:
            self.log(f"-> {report.hex(' ')}")
        if self._dev.write(report) != len(report):
            raise IOError("HID write failed (is another configurator holding the device?)")
        self._last_write = time.monotonic()

    def _await_reply(self, report: bytes, timeout_s: float) -> Optional[Report]:
        deadline = time.monotonic() + timeout_s
        while (remaining := deadline - time.monotonic()) > 0:
            raw = self._dev.read(64, max(1, int(remaining * 1000)))
            if not raw:
                continue
            if self.log:
                self.log(f"<- {bytes(raw).hex(' ')}")
            try:
                reply = parse_report(raw)
            except ProtocolError:
                continue
            if reply.cmd == Cmd.STATUS_CHANGED and report[1] != Cmd.STATUS_CHANGED:
                self.status_events.append(reply)
                continue
            if reply.cmd != report[1]:
                continue
            if reply.cmd == Cmd.WRITE_FLASH and reply.raw != report:
                continue
            return reply
        return None

    # -- commands ----------------------------------------------------------
    def version(self) -> str:
        p = self.request(build_report(Cmd.READ_VERSION)).payload
        return f"{p[0]:x}.{p[1]:02x}"

    def online(self) -> bool:
        return self.request(build_report(Cmd.DEVICE_ONLINE)).payload[0] != 0

    def identify(self) -> Identity:
        """CID (11 = LAMZU), model id and link type, as the official app reads them."""
        return parse_identity(self.request(identify_request(os.urandom(4))))

    def battery(self) -> Battery:
        p = self.request(build_report(Cmd.BATTERY_LEVEL)).payload
        return Battery(p[0], bool(p[1]), (p[2] << 8) | p[3])

    def read_flash(self, address: int, length: int) -> bytes:
        data = bytearray()
        for req in read_flash_requests(address, length):
            reply = self.request(req)
            data += reply.payload[:req[5]]
        return bytes(data)

    def read_config(self, with_shortcuts: bool = False) -> FlashImage:
        size = SHORTCUTS + KEY_COUNT * SHORTCUT_STRIDE if with_shortcuts else CONFIG_SIZE
        return FlashImage(self.read_flash(0, size))

    def long_range(self) -> bool:
        return self.request(build_report(Cmd.GET_LONG_RANGE_MODE)).payload[0] != 0

    def set_long_range(self, enabled: bool) -> None:
        # UsbServer_SetLongRangeMode: length 1, value in the first payload byte.
        req = build_report(Cmd.SET_LONG_RANGE_MODE, length=1, payload=bytes([int(enabled)]))
        if not self.dry_run:
            self.request(req)

    def apply(self, patches: Sequence[Patch]) -> List[bytes]:
        requests = patch_requests(patches)
        if self.dry_run:
            return requests
        for req in requests:
            self.request(req)
        return requests

    def reset_settings(self) -> None:
        self.request(build_report(Cmd.CLEAR_SETTING), timeout_s=5.0)
