"""Manual browser ordering without altering definition storage or categories."""
from PyQt5 import QtCore as C, QtWidgets as W


class ItemTree(W.QTreeWidget):
    orderChanged = C.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setDragDropMode(W.QAbstractItemView.InternalMove)
        self.setDefaultDropAction(C.Qt.MoveAction)
        self.setDropIndicatorShown(True)
        self.setSortingEnabled(False)

    def move_item(self, source, parent, index):
        # Reordering never changes category memberships in the imported XDF.
        if source is None or source.parent() is not parent:
            return False
        container = parent or self.invisibleRootItem()
        old_index = container.indexOfChild(source)
        if old_index < index:
            index -= 1
        container.takeChild(old_index)
        container.insertChild(max(0, min(index, container.childCount())), source)
        self.setCurrentItem(source)
        self.orderChanged.emit()
        return True

    def dropEvent(self, event):
        if event.source() is not self or self.is_searching:
            event.ignore()
            return
        source, target = self.currentItem(), self.itemAt(event.pos())
        position = self.dropIndicatorPosition()
        if target is None:
            parent, index = None, self.topLevelItemCount()
        elif position == W.QAbstractItemView.OnItem:
            parent, index = target, target.childCount()
        else:
            parent = target.parent()
            container = parent or self.invisibleRootItem()
            index = container.indexOfChild(target) + (position == W.QAbstractItemView.BelowItem)
        if self.move_item(source, parent, index):
            event.setDropAction(C.Qt.MoveAction)
            event.accept()
        else:
            event.ignore()

    is_searching = False
