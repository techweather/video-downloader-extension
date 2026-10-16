"""
Runs engine callbacks on the Qt main thread.

The download engine (core/) emits its signals from worker threads, and Qt
widgets may only be touched from the main thread. Wrapping a window method
with on_main_thread() queues each call onto the Qt event loop instead —
the same hand-off PyQt's own signals used to do.
"""

from PyQt5.QtCore import QObject, pyqtSignal


class _Relay(QObject):
    call = pyqtSignal(object, tuple)

    def __init__(self):
        super().__init__()
        self.call.connect(lambda slot, args: slot(*args))


_relay = None


def on_main_thread(slot):
    """Wrap a slot so calls from any thread run on the Qt main thread, in order."""
    global _relay
    if _relay is None:
        # Created on first use, which is during window setup on the main thread,
        # so the relay lives there and cross-thread emits are queued to it.
        _relay = _Relay()

    def wrapper(*args):
        _relay.call.emit(slot, args)

    return wrapper
