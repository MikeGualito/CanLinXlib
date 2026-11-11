#!/usr/bin/env python3
"""
flash.py - writes the CanLinX firmware to a CanLinX board.

The .hex next to this script is the image the two host libraries in this repo
talk to. Flashing it is the one step that cannot be done from Python alone: it
goes through STM32CubeProgrammer's CLI. Two ways in:

  USB DFU   (--dfu)  the STM32 built-in bootloader. Put the board in boot mode
                     (BOOT0 high, then reset or power-cycle), connect its USB
                     cable, and run this script. No debug probe is needed.
  SWD       (default) an external ST-LINK probe wired to SWDIO (PA13) and
                     SWCLK (PA14).

After flashing, the board runs the firmware and enumerates as "CanLinX USB
Device": a CDC COM port for LIN and a WinUSB interface for CAN. The libraries
open that USB connection.

Usage:
  py flash.py --dfu                flash the single board in DFU boot mode
  py flash.py --dfu --list         list the boards in DFU mode and do nothing else
  py flash.py --dfu --usb 1        pick USB<N> when several boards are in DFU mode
  py flash.py                      flash the single board on an attached probe
  py flash.py --list               list attached probes and do nothing else
  py flash.py --sn <ST-LINK>       pick one board when several probes are attached
  py flash.py --image <path>       write a different image (.hex, .bin or .elf)

With more than one probe (or DFU board) attached and no selector, the script
refuses rather than guessing: writing the wrong board of a two-board bench is
silent, and costs a debugging session to notice.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMAGE = os.path.join(HERE, "CanLinX_firmware.hex")

# Where the firmware lives in the STM32C552CE's flash. Only needed for a raw
# .bin, which carries no addresses of its own; .hex and .elf carry theirs.
FLASH_BASE = "0x08000000"

# Where STM32CubeProgrammer's CLI tends to live. Globbed rather than pinned:
# the CubeIDE plugin directory carries the build date in its name and changes
# with every update, and the standalone bundle carries its version.
PROGRAMMER_GLOBS = [
    # Bundled with STM32CubeIDE.
    os.path.join("C:\\", "ST", "STM32CubeIDE_*", "STM32CubeIDE", "plugins",
                 "com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.*",
                 "tools", "bin", "STM32_Programmer_CLI.exe"),
    # Bundle dropped by the STM32Cube tools under the user profile.
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "stm32cube", "bundles",
                 "programmer", "*", "bin", "STM32_Programmer_CLI.exe"),
    # Standalone STM32CubeProgrammer install.
    os.path.join("C:\\", "Program Files", "STMicroelectronics",
                 "STM32Cube", "STM32CubeProgrammer", "bin",
                 "STM32_Programmer_CLI.exe"),
    # Linux / macOS standalone install.
    os.path.expanduser("~/STMicroelectronics/STM32Cube/STM32CubeProgrammer/"
                       "bin/STM32_Programmer_CLI"),
    "/opt/stm32cubeprog/bin/STM32_Programmer_CLI",
]


def find_programmer() -> str | None:
    """The STM32_Programmer_CLI to use, or None if there is no copy around."""
    override = os.environ.get("STM32_PROGRAMMER_CLI")
    if override and os.path.exists(override):
        return override

    for pattern in PROGRAMMER_GLOBS:
        if not pattern:
            continue
        hits = sorted(glob.glob(pattern))
        if hits:
            # Newest by name: the globs sort by version or build date.
            return hits[-1]

    # Last resort: on PATH.
    from shutil import which
    return which("STM32_Programmer_CLI")


def run_programmer(prog: str, args: list[str]) -> str:
    try:
        out = subprocess.run([prog] + args, capture_output=True, text=True,
                             timeout=180)
    except subprocess.TimeoutExpired:
        return "<timed out>"
    return (out.stdout or "") + (out.stderr or "")


def list_probes(prog: str) -> list[tuple[str, str]]:
    """The ST-LINK probes attached, as (serial, board name)."""
    text = run_programmer(prog, ["-l", "st-link"])
    serials = re.findall(r"ST-LINK SN\s*:\s*(\S+)", text)
    boards = re.findall(r"Board Name\s*:\s*(.+)", text)
    return [(sn, boards[i].strip() if i < len(boards) else "?")
            for i, sn in enumerate(serials)]


def list_dfu(prog: str) -> list[tuple[str, str]]:
    """The boards in DFU boot mode, as (port such as "USB1", serial)."""
    text = run_programmer(prog, ["-l", "usb"])
    ports = re.findall(r"Device Index\s*:\s*(\S+)", text)
    serials = re.findall(r"Serial number\s*:\s*(\S+)", text)
    return [(p, serials[i] if i < len(serials) else "?")
            for i, p in enumerate(ports)]


def flash_dfu(prog: str, image: str, wanted: str | None) -> bool:
    if not os.path.exists(image):
        print(f"!! {image} does not exist.")
        return False

    boards = list_dfu(prog)
    if not boards:
        print("!! no board in DFU mode. Set BOOT0 high, reset, and connect "
              "the USB cable.")
        return False
    if wanted is not None:
        boards = [b for b in boards if b[0].lower() == wanted.lower()]
        if not boards:
            print(f"!! no board at {wanted}.")
            return False
    elif len(boards) > 1:
        print("!! more than one board in DFU mode. Pass --usb, or unplug one, "
              "so there is no doubt about which board is being written:")
        for port, sn in boards:
            print(f"     {port}  {sn}")
        return False

    port, sn = boards[0]
    print(f"-- writing {os.path.basename(image)} over USB DFU to {port} ({sn})")
    write = ["-w", image]
    if image.lower().endswith(".bin"):
        write.append(FLASH_BASE)
    # -g starts the application when the write is done.
    text = run_programmer(prog, ["-c", f"port={port}"] + write + ["-v", "-g"])
    for line in text.splitlines():
        if re.search(r"[Ee]rror|Warning|verified|Download|complete", line):
            print("   " + line.strip())
    return "Download verified successfully" in text


def pick_probe(probes: list[tuple[str, str]],
               wanted: str | None) -> tuple[str, str] | None:
    if not probes:
        print("!! no ST-LINK probe found. Is the probe connected to SWD?")
        return None

    if wanted is not None:
        for sn, board in probes:
            if sn.lower() == wanted.lower():
                return sn, board
        print(f"!! no probe with ST-LINK SN {wanted}. Attached:")
        for sn, board in probes:
            print(f"     {sn}  {board}")
        return None

    if len(probes) > 1:
        print("!! more than one probe attached. Pass --sn, or unplug one, so "
              "there is no doubt about which board is being written:")
        for sn, board in probes:
            print(f"     {sn}  {board}")
        return None

    return probes[0]


def flash(prog: str, image: str, wanted_sn: str | None) -> bool:
    if not os.path.exists(image):
        print(f"!! {image} does not exist.")
        return False

    chosen = pick_probe(list_probes(prog), wanted_sn)
    if chosen is None:
        return False
    sn, board = chosen

    print(f"-- writing {os.path.basename(image)} to {board}, ST-LINK SN {sn}")
    # A raw .bin has no addresses in it, so the base has to be supplied; .hex
    # and .elf carry theirs and must NOT be given one, or it is written twice.
    write = ["-w", image]
    if image.lower().endswith(".bin"):
        write.append(FLASH_BASE)
    # mode=UR holds the target under reset while connecting, so a running
    # firmware busy on USB cannot refuse the connection.
    text = run_programmer(prog, ["-c", "port=SWD", f"sn={sn}", "mode=UR"]
                                + write + ["-v", "-rst"])
    for line in text.splitlines():
        if re.search(r"[Ee]rror|Warning|verified|Download|complete", line):
            print("   " + line.strip())
    return ("Download verified successfully" in text
            or "Verification...OK" in text)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.strip().splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", default=DEFAULT_IMAGE,
                    help="image to write: .hex, .bin or .elf "
                         "(default: the .hex beside this script)")
    ap.add_argument("--sn", default=None,
                    help="ST-LINK serial of the board to write")
    ap.add_argument("--dfu", action="store_true",
                    help="write over the USB DFU bootloader instead of SWD")
    ap.add_argument("--usb", default=None,
                    help="with --dfu: the board to write, e.g. USB1")
    ap.add_argument("--list", action="store_true",
                    help="list the attached probes (or DFU boards) and exit")
    args = ap.parse_args()

    prog = find_programmer()
    if prog is None:
        print("!! STM32_Programmer_CLI not found. Install STM32CubeProgrammer "
              "(or STM32CubeIDE, which bundles it), or point the environment "
              "variable STM32_PROGRAMMER_CLI at the executable.")
        return 2

    if args.list and args.dfu:
        boards = list_dfu(prog)
        if not boards:
            print("no board in DFU mode.")
        for port, sn in boards:
            print(f"{port}  {sn}")
        return 0

    if args.list:
        probes = list_probes(prog)
        if not probes:
            print("no ST-LINK probe found. Is the probe connected to SWD?")
        for sn, board in probes:
            print(f"{sn}  {board}")
        return 0

    ok = (flash_dfu(prog, args.image, args.usb) if args.dfu
          else flash(prog, args.image, args.sn))
    if not ok:
        print("\n!! flashing did not report success.")
        return 1

    print("\n-- done. The board re-enumerates, so give it a moment before "
          "opening the COM port or the WinUSB interface.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
