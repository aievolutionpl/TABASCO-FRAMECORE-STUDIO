"""Compatibility imports; persistence is owned by FrameCore."""
from framecore.persistence import atomic_write, file_lock

__all__ = ["atomic_write", "file_lock"]
