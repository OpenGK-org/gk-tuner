"""Hidden subprocess console with Qt signals and explicit stdin responses.

Uses the standard Windows process launcher: this machine's Qt5 QProcess starts
Python children that immediately exit without output, while subprocess works.
"""
import subprocess
import threading
import os

from PyQt5 import QtCore as C


class ConsoleProcess(C.QObject):
    readyReadStandardOutput = C.pyqtSignal()
    finished = C.pyqtSignal(int, int)
    errorOccurred = C.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.child = None
        self.thread = None
        self.cwd = None
        self.buffer = bytearray()
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.last_error = ""

    def state(self):
        if self.child and (self.child.poll() is None or self.thread and self.thread.is_alive()):
            return C.QProcess.Running
        return C.QProcess.NotRunning

    def setWorkingDirectory(self, path):
        self.cwd = path

    def start(self, program, args):
        if self.state() != C.QProcess.NotRunning:
            raise ValueError("An operation is already running.")
        self.ready.clear()
        self.buffer.clear()
        self.last_error = ""
        try:
            environment = os.environ.copy()
            environment["PYTHONIOENCODING"] = "utf-8"
            self.child = subprocess.Popen([program, *args], cwd=self.cwd, stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                          env=environment,
                                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.thread = threading.Thread(target=self._read, args=(self.child,), daemon=True)
            self.thread.start()
        except OSError as exc:
            self.last_error = str(exc)
            self.errorOccurred.emit(str(exc))

    def _read(self, child):
        try:
            while True:
                data = child.stdout.read(1)
                if not data:
                    break
                with self.lock:
                    notify = not self.buffer
                    self.buffer.extend(data)
                    self.ready.set()
                if notify:
                    self.readyReadStandardOutput.emit()
            code = child.wait()
        except Exception as exc:
            self.last_error = str(exc)
            self.errorOccurred.emit(str(exc))
            code = child.wait()
        finally:
            child.stdout.close()
            child.stdin.close()
        self.finished.emit(code, 0)

    def readAllStandardOutput(self):
        with self.lock:
            data = bytes(self.buffer)
            self.buffer.clear()
            self.ready.clear()
            return data

    def write(self, data):
        if not self.child or self.child.poll() is not None:
            return
        self.child.stdin.write(data)
        self.child.stdin.flush()

    def waitForStarted(self, milliseconds):
        return self.child is not None and not self.last_error

    def waitForReadyRead(self, milliseconds):
        return self.ready.wait(milliseconds / 1000)

    def waitForFinished(self, milliseconds):
        if self.thread:
            self.thread.join(milliseconds / 1000)
            return not self.thread.is_alive()
        return True

    def errorString(self):
        return self.last_error
