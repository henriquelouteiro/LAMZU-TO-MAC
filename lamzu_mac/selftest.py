"""Reversible write test: touches only DPI stage 7 and button 7, restores them
from a backup and checks the flash is byte-identical afterwards."""
from __future__ import annotations

from typing import List, Tuple

from . import protocol as P

FULL_SIZE = P.SHORTCUTS + P.KEY_COUNT * P.SHORTCUT_STRIDE


def run_selftest(dev) -> List[Tuple[str, bool]]:
    results: List[Tuple[str, bool]] = []
    backup = dev.read_flash(0, FULL_SIZE)
    img = P.FlashImage(backup[:P.CONFIG_SIZE])
    touched = [(P.DPI_VALUES + 4 * 7, 4), (P.KEYS + 4 * 7, 4),
               (P.SHORTCUTS + 7 * P.SHORTCUT_STRIDE, P.SHORTCUT_STRIDE)]
    try:
        results.append((f"firmware {dev.version()} responds", True))
        original = img.dpi_stage(7).dpi or 6400
        probe = original - 50 if original > P.DPI_MIN else original + 50
        dev.apply([img.set_dpi(7, probe)])
        now = P.FlashImage(dev.read_flash(0, P.CONFIG_SIZE))
        results.append((f"DPI stage 7 write {original} -> {probe}", now.dpi_stage(7).dpi == probe))

        events = P.parse_shortcut("f5")
        dev.apply(img.set_shortcut(7, events))
        region = dev.read_flash(P.SHORTCUTS + 7 * P.SHORTCUT_STRIDE, P.SHORTCUT_STRIDE)
        now = P.FlashImage(dev.read_flash(0, P.CONFIG_SIZE))
        results.append(("shortcut block write on button 7",
                        P.decode_shortcut(region) == events
                        and now.binding(7) == P.Binding(P.KeyClass.SHORTCUT)))
    finally:
        dev.apply([P.Patch(a, backup[a:a + n]) for a, n in touched])
        results.append(("flash restored byte-identical", dev.read_flash(0, FULL_SIZE) == backup))
    return results
