"""Exercise the installed runtime without opening an adapter or using real files."""
import json
import traceback
from pathlib import Path


def run(report):
    result = {'passed': False, 'hardware_connections': 0, 'checks': []}
    window = None
    try:
        from PyQt5 import QtCore as C, QtWidgets as W
        from .runtime import data_root, resource_root
        from .app import MainWindow
        from . import __version__
        from .checksum import checksum_proposal
        C.QCoreApplication.setAttribute(C.Qt.AA_EnableHighDpiScaling)
        app = W.QApplication(['gktuner-release-check'])
        app.setStyle('Fusion')
        settings = C.QSettings(str(data_root() / 'smoke-settings.ini'), C.QSettings.IniFormat)
        settings.clear()
        window = MainWindow(settings)
        window.setAttribute(C.Qt.WA_DontShowOnScreen)
        errors = []
        window.error = lambda value: errors.append(str(value))
        window.show()
        result['version'] = __version__
        assert not window.windowIcon().isNull()
        assert window.flasher_panel.ecu.count() > 1
        assert Path(window.flasher_path.text()).is_relative_to(resource_root())
        window.drawer.set_open(True)
        window.drawer.animation.setCurrentTime(window.drawer.animation.duration())
        brand = window.brand_logo.parentWidget().layout().itemAt(0).layout()
        assert brand.itemAt(0).widget() is window.brand_logo
        result['checks'] += ['startup', 'bundled ECU catalog', 'logo left of name', 'application icon']
        window.open_demo()
        assert window.document and window.definition and window.open_editors
        before = bytes(window.document.data)
        editor = window.active_editor
        first = editor.table.item(0, 0)
        first.setText(str(float(first.text()) + 1))
        assert editor.pending
        assert editor.commit()
        window.document.undo()
        assert bytes(window.document.data) == before
        result['checks'] += ['bundled demo', 'map edit and undo']
        data = bytearray(0x20000)
        data[0xFEFE:0xFF00] = b'OK'
        data[0x3EF4:0x3EF6] = b'\xff\xff'
        data[0x3EF6] = 1
        data[0x3EF8:0x3EFB] = (0x200).to_bytes(3, 'little')
        data[0x3EFC:0x3EFF] = (0x20f).to_bytes(3, 'little')
        data[0x3FE4:0x3FE6] = (0x1234).to_bytes(2, 'little')
        data[0x200:0x210] = bytes(range(16))
        segments, summary = checksum_proposal(window.flasher_path.text(), bytes(data))
        assert segments and 'Current Boot checksum:' in summary
        backend = window.flasher_panel.ensure_backend()
        assert callable(backend.flash_calibration)
        import bsl
        import flasher.rsw
        for name in ('simk4x_bootstrap.bin', 'simk4x_kernel.bin', 'simk4x_driver_i4_a29fx00bx.bin', 'simk4x_driver_v6_a29fx00bx.bin'):
            assert Path(bsl.resource_path('assets/' + name)).is_file()
        assert Path(flasher.rsw.RSW_FILE).is_file()
        result['checks'] += ['GKFlasher import', 'original checksum calculation', 'BSL and RSW resources']
        window.stack.setCurrentIndex(1)
        dashboard = window.ccp_dashboard
        assert dashboard.view is not None

        def js(expression):
            replies = []
            loop = C.QEventLoop()
            dashboard.page.runJavaScript(expression, lambda value: (replies.append(value), loop.quit()))
            C.QTimer.singleShot(3000, loop.quit)
            loop.exec_()
            return replies[0] if replies else None

        deadline = C.QDeadlineTimer(25000)
        while not deadline.hasExpired():
            if js("typeof state!=='undefined' && state.rows.length>0 && document.querySelectorAll('canvas').length===6"):
                break
            app.processEvents()
        else:
            raise AssertionError('Packaged logger did not load its sample/dashboard')
        assert window.ccp_dashboard.bridge.backend.logger.FORCED_LIBUSB, window.ccp_dashboard.bridge.backend.logger.FORCED_LIBUSB_ERROR
        window.palette_editor.set_colour('surface', '#243b48')
        window.palette_editor.set_colour('accent', '#9d79c5')
        app.processEvents()
        deadline = C.QDeadlineTimer(5000)
        while not deadline.hasExpired():
            if js("typeof customPalette!=='undefined' && customPalette.accent==='#9d79c5'"):
                break
            app.processEvents()
        else:
            raise AssertionError('Packaged palette bridge failed')
        result['checks'] += ['QtWebEngine subprocess', 'CCP backend and sample', 'six graph canvases', 'bundled libusb', 'palette bridge']
        assert not errors, errors
        result['passed'] = True
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        Path(report).write_text(json.dumps(result, indent=2), encoding='utf-8')
        if window is not None:
            window.hide()
            window.deleteLater()
            app.sendPostedEvents(None, C.QEvent.DeferredDelete)
    return 0 if result['passed'] else 1
