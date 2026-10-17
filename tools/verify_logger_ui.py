"""Exercise the real embedded CCP dashboard on Windows without any adapter I/O."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "windows"
from gktuner.app import MainWindow
from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W, QtTest as T


def main():
    app = W.QApplication(["gktuner-logger-check"])
    app.setStyle("Fusion")
    output = Path(__file__).resolve().parents[1] / "artifacts"
    with tempfile.TemporaryDirectory() as folder:
        settings = C.QSettings(str(Path(folder) / "settings.ini"), C.QSettings.IniFormat)
        settings.setValue('ui_scale', 150)
        window = MainWindow(settings)
        window.setAttribute(C.Qt.WA_DontShowOnScreen)
        window.resize(1600, 1000)
        errors = []
        window.error = lambda value: errors.append(str(value))
        window.show()
        window.stack.setCurrentIndex(1)
        dashboard = window.ccp_dashboard
        page = dashboard.page
        console = []
        page.javaScriptConsoleMessage = lambda level, message, line, source: console.append(f"{line}: {message}")

        def js(expression):
            results = []
            loop = C.QEventLoop()
            page.runJavaScript(expression, lambda value: (results.append(value), loop.quit()))
            C.QTimer.singleShot(3000, loop.quit)
            loop.exec_()
            if not results:
                raise AssertionError("JavaScript callback timed out")
            return results[0]

        def wait_for(expression):
            deadline = C.QDeadlineTimer(12000)
            while not deadline.hasExpired():
                if js(expression):
                    return
                loop = C.QEventLoop()
                C.QTimer.singleShot(100, loop.quit)
                loop.exec_()
            raise AssertionError(f"Dashboard timed out: {expression}\n{console}\n{errors}")

        def mouse_point(selector, fraction=None):
            js(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block:'center'}})")
            T.QTest.qWait(50)
            point = js("(()=>{const r=document.querySelector(" + json.dumps(selector) + ").getBoundingClientRect();return {x:r.left+" +
                       (f"52+(r.width-67)*{fraction}" if fraction is not None else "r.width/2") +
                       ",y:r.top+r.height/2,width:innerWidth,height:innerHeight}})()")
            return C.QPoint(round(point['x'] * dashboard.view.width() / point['width']),
                            round(point['y'] * dashboard.view.height() / point['height']))

        def click(selector):
            point = mouse_point(selector)
            T.QTest.mouseClick(dashboard.view.focusProxy(), C.Qt.LeftButton, pos=point)
            T.QTest.qWait(50)

        def assert_visible(selector):
            geometry = js("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height,viewportWidth:innerWidth,viewportHeight:innerHeight}})()")
            visible = geometry['width'] > 0 and geometry['top'] >= 0 and geometry['bottom'] <= geometry['viewportHeight'] and geometry['left'] >= 0 and geometry['right'] <= geometry['viewportWidth']
            if not visible:
                window.grab().save(str(output / 'gk-tuner-logger-interaction-failure.png'))
            assert visible, (selector, geometry, window.ui_scale.value(), window.size().width(), window.size().height())

        wait_for("typeof state!=='undefined' && state.rows.length>0 && document.querySelectorAll('canvas').length===6")
        assert abs(dashboard.view.zoomFactor() - 1.5) < .001, ('saved startup scale', dashboard.view.zoomFactor())
        reload_loop = C.QEventLoop()
        page.loadFinished.connect(reload_loop.quit)
        page.triggerAction(page.Reload)
        C.QTimer.singleShot(5000, reload_loop.quit)
        reload_loop.exec_()
        page.loadFinished.disconnect(reload_loop.quit)
        wait_for("typeof state!=='undefined' && state.rows.length===2989 && document.querySelectorAll('canvas').length===6")
        assert abs(dashboard.view.zoomFactor() - 1.5) < .001, ('reloaded scale', dashboard.view.zoomFactor())
        assert js("$('settings').classList.contains('open') && $('settings-toggle').getAttribute('aria-expanded')==='true'")
        # Round trips retain the same dashboard and must never produce a native
        # top-level combo box or discard its open connection controls.
        initial_top_levels = {w for w in W.QApplication.topLevelWidgets() if w.isVisible()}
        for _ in range(3):
            window.log_mode.setCurrentIndex(1)
            T.QTest.qWait(50)
            window.log_mode.setCurrentIndex(0)
            T.QTest.qWait(50)
            assert dashboard.view is not None and dashboard.view.zoomFactor() == 1.5
            assert window.rate.isHidden() and not window.rate.isWindow()
            assert {w for w in W.QApplication.topLevelWidgets() if w.isVisible()} == initial_top_levels
            assert js("$('settings').classList.contains('open')")
        assert js("state.rows.length") == 2989
        assert js("document.querySelectorAll('.signal-item').length") == 103
        assert window.session.snapshot()["state"] == "idle"
        assert not errors, errors
        assert not js("document.getElementById('notice').textContent"), console
        # Actual Qt mouse events verify browser hit testing, rather than calling
        # DOM click handlers directly. Check small windows and every scale edge.
        interaction_cases = []
        for width, height in ((1440, 900), (1050, 680)):
            for scale in (75, 100, 150, 200):
                window.resize(width, height)
                window.ui_scale.setValue(scale)
                window.apply_appearance(False)
                T.QTest.qWait(150)
                assert abs(dashboard.view.zoomFactor() - scale / 100) < .001
                js("window.scrollTo(0,0);document.querySelector('.sidebar').scrollTop=0")
                for selector in ('#mode-record', '#mode-monitor', '#capture-button', '#settings-toggle'):
                    assert_visible(selector)
                if js("$('settings').classList.contains('open')"):
                    click('#settings-toggle')
                click('#settings-toggle')
                assert js("$('settings').classList.contains('open')")
                for selector in ('#channel', '#bitrate', '#rate'):
                    mouse_point(selector)
                    assert_visible(selector)
                click('#settings-toggle')
                click('.chart-actions button')
                wait_for("!$('plot-modal').hidden")
                assert_visible('.modal')
                assert_visible('#modal-close')
                assert_visible('#modal-save')
                click('#modal-close')
                wait_for("$('plot-modal').hidden")
                for fraction in (.2, .7):
                    point = mouse_point('canvas', fraction)
                    event = G.QMouseEvent(C.QEvent.MouseMove, C.QPointF(point), C.Qt.NoButton, C.Qt.NoButton, C.Qt.NoModifier)
                    W.QApplication.sendEvent(dashboard.view.focusProxy(), event)
                    T.QTest.qWait(80)
                    # Error in displayed X location, expressed in native pixels.
                    error = js("(()=>{const r=document.querySelector('canvas').getBoundingClientRect();const v=view();return Math.abs((state.cursor-v[0])/(v[1]-v[0])-" + str(fraction) + ")*(r.width-67)*devicePixelRatio})()")
                    assert error < 3, (width, height, scale, fraction, error)
                interaction_cases.append([width, height, scale])
        window.resize(1600, 1000)
        window.ui_scale.setValue(100)
        window.apply_appearance(False)
        T.QTest.qWait(150)
        js("window.scrollTo(0,0);document.querySelector('.sidebar').scrollTop=0")
        session = window.session
        def fake_start(names, channel, bitrate, rate, mode):
            session.state, session.mode, session.fields = 'recording', mode, ['t_s', 'RPM']
        def fake_stop():
            session.state = 'stopped'
        with patch.object(session, 'start', side_effect=fake_start) as start, patch.object(session, 'stop', side_effect=fake_stop):
            for mode in ('monitor', 'record'):
                click('#mode-' + mode)
                assert js('state.sessionMode') == mode
                click('#capture-button')
                wait_for("state.status==='recording'")
                assert start.call_args.args[-1] == mode
                click('#capture-button')
                wait_for("state.status==='stopped'")
        js('loadSample()')
        wait_for("state.source==='sample' && state.rows.length===2989")
        js("$('signal-search').value='RPM';renderSignalList()")
        assert js("document.querySelectorAll('.signal-item').length") < 103
        js("$('signal-search').value='';renderSignalList()")
        click('#zoom-in')
        assert js("state.view!==null")
        assert_visible('#time-scroll')
        assert js("getComputedStyle($('time-scroll')).webkitAppearance") == 'none'
        click('#time-scroll')
        T.QTest.keyClick(dashboard.view.focusProxy(), C.Qt.Key_Home)
        wait_for("view()[0]<.01")
        T.QTest.keyClick(dashboard.view.focusProxy(), C.Qt.Key_End)
        wait_for("view()[0]>1")
        T.QTest.qWait(150)
        window.grab().save(str(output / 'gk-tuner-logger-blue-scrollbar.png'))
        js("$('fit-view').click();$('add-graph').click()")
        assert js("!$('plot-modal').hidden && state.graphs.length===7")
        js("$('modal-save').click()")
        assert js("$('plot-modal').hidden")
        if not js("$('settings').classList.contains('open')"):
            click('#settings-toggle')
        assert js("$('settings').classList.contains('open')")
        T.QTest.qWait(200)
        window.grab().save(str(output / "gk-tuner-logging-light.png"))
        window.theme_choice.setCurrentText("Dark")
        window.apply_appearance(False)
        wait_for("document.documentElement.dataset.theme==='dark'")
        wait_for("getComputedStyle(document.querySelector('.charts')).backgroundColor==='rgb(34, 48, 64)'")
        T.QTest.qWait(200)
        window.grab().save(str(output / "gk-tuner-logging-dark.png"))
        window.palette_editor.set_colour('surface', '#243b48')
        window.palette_editor.set_colour('accent', '#9d79c5')
        window.palette_editor.set_colour('text', '#f2eaff')
        wait_for("getComputedStyle(document.querySelector('.charts')).backgroundColor==='rgb(36, 59, 72)'")
        wait_for("customPalette.accent==='#9d79c5' && customPalette.text==='#f2eaff'")
        T.QTest.qWait(150)
        window.grab().save(str(output / 'gk-tuner-logger-custom-palette.png'))
        window.palette_editor.reset()
        wait_for("getComputedStyle(document.querySelector('.charts')).backgroundColor==='rgb(34, 48, 64)'")
        wait_for("Object.keys(customPalette).length===0")
        click('.chart-actions button')
        wait_for("!$('plot-modal').hidden")
        T.QTest.qWait(150)
        window.grab().save(str(output / 'gk-tuner-logger-trace-settings.png'))
        click('#modal-close')
        # Use the actual CSV parser/import path and native export dialog, offline.
        js("const imported=parseCSV('t_s,RPM,TCO\\n0,800,50\\n1,900,51');setData(imported.fields,imported.rows,'test.csv','imported')")
        assert js("state.rows.length") == 2
        export_path = str(Path(folder) / "export.csv")
        with patch.object(W.QFileDialog, "getSaveFileName", return_value=(export_path, "CSV (*.csv)")):
            js("$('download-button').click()")
            wait_for("true")
            deadline = C.QDeadlineTimer(5000)
            while not Path(export_path).is_file() and not deadline.hasExpired():
                app.processEvents()
            assert Path(export_path).is_file(), "CSV download did not finish"
        assert "RPM" in Path(export_path).read_text()
        assert not console, console
        window.hide()
        window.deleteLater()
        app.sendPostedEvents(None, C.QEvent.DeferredDelete)
        print(json.dumps({"sample_rows": 2989, "signals": 103,
                          "checks": ["metadata", "sample", "six traces", "filter", "zoom", "fit",
                                     "trace settings", "themes", "CSV import", "CSV export",
                                     "real gear clicks", "connection controls", "monitor/CSV start/stop", "cursor alignment",
                                     "blue time slider mouse/keyboard", "saved startup scaling", "scaling after reload",
                                     "K-line/CCP round trips", "connection settings visible by default", "custom palette and reset"],
                          "window_and_scale_cases": interaction_cases,
                          "hardware_connections": 0}))


if __name__ == "__main__":
    main()
