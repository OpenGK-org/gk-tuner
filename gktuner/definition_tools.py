"""Definition creation and header editing, preserving unedited XML metadata."""
import copy
import uuid
import xml.etree.ElementTree as ET
from PyQt5 import QtWidgets as W
from .core import Definition, integer
from .properties import set_text, SIZES, OUTPUTS, choices


def candidate_definition(definition, root):
    result = Definition(definition.path, root)
    result.saved_xml = definition.saved_xml
    result.source_path = definition.source_path
    return result


def new_item_candidate(owner, kind):
    node = ET.Element(kind)
    uid = "0x" + uuid.uuid4().hex[:8]
    while uid.lower() in owner.definition.by_id:
        uid = "0x" + uuid.uuid4().hex[:8]
    node.set("uniqueid", uid)
    set_text(node, "title", "New " + {"XDFTABLE": "table", "XDFCONSTANT": "constant", "XDFPATCH": "patch", "XDFFLAG": "flag", "XDFFUNCTION": "function"}[kind])
    set_text(node, "description", "")
    defaults = owner.definition.root.find("XDFHEADER/DEFAULTS")
    if kind != "XDFPATCH":
        axis = node
        if kind in ("XDFTABLE", "XDFFUNCTION"):
            for which in ("x", "y"):
                labels = ET.SubElement(node, "XDFAXIS", id=which)
                ET.SubElement(labels, "LABEL", index="0", value="1")
            axis = ET.SubElement(node, "XDFAXIS", id="z")
        ET.SubElement(axis, "EMBEDDEDDATA", mmedaddress=hex(max(0, -owner.definition.base)),
                      mmedelementsizebits=str(owner.definition.default_bits), mmedrowcount="1", mmedcolcount="1", mmedtypeflags=str(owner.definition.default_flags))
        set_text(axis, "decimalpl", defaults.get("sigdigits", "2") if defaults is not None else "2")
        set_text(axis, "outputtype", defaults.get("outputtype", "1") if defaults is not None else "1")
        ET.SubElement(ET.SubElement(axis, "MATH", equation="X"), "VAR", id="X")
        if kind == "XDFFLAG":
            set_text(node, "mask", "0x1")
    root = copy.deepcopy(owner.definition.root)
    root.append(node)
    definition = candidate_definition(owner.definition, root)
    return definition, definition.by_id[uid.lower()]


class NewItemDialog(W.QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.setWindowTitle("Choose new XDF item type")
        layout = W.QFormLayout(self)
        self.kind = W.QComboBox()
        for title, kind in (("Table", "XDFTABLE"), ("Constant", "XDFCONSTANT"), ("Patch", "XDFPATCH"), ("Flag / switch", "XDFFLAG"), ("Function", "XDFFUNCTION")):
            self.kind.addItem(title, kind)
        layout.addRow("Item type", self.kind)
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.Ok | W.QDialogButtonBox.Cancel)
        buttons.button(W.QDialogButtonBox.Ok).setText("Next")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class HeaderEditor(W.QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("XDF header editor")
        self.resize(650, 670)
        self.original = copy.deepcopy(owner.definition.root.find("XDFHEADER"))
        layout = W.QVBoxLayout(self)
        tabs = W.QTabWidget()
        layout.addWidget(tabs)
        general = W.QWidget()
        form = W.QFormLayout(general)
        self.fields = {}
        for title, tag in (("Title", "deftitle"), ("Description", "description"), ("Author", "author"), ("XDF version", "fileversion")):
            field = W.QPlainTextEdit(self.original.findtext(tag, "")) if tag == "description" else W.QLineEdit(self.original.findtext(tag, ""))
            self.fields[tag] = field
            form.addRow(title, field)
        base = self.original.find("BASEOFFSET")
        self.offset = W.QLineEdit(hex(integer(base.get("offset"))) if base is not None else "0x0")
        self.subtract = W.QCheckBox("Subtract")
        self.subtract.setChecked(bool(integer(base.get("subtract"))) if base is not None else False)
        form.addRow("Base offset (hex)", self.offset)
        form.addRow(self.subtract)
        region = self.original.find("REGION")
        self.bin_size = W.QLineEdit(region.get("size", "0") if region is not None else "0")
        form.addRow("BIN region size (hex)", self.bin_size)
        defaults = self.original.find("DEFAULTS")
        self.defaults = {}
        for title, key, value in (("Default cell size", "datasizeinbits", "8"), ("Significant digits", "sigdigits", "2"), ("Output type", "outputtype", "1")):
            value = integer(defaults.get(key, value)) if defaults is not None else int(value)
            if key == "sigdigits":
                field = W.QSpinBox()
                field.setRange(0, 16)
                field.setValue(value)
            else:
                field = choices(SIZES if key == "datasizeinbits" else OUTPUTS, value)
            self.defaults[key] = field
            form.addRow(title, field)
        self.checks = {}
        for title, key in (("Signed", "signed"), ("LSB first", "lsbfirst"), ("Floating point", "float")):
            field = W.QCheckBox(title)
            field.setChecked(bool(integer(defaults.get(key))) if defaults is not None else False)
            self.checks[key] = field
            form.addRow(field)
        tabs.addTab(general, "General")
        categories = W.QWidget()
        category_layout = W.QVBoxLayout(categories)
        self.categories = W.QTableWidget(0, 2)
        self.categories.setHorizontalHeaderLabels(["Index (hex, zero based)", "Name"])
        for node in self.original.findall("CATEGORY"):
            self.add_category(node.get("index", "0"), node.get("name", ""))
        self.categories.horizontalHeader().setStretchLastSection(True)
        category_layout.addWidget(self.categories)
        row = W.QHBoxLayout()
        add, remove = W.QPushButton("Add category"), W.QPushButton("Remove category")
        add.clicked.connect(lambda: self.add_category())
        remove.clicked.connect(lambda: self.categories.removeRow(self.categories.currentRow()) if self.categories.currentRow() >= 0 else None)
        row.addWidget(add)
        row.addWidget(remove)
        category_layout.addLayout(row)
        tabs.addTab(categories, "Categories")
        advanced = W.QWidget()
        advanced_layout = W.QVBoxLayout(advanced)
        self.use_xml = W.QCheckBox("Use this complete header XML instead of the General / Categories forms")
        self.xml = W.QPlainTextEdit(ET.tostring(self.original, encoding="unicode"))
        advanced_layout.addWidget(self.use_xml)
        advanced_layout.addWidget(W.QLabel("Preserves and allows editing checksum, sync-group and DA metadata. This does not implement checksum calculation or encryption."))
        advanced_layout.addWidget(self.xml)
        tabs.addTab(advanced, "Advanced XML")
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.Ok | W.QDialogButtonBox.Apply | W.QDialogButtonBox.Close)
        buttons.button(W.QDialogButtonBox.Apply).clicked.connect(self.apply)
        buttons.button(W.QDialogButtonBox.Ok).clicked.connect(lambda: self.accept() if self.apply() else None)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_category(self, index=None, name=""):
        if index is None:
            try:
                used = {int(self.categories.item(i, 0).text(), 16) for i in range(self.categories.rowCount())}
            except (ValueError, AttributeError):
                self.owner.error("Correct the existing category indices before adding a category.")
                return
            index = hex(next(i for i in range(65536) if i not in used))
        row = self.categories.rowCount()
        self.categories.insertRow(row)
        self.categories.setItem(row, 0, W.QTableWidgetItem(index))
        self.categories.setItem(row, 1, W.QTableWidgetItem(name))

    def apply(self):
        try:
            if self.use_xml.isChecked():
                text = self.xml.toPlainText()
                if "<!" in text:
                    raise ValueError("DTD and entity declarations are not supported.")
                header = ET.fromstring(text)
                if header.tag != "XDFHEADER":
                    raise ValueError("Advanced XML must contain one XDFHEADER element.")
            else:
                header = copy.deepcopy(self.original)
                for tag, field in self.fields.items():
                    set_text(header, tag, field.toPlainText() if isinstance(field, W.QPlainTextEdit) else field.text())
                for tag in ("BASEOFFSET", "DEFAULTS", "REGION"):
                    if header.find(tag) is None:
                        ET.SubElement(header, tag)
                offset, size = int(self.offset.text(), 16), int(self.bin_size.text(), 16)
                if min(offset, size) < 0:
                    raise ValueError("Offset and region size must be nonnegative.")
                header.find("BASEOFFSET").attrib.update(offset=str(offset), subtract=str(int(self.subtract.isChecked())))
                header.find("REGION").set("size", hex(size))
                defaults = header.find("DEFAULTS")
                for key, field in self.defaults.items():
                    value = field.value() if isinstance(field, W.QSpinBox) else field.currentData()
                    if value < 0 or key == "datasizeinbits" and value not in (8, 16, 32, 64):
                        raise ValueError("Invalid default data size or value.")
                    defaults.set(key, str(value))
                for key, field in self.checks.items():
                    defaults.set(key, str(int(field.isChecked())))
                for node in header.findall("CATEGORY"):
                    header.remove(node)
                seen = set()
                for row in range(self.categories.rowCount()):
                    index = int(self.categories.item(row, 0).text(), 16)
                    name = self.categories.item(row, 1).text().strip()
                    if index < 0 or index in seen or not name:
                        raise ValueError("Categories require unique nonnegative indices and names.")
                    seen.add(index)
                    ET.SubElement(header, "CATEGORY", index=hex(index), name=name)
            root = copy.deepcopy(self.owner.definition.root)
            root.remove(root.find("XDFHEADER"))
            root.insert(0, header)
            result = candidate_definition(self.owner.definition, root)
            for node in root.iter("CATEGORYMEM"):
                value = integer(node.get("category"))
                if value and value not in result.categories:
                    raise ValueError("A removed category is still used by an item. Reassign those items first.")
            for item in result.maps:
                previous = self.owner.definition.by_id.get(item.uid.lower())
                if previous is not None and not previous.reason and item.reason:
                    raise ValueError(item.reason)
                if not item.reason and self.owner.document:
                    low, high = item.storage_bounds()
                    if low < 0 or high > len(self.owner.document.data):
                        raise ValueError("The header's base offset puts an item outside the BIN.")
                    for which in ("x", "y"):
                        axis = result.internal_axis(item, which)
                        if axis is not None:
                            low, high = axis.storage_bounds()
                            if low < 0 or high > len(self.owner.document.data):
                                raise ValueError("The header's base offset puts an internal axis outside the BIN.")
            self.owner.apply_definition(result)
            if not self.owner.save_xdf_current():
                return False
            self.original = copy.deepcopy(header)
            return True
        except Exception as exc:
            self.owner.error(exc)
            return False
