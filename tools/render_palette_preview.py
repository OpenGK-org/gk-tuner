"""Render bounded forms and palette controls with disposable settings."""
import os
import tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W, QtTest as T
from gktuner.app import MainWindow


def main():
    app = W.QApplication(['palette-preview'])
    app.setStyle('Fusion')
    for font in ('segoeui.ttf', 'segoeuib.ttf', 'trebuc.ttf'):
        G.QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + font)
    output = Path(__file__).resolve().parents[1] / 'artifacts'
    with tempfile.TemporaryDirectory() as folder:
        window = MainWindow(C.QSettings(str(Path(folder) / 'settings.ini'), C.QSettings.IniFormat))
        window.resize(1920, 1080)
        window.show()
        window.stack.setCurrentIndex(2)
        T.QTest.qWait(50)
        window.grab().save(str(output / 'gk-tuner-flashing-bounded.png'))
        window.stack.setCurrentIndex(4)
        T.QTest.qWait(50)
        window.grab().save(str(output / 'gk-tuner-settings-bounded.png'))
        window.palette_editor.open_dialog()
        T.QTest.qWait(50)
        window.palette_editor.dialog.grab().save(str(output / 'gk-tuner-palette-editor.png'))
        window.palette_editor.dialog.close()
        window.open_demo()
        for role, colour in dict(heat_low='#132e42', heat_mid='#4296a1', heat_high='#f1d68a', workspace='#24323e').items():
            window.palette_editor.set_colour(role, colour)
        window.stack.setCurrentIndex(0)
        T.QTest.qWait(50)
        window.grab().save(str(output / 'gk-tuner-custom-heatmap.png'))
        window.deleteLater()
        app.sendPostedEvents(None, C.QEvent.DeferredDelete)
    print('Rendered bounded Flashing/Settings, palette editor, and custom heatmap.')


if __name__ == '__main__':
    main()
