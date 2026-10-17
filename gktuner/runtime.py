"""Separate installed resources from writable, per-user application data."""
import os
import sys
from pathlib import Path


def frozen():
    return bool(getattr(sys, 'frozen', False))


def resource_root():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


def data_root():
    override = os.environ.get('GKTUNER_DATA_DIR')
    return Path(override) if override else Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'GK Tuner'


def default_backend(name):
    if frozen():
        return resource_root() / 'backends' / name
    parent = resource_root().parent
    return parent / ('GKFlasher-1.99 STOCK' if name == 'GKFlasher' else 'ECU Reverse Engineering/ca663056 CCP/Logger')


def backend_setting(settings, name):
    key = 'flasher_path' if name == 'GKFlasher' else 'logger_path'
    saved = settings.value(key, '')
    entry = 'gui.py' if name == 'GKFlasher' else 'ccp_studio.py'
    if saved and (Path(saved) / entry).is_file():
        return Path(saved)
    return default_backend(name)


def prepare_desktop_runtime():
    """A windowed executable has no terminal and must not write beside itself."""
    folder = data_root()
    folder.mkdir(parents=True, exist_ok=True)
    if frozen():
        os.chdir(folder)
    if sys.stdout is None or sys.stderr is None:
        log = folder / 'runtime.log'
        if log.exists() and log.stat().st_size > 2_000_000:
            log.replace(folder / 'runtime.previous.log')
        stream = log.open('a', encoding='utf-8', buffering=1)
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream
