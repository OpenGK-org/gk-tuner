"""Preview every flashing section without importing drivers or opening hardware."""
import os
import tempfile
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt5 import QtCore as C, QtWidgets as W, QtGui as G, QtTest as T
from gktuner.app import MainWindow


def main():
    app = W.QApplication(['gktuner-flashing-preview'])
    app.setStyle('Fusion')
    for name in ('segoeui.ttf', 'segoeuib.ttf', 'trebuc.ttf'):
        G.QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + name)
    output = Path(__file__).resolve().parents[1] / 'artifacts'
    with tempfile.TemporaryDirectory() as folder:
        window = MainWindow(C.QSettings(str(Path(folder) / 'settings.ini'), C.QSettings.IniFormat))
        window.resize(1440, 1000)
        window.show()
        window.stack.setCurrentIndex(2)
        panel = window.flasher_panel
        for theme in ('Light', 'Dark'):
            window.theme_choice.setCurrentText(theme)
            window.apply_appearance(False)
            for index, name in enumerate(('read-write', 'files', 'diagnostics', 'immobilizer', 'recovery', 'advanced')):
                panel.tabs.setCurrentIndex(index)
                T.QTest.qWait(60)
                window.grab().save(str(output / f'gk-tuner-flashing-{name}-{theme.lower()}.png'))
        panel.tabs.setCurrentIndex(0)
        window.drawer.set_open(True)
        window.drawer.animation.setCurrentTime(window.drawer.animation.duration())
        T.QTest.qWait(60)
        window.grab().save(str(output / 'gk-tuner-flashing-navigation.png'))
        assert panel.backend is None, 'A preview must not load the hardware backend'
        window.deleteLater()
        app.sendPostedEvents(None, C.QEvent.DeferredDelete)
    print('Rendered all six flashing tabs in Light and Dark, plus navigation. No hardware backend was loaded.')


if __name__ == '__main__':
    main()
