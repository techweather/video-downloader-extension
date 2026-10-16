"""
Tests for core/events.py — the Qt-free signals the download engine uses.
"""

import threading

from core.events import Signal, WorkerThread


class Emitter:
    changed = Signal(str, int)
    done = Signal()


class TestSignal:
    def test_connected_slots_receive_arguments_in_order(self):
        e = Emitter()
        calls = []
        e.changed.connect(lambda a, b: calls.append(('first', a, b)))
        e.changed.connect(lambda a, b: calls.append(('second', a, b)))
        e.changed.emit('x', 3)
        assert calls == [('first', 'x', 3), ('second', 'x', 3)]

    def test_each_instance_has_its_own_slots(self):
        a, b = Emitter(), Emitter()
        hits = []
        a.done.connect(lambda: hits.append('a'))
        b.done.emit()
        assert hits == []

    def test_same_bound_signal_on_every_access(self):
        e = Emitter()
        assert e.changed is e.changed

    def test_disconnect_one_and_all(self):
        e = Emitter()
        hits = []
        slot = lambda: hits.append(1)
        e.done.connect(slot)
        e.done.connect(lambda: hits.append(2))
        e.done.disconnect(slot)
        e.done.emit()
        assert hits == [2]
        e.done.disconnect()
        e.done.emit()
        assert hits == [2]

    def test_emit_with_no_slots_is_harmless(self):
        Emitter().changed.emit('x', 1)

    def test_instance_attribute_can_replace_signal(self):
        # tests/test_downloader.py swaps signals for Mocks this way
        e = Emitter()
        e.done = 'replaced'
        assert e.done == 'replaced'


class TestWorkerThread:
    def test_run_happens_off_the_calling_thread(self):
        seen = {}

        class W(WorkerThread):
            def run(self):
                seen['thread'] = threading.current_thread()

        w = W()
        w.start()
        assert w.wait(2000) is True
        assert seen['thread'] is w
        assert not w.isRunning()

    def test_wait_times_out_while_still_running(self):
        release = threading.Event()

        class W(WorkerThread):
            def run(self):
                release.wait(5)

        w = W()
        w.start()
        assert w.wait(50) is False
        assert w.isRunning()
        release.set()
        assert w.wait(2000) is True

    def test_threads_are_daemons(self):
        assert WorkerThread().daemon is True
