# lamzu-mac

**English** · [Português (Brasil)](README.pt-BR.md)

Open-source configurator for LAMZU mice (Atlantis OG V2, Atlantis Mini, Thorn, Maya,
Paro, Atlantis Nordic) on macOS, which has no official app. It is a port of the
Windows-only "Mouse Drive Beta" 1.6.0.43, built by reverse engineering; the protocol
and the evidence behind it are in [docs/PROTOCOL.md](docs/PROTOCOL.md) (Portuguese).

It also runs on Windows and Linux, since it uses `hidapi`.

> Independent project, not affiliated with LAMZU. Use at your own risk; before
> changing a lot of settings, export a backup (`lamzu dump -o backup.bin` or from the app).

## Compatibility

The app identifies the model (using the mouse's own identification command) and only
shows the options the official app shows for it, including the polling rates supported
by the mouse + receiver pair.

| Model | Status |
|---|---|
| Atlantis Mini + 4K receiver | tested on Windows and macOS |
| Atlantis OG V2, Thorn, Maya, Paro, Atlantis Nordic-R'lyeh | supported by the official app 1.6.0.43, not tested here yet |
| Wired mode (PID `0xF50F`), 1K/2K/8K receivers | expected to work, not tested yet |
| Other PIDs with VID `0x3554` | accepted only if the device identifies itself as LAMZU (CID 11) |

Tested another model? Please open an issue with the output of `lamzu info` and `lamzu selftest`.

## Installation

Requires Python 3.10+.

### macOS

Install Python from python.org or with `brew install python`, then:

```sh
git clone https://github.com/henriquelouteiro/LAMZU-TO-MAC.git
cd LAMZU-TO-MAC
bash scripts/install-mac.sh
```

The script creates `.venv`, installs `hidapi` and `PySide6`, runs the tests and creates
**LAMZU Configurator** in `~/Applications` (also available through Spotlight). Then plug
in the receiver and run `source .venv/bin/activate && lamzu selftest` to validate the
connection. The app points to the folder where you ran the script, so keep that folder.

The configuration channel is a vendor-defined HID collection (`0xFF02`), not a
keyboard or mouse, so no special permission should be needed. If macOS asks for
*Input Monitoring*, allow it for Terminal/Python in System Settings → Privacy & Security.

**Updating** (close the app first; no need to uninstall):

```sh
cd LAMZU-TO-MAC
bash scripts/update-mac.sh        # git pull + reinstall dependencies, tests and app
```

**Uninstalling:**

```sh
bash scripts/uninstall-mac.sh     # removes ~/Applications/LAMZU Configurator.app and .venv
cd .. && rm -rf LAMZU-TO-MAC      # optional: delete the code too
```

Your mouse keeps its settings either way: they are stored in the mouse, not on the computer.

### Windows / Linux

```sh
git clone https://github.com/henriquelouteiro/LAMZU-TO-MAC.git
cd LAMZU-TO-MAC
python -m venv .venv
.venv\Scripts\activate            # Linux: source .venv/bin/activate
pip install -e ".[gui]"
lamzu-gui
```

On Windows, close the official "Mouse Drive Beta" so both apps don't compete for the
device. On Linux, your user needs read/write access to the `hidraw` device (udev rule).

## Desktop app

```sh
lamzu-gui                                         # or: python -m lamzu_mac.gui
lamzu-gui --demo tests/fixtures/flash_f510.bin    # no mouse needed, uses a flash dump
```

Sections: **Performance** (polling rate and DPI stages with colors), **Buttons**
(clickable diagram: clicks, DPI, scrolling, media keys, keyboard shortcuts, rapid fire,
DPI lock), **Lighting** (only for models with LEDs), **Sensor** (Motion Sync, angle
snapping, ripple control, LOD, LP/HP mode, debounce) and **Device** (battery,
long-range mode, backup, self-test, factory reset). Changes are written immediately.

## Command line

```sh
lamzu info                        # model, firmware, battery, DPI, buttons, settings
lamzu dpi 0 800 --color 00ff00    # stage 0 = 800 DPI, green LED
lamzu stages 3                    # 3 active DPI stages
lamzu active 1                    # active stage
lamzu rate 4000                   # 125 … 8000 Hz, as supported by mouse and receiver
lamzu button 4 dpi-up             # buttons 0-5: left, right, middle, back, forward, dpi
lamzu shortcut 3 cmd+c            # keyboard shortcut or media key (mute, play, vol-up…)
lamzu settings                    # list of advanced settings
lamzu set motion-sync 1
lamzu dump -o backup.bin          # raw copy of the configuration flash
lamzu selftest                    # reversible read/write test (run this first)
lamzu reset --yes                 # factory reset
```

Use `--dry-run` to print the packets without sending them, and `-v` to log the HID
traffic. With the wireless receiver the mouse must be awake: the receiver answers the
online status, but reads and writes are relayed to the mouse.

## Project layout

```
lamzu_mac/protocol.py   pure encoding: reports, checksum, flash map, DPI, buttons, model table
lamzu_mac/device.py     hidapi transport (same timing/retries as the original app)
lamzu_mac/cli.py        command line
lamzu_mac/gui/          PySide6 app (HID on a separate thread; --demo mode)
tests/                  tests with a real 0xF510 receiver dump (+ GUI flows)
tools/re/               scripts used for the reverse engineering
```

```sh
python -m unittest discover -s tests -t .
```

## License

MIT. See [LICENSE](LICENSE).
