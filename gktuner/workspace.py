"""Movable MDI item windows with document-aware close handling."""
from PyQt5 import QtCore as C, QtWidgets as W


class ItemWindow(W.QMdiSubWindow):
    def __init__(self, owner, editor):
        super().__init__()
        self.owner, self.editor = owner, editor
        self.setAttribute(C.Qt.WA_DeleteOnClose)
        self.setWidget(editor)
        self.setMinimumSize(260, 120)
        self.setMouseTracking(True)
        self.drag = None

    def edges(self, pos):
        border = round(8 * getattr(self.owner, "appearance_scale", 1))
        return (pos.x() < border, pos.x() >= self.width() - border,
                pos.y() < border, pos.y() >= self.height() - border)

    def mousePressEvent(self, event):
        edges = self.edges(event.pos())
        if event.button() == C.Qt.LeftButton and any(edges):
            self.drag = (event.globalPos(), self.geometry(), edges)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag:
            start, rect, (left, right, top, bottom) = self.drag
            delta = event.globalPos() - start
            result = C.QRect(rect)
            if left:
                result.setLeft(min(rect.left() + delta.x(), rect.right() - self.minimumWidth() + 1))
            if right:
                result.setRight(max(rect.right() + delta.x(), rect.left() + self.minimumWidth() - 1))
            if top:
                result.setTop(min(rect.top() + delta.y(), rect.bottom() - self.minimumHeight() + 1))
            if bottom:
                result.setBottom(max(rect.bottom() + delta.y(), rect.top() + self.minimumHeight() - 1))
            self.owner.auto_tile.setChecked(False)
            self.setGeometry(result)
            event.accept()
            return
        left, right, top, bottom = self.edges(event.pos())
        cursor = C.Qt.SizeFDiagCursor if (left and top or right and bottom) else C.Qt.SizeBDiagCursor if (right and top or left and bottom) else C.Qt.SizeHorCursor if left or right else C.Qt.SizeVerCursor if top or bottom else C.Qt.ArrowCursor
        self.setCursor(cursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drag:
            self.drag = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        if hasattr(self.editor, "can_close") and not self.editor.can_close():
            event.ignore()
            return
        self.owner.remove_item_window(self)
        event.accept()


class ItemWorkspace(W.QMdiArea):
    resized = C.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setOption(W.QMdiArea.DontMaximizeSubWindowOnActivation, True)
        self.setHorizontalScrollBarPolicy(C.Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(C.Qt.ScrollBarAsNeeded)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()
