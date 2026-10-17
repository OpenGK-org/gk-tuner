"""The CCP logger's complete dashboard, sharing GK Tuner's adapter ownership.

The bundled frontend comes from CCP Studio. QWebChannel replaces its HTTP API,
so every capture request is serialized with the desktop application's controls.
Opening the dashboard only loads metadata and the sample capture.
"""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PyQt5 import QtCore as C, QtWidgets as W

# WebEngine must be imported before QApplication is created.
C.QCoreApplication.setAttribute(C.Qt.AA_ShareOpenGLContexts)
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile
    from PyQt5.QtWebChannel import QWebChannel
except ImportError:
    QWebEngineView = None


class LoggerBridge(C.QObject):
    appearanceChanged = C.pyqtSignal(str, float)
    paletteChanged = C.pyqtSignal(str)

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.backend = None
        self.session = None

    @C.pyqtProperty(str, constant=True)
    def preferences(self):
        return self.owner.settings.value("ccp_dashboard", "{}")

    @C.pyqtProperty(str, constant=True)
    def theme(self):
        return self.owner.theme_choice.currentText()

    @C.pyqtProperty(str, constant=True)
    def palette(self):
        return json.dumps(self.owner.palette_overrides.get(self.theme, {}))

    @C.pyqtProperty(float, constant=True)
    def scale(self):
        return self.owner.ui_scale.value() / 100

    @C.pyqtSlot(str)
    def savePreferences(self, value):
        # Only retain the frontend's small JSON preference document.
        try:
            if len(value) <= 100000 and isinstance(json.loads(value), dict):
                self.owner.settings.setValue("ccp_dashboard", value)
        except (ValueError, TypeError):
            pass

    def attach(self, backend, session):
        self.backend, self.session = backend, session

    @C.pyqtSlot(str, str, result=str)
    def request(self, path, payload):
        try:
            if self.backend is None:
                self.owner.load_can()
                if self.backend is None:
                    raise ValueError("CCP logger could not load. Check the CAN Logger folder in Settings.")
            return json.dumps(self.dispatch(path, json.loads(payload)), allow_nan=False)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    def dispatch(self, path, body):
        backend, session, owner = self.backend, self.session, self.owner
        parsed = urlparse(path)
        if parsed.path == "/api/meta":
            return {
                "signals": [{"name": s.name, "column": backend.value_column(s), "size": s.size,
                             "address": s.address, "signed": s.signed, "unit": s.unit,
                             "note": s.note, "scaled": s.scale is not None,
                             "depends_on": ["RPM"] if s.name == "INJECTOR_DUTY" else []}
                            for s in backend.SIGNAL_BY_NAME.values()] + backend.BOOST_SIGNAL_META,
                "defaults": backend.DEFAULT_SIGNALS, "max_odts": backend.logger.MAX_ODTS,
                "odt_bytes": backend.logger.ODT_PAYLOAD_BYTES, "features": ["monitor"],
                "rates": [{"prescaler": p, "hz": hz} for p, hz in backend.ALLOWED_RATES.items()],
            }
        if parsed.path == "/api/status":
            return session.snapshot()
        if parsed.path == "/api/samples":
            return session.samples(max(0, int(parse_qs(parsed.query).get("since", ["0"])[0])))
        if parsed.path == "/api/sample-capture":
            return backend.sample_data()
        if parsed.path == "/api/start":
            if owner.process.state() != C.QProcess.NotRunning or owner.flasher_panel.busy:
                raise ValueError("Wait for GKFlasher to finish before starting a capture.")
            if owner.session and owner.session is not session and owner.session.snapshot()["state"] in ("connecting", "recording", "stopping"):
                raise ValueError("Stop the K-line capture before starting CAN logging.")
            session.start(body.get("signals"), str(body.get("channel", "0")),
                          int(body.get("bitrate", 500000)), int(body.get("rate", 1)),
                          body.get("mode", "record"))
            owner.session, owner.session_kind = session, 0
            owner.log_rows, owner.log_next = [], 0
            return session.snapshot()
        if parsed.path == "/api/stop":
            session.stop()
            return session.snapshot()
        if parsed.path == "/api/download":
            output = session.snapshot()["output"]
            source = (backend.CAPTURES / output).resolve()
            if not output or source.parent != backend.CAPTURES.resolve() or not source.is_file():
                raise ValueError("No capture available.")
            target, _ = W.QFileDialog.getSaveFileName(owner, "Export capture", output, "CSV (*.csv)")
            if target and Path(target).resolve() != source:
                Path(target).write_bytes(source.read_bytes())
            return {"saved": bool(target)}
        raise ValueError("Unknown logger command.")


class LoggerDashboard(W.QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner, self.view = owner, None
        self.bridge = LoggerBridge(owner)
        self.layout = W.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.notice = W.QLabel()
        self.notice.setWordWrap(True)
        self.layout.addWidget(self.notice)

    def showEvent(self, event):
        super().showEvent(event)
        if self.view is None:
            self.load()

    def load(self):
        if QWebEngineView is None:
            self.notice.setText("The CCP dashboard requires PyQtWebEngine. Install the dependencies from requirements.txt and restart GK Tuner.")
            return
        self.notice.hide()
        self.view = QWebEngineView(self)
        self.profile = QWebEngineProfile(self.view)  # Preferences use GK Tuner settings.
        self.page = QWebEnginePage(self.profile, self.view)
        self.view.setPage(self.page)
        # Zoom belongs to the page. Setting it on the view before setPage()
        # scales the temporary default page and is lost when it is replaced.
        self.view.setZoomFactor(self.bridge.scale)
        self.web_channel = QWebChannel(self.page)
        self.web_channel.registerObject("logger", self.bridge)
        self.page.setWebChannel(self.web_channel)
        self.profile.downloadRequested.connect(self.download)
        self.view.loadFinished.connect(self.loaded)
        self.layout.addWidget(self.view)
        self.view.setUrl(C.QUrl.fromLocalFile(str(Path(__file__).parent / "logger_web" / "index.html")))

    def loaded(self, ok):
        if ok:
            self.apply_appearance()
        else:
            self.notice.setText("The CCP dashboard failed to load. Check the logger dashboard files and restart GK Tuner.")
            self.notice.show()

    def download(self, item):
        path, _ = W.QFileDialog.getSaveFileName(self.owner, "Export CSV", Path(item.path()).name, "CSV (*.csv)")
        if path:
            item.setPath(path)
            item.accept()
        else:
            item.cancel()

    def apply_appearance(self):
        if self.view is not None:
            self.view.setZoomFactor(self.bridge.scale)
        self.bridge.appearanceChanged.emit(self.bridge.theme, self.bridge.scale)
        self.bridge.paletteChanged.emit(self.bridge.palette)
