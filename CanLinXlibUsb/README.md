# canlinxlibusb

The USB handle that **CanLinXlibCan** and **CanLinXlibLin** share.

On a CanLinX board, CAN (gs_usb) and LIN are two independent bulk endpoint pairs
of the **same WinUSB interface** (interface 2). libusb on Windows gives a process
only one handle to a WinUSB interface, so the two libraries cannot each open
their own. Both call `SharedDevice.acquire()`: the first call opens and claims the
interface, the rest of the process gets the same handle, and the last
`release()` gives it back.

```python
from canlinxlibcan import CanLinXlibCan
from canlinxliblin import CanLinX

with CanLinXlibCan(bitrate=500_000) as bus, CanLinX.open() as lin:
    ...   # both channels, one process, one handle
```

| Endpoint | Direction | Channel |
|---|---|---|
| `0x83` / `0x02` | IN / OUT | CAN (gs_usb frames) |
| `0x84` / `0x03` | IN / OUT | LIN (`lin_framing` messages) |

**Two processes cannot share a board** (libusb limit on Windows): the second one
gets `UsbDeviceBusy`. The PwrSup COM port is a CDC ACM bound to `usbser.sys`, not
to WinUSB, so any process can use it meanwhile; `pwrsup_port(serial)` finds it.

Two boards are told apart only by their USB serial: `list_serials()`.

Requires `pyusb` and `libusb-package`.
