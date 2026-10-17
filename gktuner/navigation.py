"""Animated navigation that reserves space beside the workspace."""
from PyQt5 import QtCore as C


class NavigationDrawer(C.QObject):
    def __init__(self, host, panel):
        super().__init__(host)
        self.host, self.panel = host, panel
        panel.setParent(host)
        self.opened = False
        self.width = 190
        host.installEventFilter(self)
        self._extent = 0
        self.animation = C.QPropertyAnimation(self, b"extent", self)
        self.animation.setDuration(180)
        self.animation.setEasingCurve(C.QEasingCurve.OutCubic)
        self.reposition()

    def reposition(self):
        self.animation.stop()
        self.extent = self.width if self.opened else 0

    @C.pyqtProperty(int)
    def extent(self):
        return self._extent

    @extent.setter
    def extent(self, value):
        self._extent = value
        self.host.layout().setContentsMargins(value, 0, 0, 0)
        self.panel.setFixedWidth(self.width)
        self.panel.resize(self.width, self.host.height())
        self.panel.move(value - self.width, 0)
        self.panel.raise_()

    def set_open(self, opened):
        self.opened = opened
        self.animation.stop()
        self.panel.show()
        self.panel.raise_()
        self.animation.setStartValue(self.extent)
        self.animation.setEndValue(self.width if opened else 0)
        self.animation.start()

    def eventFilter(self, obj, event):
        if obj is self.host and event.type() == C.QEvent.Resize:
            self.reposition()
        return False
