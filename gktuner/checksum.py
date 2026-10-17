"""Preview original GKFlasher checksum correction on a temporary BIN only."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from .flasher_backend import load_backend


def checksum_proposal(folder, data):
    backend = load_backend(folder)
    layout = backend.detect_offsets(data)
    if layout is None:
        raise ValueError('GKFlasher could not detect a supported calibration checksum layout.')
    logs, messages = [], []

    class PreviewMessageBox:
        Yes, No = 1, 2

        @staticmethod
        def question(parent, title, message, buttons, default):
            messages.append(message)
            return PreviewMessageBox.Yes

    with TemporaryDirectory(prefix='gktuner-checksum-') as folder:
        source = Path(folder) / 'preview.bin'
        source.write_bytes(data)
        context = SimpleNamespace(checksumFileInput=SimpleNamespace(text=lambda: str(source)), log=logs.append)
        # The original handler calculates and writes its proposal only to this
        # disposable copy. The caller confirms before changing the working BIN.
        message_box = backend.QMessageBox
        try:
            backend.QMessageBox = PreviewMessageBox
            backend.Ui.correct_checksum(context)
        finally:
            backend.QMessageBox = message_box
        corrected = source.read_bytes()
    if not messages or messages[0] == 'Save?':
        raise ValueError('No checksum regions are available for correction in this BIN.')
    if len(corrected) != len(data):
        raise ValueError('GKFlasher returned a different BIN size.')
    segments = []
    for region in layout['regions']:
        address = region['cks_address']
        before, after = data[address:address+2], corrected[address:address+2]
        if before != after:
            segments.append((address, before, after))
    return segments, messages[0].removesuffix('Save?').strip()
