"""Blokada plikowa między procesami: serwer MCP i dashboard to dwa procesy, które współdzielą pliki stanu (zadania, profil).

Sam `threading.Lock` chroni tylko wątki jednego procesu, więc odczyt-zmiana-zapis `tasks.json` z dwóch procesów gubił aktualizacje
(albo dawał dwa zadania z tym samym T-id). Tu: doradcza blokada systemowa (fcntl na POSIX, msvcrt na Windows) plus blokada wątków.
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

_THREAD_LOCK = threading.RLock()


@contextmanager
def file_lock(path: Path, timeout: float = 10.0):
    """Wyłączny dostęp do zasobu opisanego plikiem `path` (tworzonym, jeśli go nie ma), z limitem czasu oczekiwania."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with _THREAD_LOCK:
        fh = open(path, "a+b")
        deadline = time.time() + timeout
        try:
            while True:
                try:
                    if os.name == "nt":
                        import msvcrt

                        fh.seek(0)
                        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.time() > deadline:
                        raise TimeoutError(f"nie udało się uzyskać blokady {path.name} w {timeout} s")
                    time.sleep(0.02)
            yield
        finally:
            try:
                if os.name == "nt":
                    import msvcrt

                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            fh.close()


def atomic_write(path: Path, text: str) -> None:
    """Zapis przez unikalny plik tymczasowy + os.replace; na Windows ponawia, gdy ktoś właśnie czyta cel."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    for attempt in range(8):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 7:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.05 * (attempt + 1))
