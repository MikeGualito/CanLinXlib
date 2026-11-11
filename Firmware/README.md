# Firmware

The firmware image the two libraries in this repo talk to, plus a script to
write it to a board.

```
Firmware/
├── CanLinX_firmware.hex   the image (STM32C552CET6, Cortex-M33)
├── flash.py               writes it over USB DFU or SWD
└── README.md
```

`CanLinXlibLin` and `CanLinXlibCan` need a board already running this image. Without
it there is nothing to enumerate: no CDC COM port for LIN, no WinUSB interface
for CAN.

## Flashing

`flash.py` needs **STM32CubeProgrammer's CLI** (`STM32_Programmer_CLI`), which ships
standalone and also inside STM32CubeIDE. The script looks in the usual install
locations and on `PATH`; if yours is somewhere else, point
`STM32_PROGRAMMER_CLI` at the executable.

### Over USB (DFU bootloader)

No debug probe needed. Set BOOT0 high, reset or power-cycle the board so it
starts the STM32 bootloader, connect its USB cable, and run:

```
py Firmware/flash.py --dfu             # flash the single board in DFU mode
py Firmware/flash.py --dfu --list      # just list the boards in DFU mode
py Firmware/flash.py --dfu --usb USB1  # pick one when several are in DFU mode
```

The script asks the bootloader to start the new firmware when the write is done.

### Over SWD

With an external ST-LINK probe wired to SWDIO (PA13) and SWCLK (PA14):

```
py Firmware/flash.py            # flash the single attached board
py Firmware/flash.py --list     # just list the attached ST-LINK probes
py Firmware/flash.py --sn <SN>  # pick one when several probes are attached
```

With more than one probe or DFU board attached and no selector, the script
refuses rather than guessing: writing the wrong board of a two-board bench is
silent, and costs a debugging session to notice.

## After a write

The board re-enumerates, so Windows may hand it a different COM port number.
Give it a moment before opening the device.

Each board derives its USB serial from its MCU's unique device ID, so two
boards running this same image are still told apart by
`CanLinXlibCan(serial=...)` and `CanLinX.open(serial_number=...)`.

## Image

| | |
|---|---|
| Target | CanLinX (STM32C552CET6) |
| Channels | LIN on UART5, CAN / CAN FD on FDCAN1, both over one composite USB device |
| Format | Intel HEX, carrying its own load addresses and entry point |
| Flash range | `0x08000000`-`0x08008BF7` (35 832 bytes) |
| Size on chip | `text 35408` - `data 424` - `bss 48472` |
| sha256 | `d80fd051a18c94da61887f66bec56c7fbb2099efddd3978dd30b124bd8149961` |

Built with `arm-none-eabi-gcc` 14.3 from the firmware project (a separate
repository); this folder carries the built artefact only.

**Why Intel HEX and not an `.elf`.** The bytes that reach flash are the same
either way, but an `.elf` built for debugging carries the whole DWARF tree with
it: absolute source paths from the build machine, every function and struct
member by name, a map from each instruction back to its source line, and the
literal text of every macro. None of that is needed to program a board, and it
is a third of a megabyte of build-machine detail travelling with a 36 KB image.
Intel HEX carries the addresses and nothing else.

The `.hex` verifies byte for byte against the linked image, and every line
carries its own checksum, so a corrupted download fails at programming time
rather than producing a board that misbehaves.

`flash.py` also accepts a `.bin` (`--image`), supplying the load address for
it, and an `.elf` if you ever need to debug on target.
