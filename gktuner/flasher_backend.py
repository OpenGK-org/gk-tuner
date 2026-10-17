"""UI adapter for the installed GKFlasher source, without duplicating ECU logic."""
import ast
import contextlib
import importlib.util
import sys
import threading
from pathlib import Path
from PyQt5 import QtCore as C, QtWidgets as W
from .runtime import frozen, data_root


def metadata(folder):
    """Read the backend's literal ECU/speed catalog without loading any driver."""
    path = Path(folder) / 'ecu_definitions.py'
    values = {}
    for node in ast.parse(path.read_text(encoding='utf-8-sig')).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('ECU_IDENTIFICATION_TABLE', 'BAUDRATES'):
                    values[target.id] = ast.literal_eval(node.value)
    return values['ECU_IDENTIFICATION_TABLE'], values['BAUDRATES']


_modules = {}


def load_backend(folder):
    folder = Path(folder).resolve()
    if folder in _modules:
        return _modules[folder]
    entry = folder / 'gui.py'
    if not entry.is_file():
        raise ValueError('Choose the GKFlasher source folder containing gui.py.')
    existing = sys.modules.get('ecu_definitions')
    if existing is not None and Path(existing.__file__).resolve().parent != folder:
        raise ValueError('Restart GK Tuner after changing GKFlasher source folders so its modules load together.')
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    name = 'gktuner_original_gkflasher'
    spec = importlib.util.spec_from_file_location(name, entry)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # Import the original functions/classes unchanged. Skip the standalone UI's
    # startup directory/log-file creation; GK Tuner owns application startup.
    tree = ast.parse(entry.read_text(encoding='utf-8-sig'), filename=str(entry))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef, ast.FunctionDef))]
    module.home = str(data_root() if frozen() else folder)
    exec(compile(tree, str(entry), 'exec'), module.__dict__)
    _modules[folder] = module
    return module


class JobSignals(C.QObject):
    log = C.pyqtSignal(str)
    progress = C.pyqtSignal(tuple)
    error = C.pyqtSignal(str)
    finished = C.pyqtSignal()


class ThreadOutput:
    """Route this job's printed output without swallowing other threads' text."""
    def __init__(self, original, emit):
        self.original, self.emit = original, emit
        self.thread = threading.get_ident()
        self.pending = ''

    def write(self, value):
        if threading.get_ident() != self.thread:
            return self.original.write(value)
        self.pending += value.replace('\r', '\n')
        while '\n' in self.pending:
            line, self.pending = self.pending.split('\n', 1)
            if line:
                self.emit(line)
        return len(value)

    def flush(self):
        if threading.get_ident() == self.thread and self.pending:
            self.emit(self.pending)
            self.pending = ''


class BackendJob(C.QRunnable):
    def __init__(self, callback, cleanup, interruptible=False):
        super().__init__()
        self.callback, self.cleanup, self.interruptible = callback, cleanup, interruptible
        self.signals = JobSignals()
        self.stop_event = threading.Event()

    def trace(self, frame, event, arg):
        if self.stop_event.is_set():
            # GKFlasher's logging handlers use KeyboardInterrupt to flush CSV.
            raise KeyboardInterrupt
        return self.trace

    def run(self):
        output = ThreadOutput(sys.stdout, self.signals.log.emit)
        try:
            if self.interruptible:
                sys.settrace(self.trace)
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                self.callback(self.signals)
        except KeyboardInterrupt:
            self.signals.log.emit('Stopped.')
        except BaseException as exc:
            self.signals.error.emit(str(exc))
        finally:
            sys.settrace(None)
            output.flush()
            try:
                self.cleanup(self.signals)
            except Exception as exc:
                self.signals.error.emit(f'Adapter release failed: {exc}')
            self.signals.finished.emit()


def controller_for(panel, module):
    """Bind the original GUI handlers to GK Tuner widgets and prompt lifecycle."""
    class Controller(module.Ui):
        @property
        def promptPending(self):
            return self.pending_prompts > 0

        def __init__(self):
            # Deliberately bypass standalone Ui.__init__: it shows its own window,
            # changes process cwd and scans adapters. Only its handlers are reused.
            W.QMainWindow.__init__(self, panel)
            self.pending_prompts = 0
            for name, widget in panel.backend_widgets.items():
                setattr(self, name, widget)
            self.previous_baudrate = False
            self.log_signal.connect(panel.append_log)
            prompts = {
                'request_pin_signal1': 'request_pin_from_user1',
                'request_pin_signal2': 'request_pin_from_user2',
                'request_pin_signal3': 'request_pin_from_user3',
                'request_pin_signal4': 'request_pin_from_user4',
                'request_pin_signal5': 'request_pin_from_user5',
                'request_new_password_signal': 'request_new_password_from_user',
                'request_vin_signal': 'request_vin_from_user',
                'request_vin_to_pin_signal': 'request_vin_to_pin_from_user',
            }
            self.prompt_slots = []
            for signal, method in prompts.items():
                def mark_pending(*args):
                    self.pending_prompts += 1
                def prompt(*args, method=method):
                    try:
                        getattr(module.Ui, method)(self, *args)
                    finally:
                        self.pending_prompts -= 1
                        panel.finish_if_idle()
                getattr(self, signal).connect(mark_pending, C.Qt.DirectConnection)
                self.prompt_slots.append(prompt)
                getattr(self, signal).connect(prompt, C.Qt.QueuedConnection)
            logger = module.bsl.logger
            before = set(logger.handlers)
            module.bsl.set_gui_log_handler(self.log_signal.emit)
            handlers = tuple(handler for handler in logger.handlers if handler not in before)
            self.destroyed.connect(lambda *args, logger=logger, handlers=handlers: [logger.removeHandler(handler) for handler in handlers])

        def log(self, text):
            self.log_signal.emit(str(text))

        def log2(self, text):
            self.log(text)

        def send_notification(self, title, body):
            self.log(f'{title}: {body}')

        def get_interface_url(self):
            value = panel.interface.currentText().strip()
            if not value:
                raise IndexError('Choose an adapter interface.')
            return value

        def is_can_interface(self, interface_name):
            return panel.protocol.currentData() == 'canbus'

    return Controller()
