"""Utilidades compartidas: cancelación y callbacks de log/progreso."""

import threading
from typing import Callable, Optional

LogFn = Callable[[str], None]
ProgressFn = Callable[[int, int], None]


class Cancelled(Exception):
    """El usuario canceló la operación."""


def noop_log(msg: str) -> None:
    pass


def check_cancel(cancel: Optional[threading.Event]) -> None:
    if cancel is not None and cancel.is_set():
        raise Cancelled()
