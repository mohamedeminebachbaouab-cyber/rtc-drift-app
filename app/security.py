"""
security.py — Anti-debug Windows + obfuscation memoire.
"""

import os
import ctypes
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
#  ANTI-DEBUG WINDOWS
# ══════════════════════════════════════════════════

def check_debugger() -> bool:
    """Detecte un debugger local via kernel32.IsDebuggerPresent()."""
    try:
        return bool(ctypes.windll.kernel32.IsDebuggerPresent())
    except Exception:
        return False


def check_remote_debugger() -> bool:
    """Detecte un debugger distant via kernel32.CheckRemoteDebuggerPresent()."""
    try:
        is_debugged = ctypes.c_int(0)
        ctypes.windll.kernel32.CheckRemoteDebuggerPresent(
            ctypes.windll.kernel32.GetCurrentProcess(),
            ctypes.byref(is_debugged),
        )
        return bool(is_debugged.value)
    except Exception:
        return False


# ══════════════════════════════════════════════════
#  OBFUSCATION MEMOIRE
# ══════════════════════════════════════════════════

class ObfuscatedBytes:
    """
    Stocke des bytes XOR'd avec un pad aleatoire de meme longueur.
    Un dump memoire brut ne revele ni la cle Fernet ni le token —
    il faut trouver ET le XOR'd ET le pad ET savoir les combiner.
    """
    __slots__ = ('_xored', '_pad')

    def __init__(self, data: bytes):
        self._pad = os.urandom(len(data))
        self._xored = bytes(a ^ b for a, b in zip(data, self._pad))

    def get(self) -> bytes:
        """Retourne les bytes originaux (XOR inverse)."""
        return bytes(a ^ b for a, b in zip(self._xored, self._pad))
