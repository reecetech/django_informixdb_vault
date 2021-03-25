"""The PropagatingThread class allows tests to capture exceptions raised within threads
"""
from threading import Thread


class PropagatingThread(Thread):
    """Enables exceptions to be raised in the parent thread when the child thread is joined
    """
    def __init__(self, target=None):
        super().__init__(target=target)
        self.exc = None
        self.ret = None

    def run(self):
        try:
            self.ret = self._target(*self._args, **self._kwargs)
        except BaseException as exc:
            self.exc = exc

    def join(self, timeout=None):
        super().join(timeout=timeout)
        if self.exc:
            raise self.exc
        return self.ret
