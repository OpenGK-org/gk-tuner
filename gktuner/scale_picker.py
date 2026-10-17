"""Search linked scales by name or browse their XDF categories."""
from PyQt5 import QtCore as C, QtWidgets as W
from .icons import item_icon


class ScalePicker(W.QDialog):
    def __init__(self, parent, targets, selected=""):
        super().__init__(parent)
        self.setWindowTitle("Choose linked scale")
        self.resize(660, 540)
        self.uid = selected
        layout = W.QVBoxLayout(self)
        self.search = W.QLineEdit()
        self.search.setPlaceholderText("Type a map name to narrow the results…")
        layout.addWidget(self.search)
        self.tree = W.QTreeWidget()
        self.tree.setHeaderLabels(["Category / map", "Size"])
        self.tree.setColumnWidth(0, 480)
        layout.addWidget(self.tree)
        groups = {}
        for item in targets:
            group = groups.setdefault(item.category, None)
            if group is None:
                group = groups[item.category] = W.QTreeWidgetItem(self.tree, [item.category])
                group.setIcon(0, self.style().standardIcon(W.QStyle.SP_DirClosedIcon))
            child = W.QTreeWidgetItem(group, [item.title, f"{item.rows} × {item.cols}"])
            child.setData(0, C.Qt.UserRole, item.uid.lower())
            child.setIcon(0, item_icon(item.kind))
            child.setToolTip(0, item.reason or item.uid)
            if item.reason or item.output_type == 4:
                child.setDisabled(True)
            if item.uid.lower() == selected:
                self.tree.setCurrentItem(child)
                group.setExpanded(True)
        self.search.textChanged.connect(self.filter)
        self.tree.itemDoubleClicked.connect(lambda: self.choose())
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.Ok | W.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.choose)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search.setFocus()

    def filter(self, query):
        query = query.casefold().strip()
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            visible = False
            for j in range(group.childCount()):
                child = group.child(j)
                match = not query or query in (child.text(0) + " " + group.text(0)).casefold()
                child.setHidden(not match)
                visible |= match
            group.setHidden(not visible)
            group.setExpanded(bool(query))

    def choose(self):
        item = self.tree.currentItem()
        uid = item.data(0, C.Qt.UserRole) if item is not None else None
        if uid and not item.isDisabled() and not item.isHidden():
            self.uid = uid
            self.accept()


class ScaleCombo(W.QComboBox):
    def __init__(self, targets):
        super().__init__()
        self.targets = targets
        self.setToolTip("Search by map name or browse XDF categories")

    def showPopup(self):
        dialog = ScalePicker(self, self.targets, self.currentData() or "")
        if dialog.exec_() == W.QDialog.Accepted:
            self.setCurrentIndex(self.findData(dialog.uid))
        self.hidePopup()
