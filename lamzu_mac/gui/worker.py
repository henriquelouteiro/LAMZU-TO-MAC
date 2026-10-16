"""Background HID access. All device I/O runs on one QThread so the UI never
blocks; jobs are plain callables executed in submission order."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

from PySide6.QtCore import QObject, Qt, Signal, Slot

from .. import protocol as P
from ..device import Battery, DeviceInfo, LamzuDevice, find_devices
from ..selftest import FULL_SIZE


@dataclass
class Snapshot:
    info: DeviceInfo
    online: bool
    firmware: Optional[str] = None
    battery: Optional[Battery] = None
    image: Optional[P.FlashImage] = None
    long_range: Optional[bool] = None
    identity: Optional[P.Identity] = None


class DemoDevice:
    """Stands in for LamzuDevice using a flash dump, for offline UI work."""

    def __init__(self, data: bytes):
        self.flash = bytearray(data) + bytearray(b"\xff" * max(0, FULL_SIZE - len(data)))
        self.info = DeviceInfo(b"demo", 0xF510, "LAMZU 4K Receiver (demo)", "")
        self._long_range = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def online(self) -> bool:
        return True

    def identify(self) -> P.Identity:
        return P.Identity(P.LAMZU_CID, 2, 1)   # Atlantis Mini on a 4K receiver

    def version(self) -> str:
        return "1.24"

    def battery(self) -> Battery:
        return Battery(78, False, 3920)

    def read_flash(self, address: int, length: int) -> bytes:
        return bytes(self.flash[address:address + length])

    def read_config(self, with_shortcuts: bool = False) -> P.FlashImage:
        return P.FlashImage(self.read_flash(0, FULL_SIZE if with_shortcuts else P.CONFIG_SIZE))

    def apply(self, patches: Sequence[P.Patch]) -> List[bytes]:
        for patch in patches:
            self.flash[patch.address:patch.address + len(patch.data)] = patch.data
        return P.patch_requests(patches)

    def long_range(self) -> bool:
        return self._long_range

    def set_long_range(self, enabled: bool) -> None:
        self._long_range = enabled

    def reset_settings(self) -> None:
        pass


class DeviceWorker(QObject):
    _job = Signal(object)
    finished = Signal(object, object, object)   # callback, result, exception

    def __init__(self, demo: Optional[bytes] = None):
        super().__init__()
        self.device = None
        self._demo = demo
        self._job.connect(self._run, Qt.ConnectionType.QueuedConnection)

    def submit(self, fn: Callable[["DeviceWorker"], object],
               callback: Optional[Callable[[object, Optional[BaseException]], None]] = None) -> None:
        self._job.emit((fn, callback))

    @Slot(object)
    def _run(self, item) -> None:
        fn, callback = item
        try:
            result, error = fn(self), None
        except Exception as exc:  # reported to the UI thread
            result, error = None, exc
            if isinstance(exc, (IOError, OSError)):
                self.close()
        self.finished.emit(callback, result, error)

    # -- helpers used inside jobs (worker thread) -------------------------
    def ensure_open(self):
        if self.device is not None:
            return self.device
        if self._demo is not None:
            self.device = DemoDevice(self._demo)
            return self.device
        devices = find_devices()
        if not devices:
            return None
        dev = LamzuDevice(devices[0])
        dev.__enter__()
        self.device = dev
        return dev

    def close(self) -> None:
        if self.device is not None:
            try:
                self.device.__exit__(None, None, None)
            except Exception:
                pass
            self.device = None


# -- jobs ------------------------------------------------------------------

def load_snapshot(w: DeviceWorker) -> Optional[Snapshot]:
    dev = w.ensure_open()
    if dev is None:
        return None
    snap = Snapshot(dev.info, dev.online())
    if snap.online:
        try:
            snap.identity = dev.identify()
        except TimeoutError:
            snap.identity = None
        if not dev.info.known and (snap.identity is None or not snap.identity.is_lamzu):
            raise IOError(f"o dispositivo PID 0x{dev.info.product_id:04X} não se identificou como LAMZU")
        snap.firmware = dev.version()
        snap.battery = dev.battery()
        snap.image = dev.read_config(with_shortcuts=True)
        try:
            snap.long_range = dev.long_range()
        except TimeoutError:
            snap.long_range = None
    return snap


def poll_status(w: DeviceWorker, with_battery: bool) -> Optional[Snapshot]:
    dev = w.ensure_open()
    if dev is None:
        return None
    snap = Snapshot(dev.info, dev.online())
    if snap.online and with_battery:
        snap.battery = dev.battery()
    return snap
