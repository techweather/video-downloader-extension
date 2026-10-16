"""
Qt-free signals and worker threads for the download engine.

`Signal` covers the part of pyqtSignal the workers use — connect() and emit() —
so core/ runs without Qt (the native Mac and Windows apps talk to it over the
local API instead). Connected callbacks run on the emitting thread; a UI that
must touch widgets from its own thread marshals them itself
(see ui/engine_bridge.py for the Qt window).
"""

import threading


class BoundSignal:
    """One worker's copy of a signal: a list of callbacks, called in order."""

    def __init__(self):
        self._slots = []
        self._lock = threading.Lock()

    def connect(self, slot):
        with self._lock:
            self._slots.append(slot)

    def disconnect(self, slot=None):
        with self._lock:
            if slot is None:
                self._slots.clear()
            else:
                self._slots.remove(slot)

    def emit(self, *args):
        with self._lock:
            slots = list(self._slots)
        for slot in slots:
            slot(*args)


class Signal:
    """Declares a signal on a class, like pyqtSignal. Argument types are documentation only."""

    def __init__(self, *arg_types):
        self.arg_types = arg_types
        self._name = None

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        # Each instance gets its own BoundSignal, created on first access.
        bound = obj.__dict__.get(self._name)
        if bound is None:
            bound = obj.__dict__.setdefault(self._name, BoundSignal())
        return bound


class WorkerThread(threading.Thread):
    """threading.Thread plus the two QThread calls the app relies on: wait(ms) and isRunning()."""

    def __init__(self):
        super().__init__(daemon=True)

    def wait(self, msecs=None):
        self.join(None if msecs is None else msecs / 1000)
        return not self.is_alive()

    def isRunning(self):
        return self.is_alive()
