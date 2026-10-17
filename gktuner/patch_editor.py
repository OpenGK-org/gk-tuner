"""Patch operation window and definition/map-entry editing dialogs."""
import copy
import xml.etree.ElementTree as ET
from PyQt5 import QtCore as C, QtWidgets as W
from .core import integer, format_number
from .patches import PatchPlan, map_entries
from .properties import set_text, choices


class PatchEntryDialog(W.QDialog):
    def __init__(self, owner, node=None):
        super().__init__(owner)
        self.owner = owner
        self.node = copy.deepcopy(node) if node is not None else ET.Element("XDFPATCHENTRY")
        self.setWindowTitle("Patch entry editor - Overwrite")
        self.resize(580, 400)
        form = W.QFormLayout(self)
        self.name = W.QLineEdit(self.node.get("name", ""))
        self.address = W.QLineEdit(self.node.get("address", "0x0"))
        self.data = W.QPlainTextEdit(self.node.get("patchdata", ""))
        self.base = W.QPlainTextEdit(self.node.get("basedata", ""))
        self.size = W.QLabel()
        for label, field in (("Entry name", self.name), ("Start address (hex)", self.address), ("Patch bytes (hex)", self.data), ("Size in bytes", self.size), ("Base bytes (optional hex)", self.base)):
            form.addRow(label, field)
        self.data.textChanged.connect(self.update_size)
        self.update_size()
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.Ok | W.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def update_size(self):
        try:
            self.size.setText(str(len(bytes.fromhex(self.data.toPlainText()))))
        except ValueError:
            self.size.setText("Invalid hex")

    def validate(self):
        try:
            address = int(self.address.text(), 16)
            if address < 0 or not self.name.text().strip():
                raise ValueError("Provide a name and a nonnegative address.")
            data = bytes.fromhex(self.data.toPlainText())
            base = bytes.fromhex(self.base.toPlainText())
            if not data or base and len(base) != len(data):
                raise ValueError("Patch bytes cannot be empty; base bytes must have the same length.")
            self.node.attrib.update(name=self.name.text().strip(), address=hex(address), datasize=hex(len(data)), patchdata=data.hex().upper())
            self.node.attrib.pop("operation", None)
            self.node.attrib.pop("op", None)
            self.node.attrib.pop("type", None)
            if base:
                self.node.set("basedata", base.hex().upper())
            else:
                self.node.attrib.pop("basedata", None)
            self.accept()
        except Exception as exc:
            self.owner.owner.error(exc)


class MapPatchDialog(W.QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.main = owner.owner
        self.setWindowTitle("Create patch entries from an XDF map")
        self.resize(850, 570)
        layout = W.QVBoxLayout(self)
        heading = W.QLabel("Build patch entries from a map")
        heading.setObjectName("patchTitle")
        layout.addWidget(heading)
        help_text = W.QLabel("Choose a map, edit its values, then Save to create patch entries. The working BIN stays unchanged.")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.maps = W.QComboBox()
        for item in self.main.definition.maps:
            if not item.reason and item.kind in ("XDFTABLE", "XDFCONSTANT"):
                self.maps.addItem(item.title, item.uid)
        layout.addWidget(self.maps)
        self.table = W.QTableWidget()
        layout.addWidget(self.table)
        self.table.itemChanged.connect(self.cell_changed)
        self.maps.currentIndexChanged.connect(self.load_map)
        self.loading = False
        self.entries = []
        self.load_map()
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.Save | W.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_entries)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_map(self):
        if hasattr(self, "buffer") and self.buffer.dirty:
            answer = W.QMessageBox.question(self, "Unsaved patch-map changes", "Discard these map edits and select another map?", W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.No)
            if answer != W.QMessageBox.Yes:
                self.maps.blockSignals(True)
                self.maps.setCurrentIndex(self.last_index)
                self.maps.blockSignals(False)
                return
        if self.maps.currentData() is None:
            return
        self.loading = True
        try:
            self.last_index = self.maps.currentIndex()
            self.item = self.main.definition.by_id[str(self.maps.currentData()).lower()]
            self.buffer = self.main.document.fork()
            self.base = bytes(self.buffer.data)
            item = self.item
            self.table.setRowCount(item.rows)
            self.table.setColumnCount(item.cols)
            self.table.setHorizontalHeaderLabels(self.main.definition.axis_labels(item, "x", self.base))
            self.table.setVerticalHeaderLabels(self.main.definition.axis_labels(item, "y", self.base))
            for r in range(item.rows):
                for c in range(item.cols):
                    value = item.raw_bits(self.base, r, c) if item.output_type == 4 else item.value(self.base, r, c)
                    self.table.setItem(r, c, W.QTableWidgetItem(format_number(value, item.output_type, item.decimals)))
            self.table.resizeColumnsToContents()
        except Exception as exc:
            self.main.error(exc)
        finally:
            self.loading = False

    def cell_changed(self, cell):
        if self.loading:
            return
        try:
            if self.item.output_type == 4:
                value = cell.text().encode("latin-1")
                if len(value) != 1:
                    raise ValueError("Enter one single-byte character per text cell.")
                self.buffer.edit_raw(self.item, [(cell.row(), cell.column(), value[0])])
            else:
                value = float(int(cell.text(), 16)) if self.item.output_type == 3 else float(cell.text())
                self.buffer.edit(self.item, [(cell.row(), cell.column(), value)])
        except Exception as exc:
            self.main.error(exc)
            self.loading = True
            cell.setText(format_number(self.item.value(self.buffer.data, cell.row(), cell.column()), self.item.output_type, self.item.decimals))
            self.loading = False

    def save_entries(self):
        try:
            if not hasattr(self, "item"):
                raise ValueError("This XDF has no supported numeric maps to use as patch entries.")
            self.entries = map_entries(self.item, self.base, self.buffer.data, self.main.definition.base)
            self.accept()
        except Exception as exc:
            self.main.error(exc)


class PatchDefinitionDialog(W.QDialog):
    def __init__(self, owner, item, definition=None):
        super().__init__(owner)
        self.owner, self.item = owner, item
        self.definition = definition if definition is not None else owner.definition
        self.node = copy.deepcopy(item.node)
        self.setWindowTitle("Patch properties and entries")
        self.resize(760, 560)
        layout = W.QVBoxLayout(self)
        form = W.QFormLayout()
        self.title = W.QLineEdit(item.title)
        self.title.setObjectName("patchName")
        self.description = W.QPlainTextEdit(self.node.findtext("description", ""))
        self.description.setMaximumHeight(90)
        form.addRow("Title", self.title)
        form.addRow("Description", self.description)
        self.visibility = choices([("Always", 0)] + [(f"Level {i}", i) for i in range(1, 5)], integer(self.node.get("vislevel")))
        form.addRow("Visibility", self.visibility)
        self.categories = []
        memberships = {integer(n.get("index")): integer(n.get("category")) for n in self.node.findall("CATEGORYMEM")}
        for i in range(3):
            field = W.QComboBox()
            field.addItem("Uncategorized", 0)
            for index, name in owner.definition.categories.items():
                field.addItem(name, index)
            field.setCurrentIndex(max(0, field.findData(memberships.get(i, 0))))
            form.addRow(f"Category {i + 1}", field)
            self.categories.append(field)
        layout.addLayout(form)
        self.entries = W.QTableWidget(0, 4)
        self.entries.setHorizontalHeaderLabels(["Name", "Address", "Bytes", "Base data"])
        self.entries.setSelectionBehavior(W.QAbstractItemView.SelectRows)
        self.entries.setEditTriggers(W.QAbstractItemView.NoEditTriggers)
        self.entries.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.entries)
        row = W.QHBoxLayout()
        for title, callback in (("New entry", self.new_entry), ("Edit entry", self.edit_entry), ("Delete entry", self.delete_entry), ("From XDF map…", self.from_map)):
            btn = W.QPushButton(title)
            btn.clicked.connect(callback)
            row.addWidget(btn)
        layout.addLayout(row)
        self.entries.itemDoubleClicked.connect(lambda: self.edit_entry())
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.Save | W.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.commit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.populate()

    def populate(self):
        nodes = self.node.findall("XDFPATCHENTRY")
        self.entries.setRowCount(len(nodes))
        for row, entry in enumerate(nodes):
            for col, value in enumerate((entry.get("name", ""), entry.get("address", ""), str(integer(entry.get("datasize"))), "Provided" if entry.get("basedata") else "Missing")):
                self.entries.setItem(row, col, W.QTableWidgetItem(value))
        self.entries.resizeColumnsToContents()

    def new_entry(self):
        dialog = PatchEntryDialog(self)
        if dialog.exec_() == W.QDialog.Accepted:
            self.node.append(dialog.node)
            self.populate()

    def edit_entry(self):
        index = self.entries.currentRow()
        if index < 0:
            return
        node = self.node.findall("XDFPATCHENTRY")[index]
        dialog = PatchEntryDialog(self, node)
        if dialog.exec_() == W.QDialog.Accepted:
            position = list(self.node).index(node)
            self.node.remove(node)
            self.node.insert(position, dialog.node)
            self.populate()

    def delete_entry(self):
        index = self.entries.currentRow()
        if index >= 0:
            self.node.remove(self.node.findall("XDFPATCHENTRY")[index])
            self.populate()

    def from_map(self):
        if self.owner.document is None:
            return self.owner.error("Open a working BIN first.")
        dialog = MapPatchDialog(self)
        if dialog.exec_() == W.QDialog.Accepted:
            self.node.extend(dialog.entries)
            self.populate()

    def commit(self):
        try:
            if not self.title.text().strip():
                raise ValueError("Enter a patch title.")
            set_text(self.node, "title", self.title.text().strip())
            set_text(self.node, "description", self.description.toPlainText())
            self.node.set("vislevel", str(self.visibility.currentData()))
            for old in self.node.findall("CATEGORYMEM"):
                self.node.remove(old)
            for index, category in enumerate(self.categories):
                ET.SubElement(self.node, "CATEGORYMEM", index=str(index), category=str(category.currentData()))
            if self.node.findall("XDFPATCHENTRY"):
                plan = PatchPlan(self.node, self.owner.definition.base)
                if self.owner.document:
                    plan.entry_states(self.owner.document.data)
            result = self.definition.replace_item(self.item, self.node)
            self.owner.apply_definition(result)
            self.accept()
        except Exception as exc:
            self.owner.error(exc)
