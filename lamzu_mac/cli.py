"""Command-line configurator for LAMZU mice (macOS, Linux and Windows)."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import protocol as P
from .device import LamzuDevice, find_devices
from .selftest import run_selftest

BUTTON_NAMES = ["left", "right", "middle", "back", "forward", "dpi"]


def _rgb(text: str):
    text = text.lstrip("#")
    if len(text) != 6:
        raise argparse.ArgumentTypeError("color must be RRGGBB")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


def _fmt(value) -> str:
    return "<invalid>" if value is None else str(value)


def _open(args) -> LamzuDevice:
    devices = find_devices()
    if not devices:
        sys.exit("no LAMZU device found (receiver or cable connected?)")
    if args.device >= len(devices):
        sys.exit(f"device index {args.device} out of range ({len(devices)} found)")
    log = (lambda line: print(line, file=sys.stderr)) if args.verbose else None
    return LamzuDevice(devices[args.device], dry_run=args.dry_run, log=log)


def _require_online(dev: LamzuDevice) -> Optional[P.Identity]:
    # The receiver answers DEVICE_ONLINE itself; READ_VERSION and the flash
    # commands are relayed to the mouse and time out while it sleeps.
    if not dev.online():
        sys.exit("receiver found but the mouse is offline (turn it on or move it)")
    try:
        ident = dev.identify()
    except TimeoutError:
        ident = None
    if not dev.info.known and (ident is None or not ident.is_lamzu):
        sys.exit(f"pid 0x{dev.info.product_id:04x} does not identify as a LAMZU device; refusing to configure it")
    return ident


def _model_line(ident: Optional[P.Identity]) -> str:
    if ident is None:
        return "unknown (no identification reply)"
    name = ident.model.name if ident.model else f"unrecognized model (CID {ident.cid}, MID {ident.mid})"
    return f"{name}, {ident.link[0]}, up to {ident.max_rate} Hz"


def cmd_list(args) -> None:
    for i, d in enumerate(find_devices()):
        print(f"[{i}] {d.product or 'LAMZU'} pid=0x{d.product_id:04x} ({d.kind})")


def cmd_info(args) -> None:
    with _open(args) as dev:
        print(f"device   : {dev.info.product} (pid 0x{dev.info.product_id:04x})")
        if not dev.online():
            print("mouse    : offline (turn it on or move it)")
            return
        print(f"model    : {_model_line(_require_online(dev))}")
        print(f"firmware : {dev.version()}")
        bat = dev.battery()
        print(f"battery  : {bat.level}% {'(charging) ' if bat.charging else ''}{bat.millivolts} mV")
        _print_config(dev.read_config())


def _print_config(img: P.FlashImage) -> None:
    rate = img.setting("report-rate")
    print(f"rate     : {P.REPORT_RATES.get(rate, f'code {rate}')} Hz")
    stages, active = img.setting("dpi-stages"), img.setting("dpi-active")
    print(f"dpi      : {_fmt(stages)} stages, active #{_fmt(active)}")
    for i in range(P.DPI_STAGES):
        st = img.dpi_stage(i)
        mark = "*" if i == active else " "
        color = "#%02x%02x%02x" % st.color if st.color else "<invalid>"
        off = "" if stages is None or i < stages else "  (disabled)"
        print(f"  {mark}{i}: {_fmt(st.dpi):>6} DPI  {color}{off}")
    print("buttons  :")
    for i, name in enumerate(BUTTON_NAMES):
        b = img.binding(i)
        print(f"   {i} {name:<8}-> {b.describe() if b else '<invalid>'}")
    bar = img.led_bar()
    if bar:
        print(f"led bar  : mode {bar.mode} #{'%02x%02x%02x' % bar.color} "
              f"speed {bar.speed} brightness {bar.brightness}")
    print("settings :")
    for s in P.SETTINGS[5:]:
        print(f"   {s.key:<20}{_fmt(img.setting(s.key)):>5}   {s.help}")


def cmd_dump(args) -> None:
    with _open(args) as dev:
        _require_online(dev)
        data = dev.read_flash(0, args.length)
    if args.output:
        with open(args.output, "wb") as fh:
            fh.write(data)
    for off in range(0, len(data), 16):
        print(f"{off:04x}: {data[off:off + 16].hex(' ')}")


def _write(args, build) -> None:
    """Read the current flash, let `build(img, identity)` produce patches, then write them."""
    with _open(args) as dev:
        ident = _require_online(dev)
        img = dev.read_config()
        patches: List[P.Patch] = build(img, ident)
        requests = dev.apply(patches)
    for req in requests:
        print(("would send " if args.dry_run else "sent ") + req.hex(" "))


def cmd_dpi(args) -> None:
    def build(img, _ident):
        patches = [img.set_dpi(args.stage, args.dpi)]
        if args.color:
            patches.append(img.set_dpi_color(args.stage, args.color))
        return patches
    _write(args, build)


def cmd_stages(args) -> None:
    if not 1 <= args.count <= P.DPI_STAGES:
        sys.exit("stage count must be 1-8")

    def build(img, _ident):
        patches = [img.set_setting("dpi-stages", args.count)]
        active = img.setting("dpi-active")
        if active is None or active >= args.count:
            patches.append(img.set_setting("dpi-active", args.count - 1))
        return patches
    _write(args, build)


def cmd_active(args) -> None:
    def build(img, _ident):
        stages = img.setting("dpi-stages") or P.DPI_STAGES
        if not 0 <= args.stage < stages:
            sys.exit(f"active stage must be 0-{stages - 1}")
        return [img.set_setting("dpi-active", args.stage)]
    _write(args, build)


def cmd_rate(args) -> None:
    def build(img, ident):
        allowed = ident.rates() if ident else sorted(P.REPORT_RATE_CODES)
        if args.hz not in allowed:
            sys.exit(f"this mouse/receiver supports {allowed} Hz")
        return [img.set_setting("report-rate", P.REPORT_RATE_CODES[args.hz])]
    _write(args, build)


def cmd_button(args) -> None:
    binding = P.parse_binding(args.action)
    _write(args, lambda img, _ident: [img.set_binding(args.index, binding)])


def cmd_shortcut(args) -> None:
    events = P.parse_shortcut(args.keys)
    _write(args, lambda img, _ident: img.set_shortcut(args.index, events))


def cmd_set(args) -> None:
    if args.key not in P.SETTINGS_BY_KEY:
        sys.exit("unknown setting; run `lamzu settings` for the list")
    _write(args, lambda img, _ident: [img.set_setting(args.key, args.value)])


def cmd_settings(args) -> None:
    for s in P.SETTINGS:
        print(f"{s.key:<20} 0x{s.address:02x}  {s.field:<28} {s.help}")


def cmd_selftest(args) -> None:
    if args.dry_run:
        sys.exit("selftest needs real writes; run it without --dry-run")
    with _open(args) as dev:
        _require_online(dev)
        results = run_selftest(dev)
    for label, ok in results:
        print(f"[{'ok' if ok else 'FAIL'}] {label}")
    failures = sum(not ok for _, ok in results)
    if failures:
        sys.exit(f"{failures} check(s) failed")


def cmd_reset(args) -> None:
    if not args.yes:
        sys.exit("this restores factory settings on the mouse; re-run with --yes")
    with _open(args) as dev:
        _require_online(dev)
        if args.dry_run:
            print("would send " + P.build_report(P.Cmd.CLEAR_SETTING).hex(" "))
        else:
            dev.reset_settings()
            print("factory settings restored")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="lamzu", description=__doc__)
    ap.add_argument("--device", type=int, default=0, help="index from `lamzu list`")
    ap.add_argument("--dry-run", action="store_true", help="print write packets without sending")
    ap.add_argument("-v", "--verbose", action="store_true", help="log raw HID traffic")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="list connected devices").set_defaults(func=cmd_list)
    sub.add_parser("info", help="show firmware, battery and configuration").set_defaults(func=cmd_info)
    sub.add_parser("settings", help="list `set` keys").set_defaults(func=cmd_settings)

    p = sub.add_parser("dump", help="hex dump of the configuration flash")
    p.add_argument("-o", "--output")
    p.add_argument("--length", type=lambda v: int(v, 0), default=P.CONFIG_SIZE)
    p.set_defaults(func=cmd_dump)

    p = sub.add_parser("dpi", help="set one DPI stage")
    p.add_argument("stage", type=int)
    p.add_argument("dpi", type=int)
    p.add_argument("--color", type=_rgb)
    p.set_defaults(func=cmd_dpi)

    p = sub.add_parser("stages", help="number of DPI stages")
    p.add_argument("count", type=int)
    p.set_defaults(func=cmd_stages)

    p = sub.add_parser("active", help="active DPI stage")
    p.add_argument("stage", type=int)
    p.set_defaults(func=cmd_active)

    p = sub.add_parser("rate", help="polling rate in Hz")
    p.add_argument("hz", type=int)
    p.set_defaults(func=cmd_rate)

    p = sub.add_parser("button", help="remap a button")
    p.add_argument("index", type=int, help="0 left, 1 right, 2 middle, 3 back, 4 forward, 5 dpi")
    p.add_argument("action", help="left|right|middle|back|forward|dpi-cycle|dpi-up|dpi-down|"
                                  "scroll-left|scroll-right|rate-cycle|profile-switch|disabled|fire:P1:P2")
    p.set_defaults(func=cmd_button)

    p = sub.add_parser("shortcut", help="bind a keyboard shortcut to a button")
    p.add_argument("index", type=int)
    p.add_argument("keys", help="e.g. cmd+c, ctrl+shift+t, f5, mute, vol-up, play")
    p.set_defaults(func=cmd_shortcut)

    p = sub.add_parser("set", help="write a raw setting (see `lamzu settings`)")
    p.add_argument("key")
    p.add_argument("value", type=lambda v: int(v, 0))
    p.set_defaults(func=cmd_set)

    sub.add_parser("selftest", help="reversible read/write test on the connected mouse"
                   ).set_defaults(func=cmd_selftest)

    p = sub.add_parser("reset", help="restore factory settings")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_reset)

    args = ap.parse_args(argv)
    try:
        args.func(args)
    except (ValueError, TimeoutError, IOError) as exc:
        sys.exit(f"error: {exc}")


if __name__ == "__main__":
    main()
