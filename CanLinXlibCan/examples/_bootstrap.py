"""Shared path bootstrap so the examples run from a checkout uninstalled."""
import pathlib
import sys

_here = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_here))
sys.path.insert(0, str(_here.parent / "CanLinXlibUsb"))
