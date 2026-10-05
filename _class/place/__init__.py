"""
jeuxRPG._class.place removed.

The entire place / navigation subsystem was removed as part of
the refactor. Importing specific place modules will raise ImportError
from their stubs. Keep this package present so imports fail loudly.
"""

__all__ = []
