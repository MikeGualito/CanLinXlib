"""
canlinxlibusb -- the USB handle that CanLinXlibCan and CanLinXlibLin share.

CAN and LIN are two bulk pairs of ONE WinUSB interface, and libusb on Windows
gives a process a single handle to it. Both libraries get that handle from here,
so they can run in the same process; see :class:`SharedDevice`.

You rarely need this package directly: ``CanLinXlibCan(...)`` and
``CanLinX.open()`` use it. It is public for tools that need the board serials or
the PwrSup COM port.
"""

from .device import (
    CAN_EP_IN, CAN_EP_OUT, CANLINX_PID, CANLINX_VID, LIN_EP_IN, LIN_EP_OUT,
    VENDOR_INTERFACE, SharedDevice, find_devices, list_serials, serial_of,
)
from .errors import (
    UsbBackendMissing, UsbDeviceBusy, UsbDeviceNotFound, UsbError,
)
from .ports import INTERFACE_PWRSUP, port_for_interface, pwrsup_port

__version__ = "0.6.0"

__all__ = [
    "SharedDevice", "find_devices", "list_serials", "serial_of",
    "CANLINX_VID", "CANLINX_PID", "VENDOR_INTERFACE",
    "CAN_EP_IN", "CAN_EP_OUT", "LIN_EP_IN", "LIN_EP_OUT",
    "UsbError", "UsbDeviceNotFound", "UsbDeviceBusy", "UsbBackendMissing",
    "INTERFACE_PWRSUP", "port_for_interface", "pwrsup_port",
]
