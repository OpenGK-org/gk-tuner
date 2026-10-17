"""XDF item property editor. Edits a private XML draft until Apply or OK."""
import copy
import math
import xml.etree.ElementTree as ET

from PyQt5 import QtCore as C, QtWidgets as W

from .core import Equation, integer, format_number
from .scale_picker import ScaleCombo


def set_text(node, tag, value):
    child = node.find(tag)
    if child is None:
        child = ET.SubElement(node, tag)
    child.text = str(value)
    return child


def field(text=""):
    return W.QLineEdit(str(text))


def spin(value, low=0, high=65536):
    widget = W.QSpinBox()
    widget.setRange(low, high)
    widget.setValue(value)
    return widget


def choices(options, value):
    widget = W.QComboBox()
    for title, data in options:
        widget.addItem(title, data)
    index = widget.findData(value)
    if index < 0:
        widget.addItem(f"Existing value ({value})", value)
        index = widget.count() - 1
    widget.setCurrentIndex(index)
    return widget


OUTPUTS = [("Default", 0), ("Floating point", 1), ("Integer", 2), ("Hexadecimal", 3), ("Text", 4)]
SIZES = [(f"{bits // 8} byte{'s' if bits > 8 else ''} ({bits} bit)", bits) for bits in (8, 16, 32, 64)]


class EnumChoice(W.QComboBox):
    """Friendly names for known IDs, with lossless numeric entry for other IDs."""
    def __init__(self, options, value):
        super().__init__()
        self.setEditable(True)
        self.setInsertPolicy(W.QComboBox.NoInsert)
        for text, key in options:
            self.addItem(text, key)
        index = self.findData(value)
        if index < 0:
            self.addItem(f"XDF value {value}", value)
            index = self.count() - 1
        self.setCurrentIndex(index)
        self.setToolTip("Choose a known type, or enter a numeric XDF ID for another type. Existing IDs are preserved.")

    def value(self):
        if self.currentIndex() >= 0 and self.currentText() == self.itemText(self.currentIndex()):
            return self.currentData()
        value = integer(self.currentText())
        if not 0 <= value <= 65536:
            raise ValueError("XDF type IDs must be between 0 and 65536.")
        return value


class AxisProperties(W.QWidget):
    def __init__(self, definition, item, which, binary_data=None):
        super().__init__()
        self.which, self.definition, self.item = which, definition, item
        self.binary_data = binary_data
        axis = item.node.find(f"XDFAXIS[@id='{which}']")
        self.original = copy.deepcopy(axis) if axis is not None else ET.Element("XDFAXIS", id=which)
        axis = self.original
        data = axis.find("EMBEDDEDDATA")
        data = data if data is not None else ET.Element("EMBEDDEDDATA")
        link = axis.find("embedinfo")
        source = "linked" if link is not None and link.get("type") == "3" else "labels" if axis.findall("LABEL") or "mmedaddress" not in data.attrib else "internal"
        self.original_source = source
        count = item.cols if which == "x" else item.rows
        layout = W.QVBoxLayout(self)
        columns = W.QHBoxLayout()
        form = W.QFormLayout()
        self.count = spin(count, 1)
        self.datatype = EnumChoice([("General", 0), ("Engine speed", 6), ("Load", 23)], integer(axis.findtext("datatype")))
        self.stock_units = EnumChoice([("Custom units", 0), ("Revolutions per minute", 4), ("Milligrams", 90)], integer(axis.findtext("unittype")))
        self.units = field(axis.findtext("units", ""))
        self.output = choices(OUTPUTS, integer(axis.findtext("outputtype"), 1))
        self.source = choices([("Literal labels", "labels"), ("Linked, Scale", "linked"), ("Internal binary axis", "internal")], source)
        form.addRow("Number of columns" if which == "x" else "Number of rows", self.count)
        form.addRow("Data type", self.datatype)
        form.addRow("Stock units", self.stock_units)
        form.addRow("Column units" if which == "x" else "Row units", self.units)
        form.addRow("Label type", self.output)
        form.addRow("Label source", self.source)
        left_side = W.QVBoxLayout()
        left_side.addLayout(form)
        columns.addLayout(left_side, 1)
        linked = W.QGroupBox("Scale / normalizer link")
        linked_form = W.QFormLayout(linked)
        self.link = ScaleCombo([target for target in definition.maps if target.kind in ("XDFTABLE", "XDFCONSTANT")])
        self.link.addItem("Choose a map…", "")
        link_id = link.get("linkobjid", "").lower() if link is not None else ""
        for target in definition.maps:
            if target.kind in ("XDFTABLE", "XDFCONSTANT"):
                self.link.addItem(f"{target.title}  [{target.uid}]", target.uid.lower())
        index = self.link.findData(link_id)
        if index < 0 and link_id:
            self.link.addItem("Unresolved link " + link_id, link_id)
            index = self.link.count() - 1
        self.link.setCurrentIndex(max(0, index))
        linked_form.addRow(self.link)
        self.link_hint = W.QLabel("Linked values are edited through Edit X axis / Edit Y axis in the map toolbar.")
        self.link_hint.setWordWrap(True)
        linked_form.addRow(self.link_hint)
        linked.setSizePolicy(W.QSizePolicy.Preferred, W.QSizePolicy.Maximum)
        right_side = W.QVBoxLayout()
        right_side.addWidget(linked)
        columns.addLayout(right_side, 1)
        self.internal = W.QGroupBox("Internal axis storage")
        internal_form = W.QFormLayout(self.internal)
        self.address = field(data.get("mmedaddress", "0x0"))
        self.size = choices(SIZES, integer(data.get("mmedelementsizebits"), definition.default_bits))
        self.step = spin(integer(data.get("mmedmajorstridebits")) // 8, -65536, 65536)
        self.digits = spin(integer(axis.findtext("decimalpl"), 2), 0, 8)
        flags = integer(data.get("mmedtypeflags"), definition.default_flags)
        self.signed, self.lsb, self.floating = W.QCheckBox("Signed"), W.QCheckBox("LSB first"), W.QCheckBox("Floating point storage")
        for widget, mask in ((self.signed, 1), (self.lsb, 2), (self.floating, 0x10000)):
            widget.setChecked(bool(flags & mask))
        bits = W.QHBoxLayout()
        for widget in (self.signed, self.lsb, self.floating):
            bits.addWidget(widget)
        self.equation = field(axis.find("MATH").get("equation", "X") if axis.find("MATH") is not None else "X")
        internal_form.addRow("Address (hex)", self.address)
        internal_form.addRow("Data size", self.size)
        internal_form.addRow("Address step (bytes, 0 = packed)", self.step)
        internal_form.addRow("Decimal places", self.digits)
        internal_form.addRow(bits)
        internal_form.addRow("Conversion equation", self.equation)
        left_side.addWidget(self.internal)
        left_side.addStretch()
        right_side.addWidget(W.QLabel("Labels"))
        self.labels = W.QTableWidget(count, 1)
        self.labels.setHorizontalHeaderLabels(["Label"])
        self.labels.horizontalHeader().setStretchLastSection(True)
        labels = {integer(n.get("index")): n.get("value", "") for n in axis.findall("LABEL")}
        if source != "labels" and binary_data is not None:
            labels = dict(enumerate(definition.axis_labels(item, which, binary_data)))
        for i in range(count):
            self.labels.setItem(i, 0, W.QTableWidgetItem(labels.get(i, "")))
        right_side.addWidget(self.labels, 1)
        layout.addLayout(columns, 1)
        self.source.currentIndexChanged.connect(self.source_changed)
        self.count.valueChanged.connect(self.labels.setRowCount)
        self.count.valueChanged.connect(self.preview_link)
        self.link.currentIndexChanged.connect(self.preview_link)
        self.output.currentIndexChanged.connect(self.preview_link)
        self.digits.valueChanged.connect(self.preview_link)
        self.source_changed()

    def preview_link(self):
        if self.source.currentData() != "linked" or self.binary_data is None:
            return
        target = self.definition.by_id.get(self.link.currentData())
        if target is None or target.reason:
            return
        for i in range(self.labels.rowCount()):
            try:
                text = format_number(target.value(self.binary_data, i // target.cols, i % target.cols), self.output.currentData(), self.digits.value())
            except ValueError:
                text = "—"
            self.labels.setItem(i, 0, W.QTableWidgetItem(text))

    def source_changed(self):
        source = self.source.currentData()
        self.internal.setEnabled(source == "internal")
        self.link.setEnabled(source == "linked")
        self.labels.setEnabled(source == "labels")
        self.preview_link()

    def collect(self):
        node = copy.deepcopy(self.original)
        set_text(node, "indexcount", self.count.value())
        set_text(node, "datatype", self.datatype.value())
        set_text(node, "unittype", self.stock_units.value())
        set_text(node, "units", self.units.text())
        set_text(node, "outputtype", self.output.currentData())
        # Preserve disabled internal metadata for linked and literal axes.
        source = self.source.currentData()
        existing_link = node.find("embedinfo")
        if source != self.original_source or source == "linked":
            for old in node.findall("embedinfo"):
                node.remove(old)
        if source == "linked":
            uid = self.link.currentData()
            target = self.definition.by_id.get(uid)
            if target is None or target.reason or target.output_type == 4 or target.rows * target.cols != self.count.value():
                raise ValueError("Choose a supported linked map with exactly the same number of axis values.")
            if self.binary_data is not None:
                start, end = target.storage_bounds()
                if start < 0 or end > len(self.binary_data):
                    raise ValueError("The linked axis is outside the loaded binary.")
            updated_link = copy.deepcopy(existing_link) if existing_link is not None else ET.Element("embedinfo")
            updated_link.set("type", "3")
            updated_link.set("linkobjid", target.uid)
            node.append(updated_link)
        elif source == "internal":
            for old in node.findall("LABEL"):
                node.remove(old)
            address = int(self.address.text(), 16)
            if address < 0:
                raise ValueError("Internal axes require a nonnegative address.")
            bits = self.size.currentData()
            if self.floating.isChecked() and bits not in (32, 64):
                raise ValueError("Floating point storage requires 32 or 64 bits.")
            Equation(self.equation.text())
            data = node.find("EMBEDDEDDATA")
            if data is None:
                data = ET.SubElement(node, "EMBEDDEDDATA")
            flags = int(self.signed.isChecked()) | (2 if self.lsb.isChecked() else 0) | (0x10000 if self.floating.isChecked() else 0)
            data.set("mmedaddress", hex(address))
            data.set("mmedelementsizebits", str(bits))
            data.set("mmedtypeflags", hex(flags))
            data.set("mmedmajorstridebits", str(self.step.value() * 8))
            set_text(node, "decimalpl", self.digits.value())
            maths = node.findall("MATH")
            if len(maths) > 1 or any(m.attrib.keys() - {"equation"} for m in maths):
                raise ValueError("This axis has scoped or custom math. Its original XML must be preserved.")
            if maths:
                maths[0].set("equation", self.equation.text())
            else:
                ET.SubElement(ET.SubElement(node, "MATH", equation=self.equation.text()), "VAR", id="X")
        else:
            # Literal labels use LABEL nodes, without inventing an embedinfo enum.
            for old in node.findall("LABEL"):
                node.remove(old)
            for i in range(self.labels.rowCount()):
                cell = self.labels.item(i, 0)
                ET.SubElement(node, "LABEL", index=str(i), value=cell.text() if cell else "")
        return node


class ItemProperties(W.QDialog):
    def __init__(self, owner, item, initial_tab=0, definition=None):
        super().__init__(owner)
        self.owner, self.item = owner, item
        self.definition = definition if definition is not None else owner.definition
        self.applied = False
        self.setWindowTitle(f"Properties - {item.title} [{item.uid}]")
        self.resize(1000, 800)
        self.setMinimumSize(820, 650)
        layout = W.QVBoxLayout(self)
        self.tabs = W.QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.axis = item.node.find("XDFAXIS[@id='z']") if item.kind == "XDFTABLE" else item.node
        self.numeric = self.axis is not None and self.axis.find("EMBEDDEDDATA") is not None and not item.reason
        self.build_general()
        self.rows = self.columns = None
        if item.kind == "XDFTABLE":
            data = owner.document.data if owner.document else None
            self.rows = AxisProperties(self.definition, item, "y", data)
            self.columns = AxisProperties(self.definition, item, "x", data)
            self.rows.setEnabled(self.numeric)
            self.columns.setEnabled(self.numeric)
            self.tabs.addTab(self.rows, "Rows - Y axis")
            self.tabs.addTab(self.columns, "Columns - X axis")
        self.build_conversion()
        self.build_da()
        self.message = W.QLabel()
        if not self.numeric:
            self.message.setText("This item is inspection-only. Title, description and categories can be edited; unsupported storage and conversion XML is preserved.")
        self.message.setWordWrap(True)
        self.message.setVisible(not self.numeric)
        layout.addWidget(self.message)
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.Ok | W.QDialogButtonBox.Apply | W.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept_changes)
        buttons.rejected.connect(self.reject)
        buttons.button(W.QDialogButtonBox.Apply).clicked.connect(self.apply_changes)
        layout.addWidget(buttons)
        self.tabs.setCurrentIndex(min(initial_tab, self.tabs.count() - 1))

    def build_general(self):
        page = W.QWidget()
        form = W.QFormLayout(page)
        self.title = field(self.item.title)
        self.description = W.QPlainTextEdit(self.item.node.findtext("description", ""))
        self.description.setMaximumHeight(95)
        form.addRow("Title", self.title)
        form.addRow("Description", self.description)
        self.address = field(hex(self.item.address - self.definition.base))
        self.file_address = field(hex(self.item.address))
        self.file_address.setReadOnly(True)
        self.address.textChanged.connect(self.update_file_address)
        self.size = choices(SIZES, self.item.bits)
        self.order = choices([("Row", 0), ("Column", 4)], self.item.flags & 4)
        self.signed, self.lsb, self.floating = W.QCheckBox("Signed"), W.QCheckBox("LSB first"), W.QCheckBox("Floating point storage")
        checks = W.QHBoxLayout()
        for widget, flag in ((self.signed, 1), (self.lsb, 2), (self.floating, 0x10000)):
            widget.setChecked(bool(self.item.flags & flag))
            checks.addWidget(widget)
        data = self.axis.find("EMBEDDEDDATA") if self.numeric else ET.Element("EMBEDDEDDATA")
        self.major = spin(integer(data.get("mmedmajorstridebits")) // 8, -1048576, 1048576)
        self.minor = spin(integer(data.get("mmedminorstridebits")) // 8, -1048576, 1048576)
        self.major.setToolTip("Element step within each row or column. 0 means packed; a negative value reverses the element order.")
        self.minor.setToolTip("Distance from the last element of a line to the next line. 0 means no gap; a negative value reverses the line order.")
        self.minimum = field("" if self.item.minimum is None else self.item.minimum)
        self.maximum = field("" if self.item.maximum is None else self.item.maximum)
        self.use_min, self.use_max = W.QCheckBox("Use low range"), W.QCheckBox("Use high range")
        self.use_min.setChecked(self.item.minimum is not None)
        self.use_max.setChecked(self.item.maximum is not None)
        self.minimum.setEnabled(self.use_min.isChecked())
        self.maximum.setEnabled(self.use_max.isChecked())
        self.use_min.toggled.connect(self.minimum.setEnabled)
        self.use_max.toggled.connect(self.maximum.setEnabled)
        self.visibility = choices([("Always", 0)] + [(f"Level {i}", i) for i in range(1, 5)], integer(self.item.node.get("vislevel")))
        self.output = choices(OUTPUTS, self.item.output_type)
        self.decimals = spin(self.item.decimals, 0, 8)
        self.units = field(self.item.units)
        storage = W.QWidget()
        pair = W.QHBoxLayout(storage)
        left, right = W.QFormLayout(), W.QFormLayout()
        for name, widget in (("Address (hex)", self.address), ("Cell data size", self.size)):
            left.addRow(name, widget)
        left.addRow(checks)
        left.addRow("Major order", self.order)
        left.addRow("Major stride (bytes)", self.major)
        left.addRow("Minor stride (bytes)", self.minor)
        right.addRow("File address", self.file_address)
        right.addRow(self.use_min, self.minimum)
        right.addRow(self.use_max, self.maximum)
        right.addRow("Visibility level", self.visibility)
        right.addRow("Output type", self.output)
        right.addRow("Decimal places", self.decimals)
        right.addRow("Cell units", self.units)
        pair.addLayout(left, 1)
        pair.addLayout(right, 1)
        storage.setEnabled(self.numeric)
        form.addRow(storage)
        self.categories = []
        memberships = {integer(n.get("index")): integer(n.get("category")) for n in self.item.node.findall("CATEGORYMEM")}
        for index, title in enumerate(("Category A", "Category B", "Category C")):
            combo = choices([("Any category", 0)] + [(name, value) for value, name in self.definition.categories.items()], memberships.get(index, 0))
            form.addRow(title, combo)
            self.categories.append(combo)
        self.tabs.addTab(page, "General")

    def update_file_address(self):
        try:
            self.file_address.setText(hex(int(self.address.text(), 16) + self.definition.base))
        except ValueError:
            self.file_address.setText("Invalid address")

    def build_conversion(self):
        page = W.QWidget()
        layout = W.QVBoxLayout(page)
        layout.addWidget(W.QLabel("Conversion"))
        maths = self.axis.findall("MATH") if self.axis is not None else []
        global_math = next((m for m in maths if integer(m.get("row"), -1) == -1 and integer(m.get("col"), -1) == -1), None)
        self.equation = field(global_math.get("equation", "X") if global_math is not None else "X")
        layout.addWidget(self.equation)
        self.equations = W.QTableWidget(self.item.rows + 1, self.item.cols + 1)
        self.equations.setHorizontalHeaderLabels(["Row equation"] + [str(i + 1) for i in range(self.item.cols)])
        self.equations.setVerticalHeaderLabels(["Column equation"] + [str(i + 1) for i in range(self.item.rows)])
        corner = W.QTableWidgetItem("")
        corner.setFlags(corner.flags() & ~C.Qt.ItemIsEditable)
        self.equations.setItem(0, 0, corner)
        for math in maths:
            r, c = integer(math.get("row"), -1), integer(math.get("col"), -1)
            if (r, c) != (-1, -1) and -1 <= r < self.item.rows and -1 <= c < self.item.cols:
                self.equations.setItem(r + 1, c + 1, W.QTableWidgetItem(math.get("equation", "X")))
        layout.addWidget(self.equations, 1)
        self.equation.setToolTip("X is the raw stored value. Nonlinear conversions are read-only.")
        page.setEnabled(self.numeric)
        self.tabs.addTab(page, "Conversion")

    def build_da(self):
        page = W.QWidget()
        layout = W.QFormLayout(page)
        self.da_links = {}
        for which, title in (("x", "X axis association"), ("y", "Y axis association"), ("z", "Value association")):
            if self.item.kind not in ("XDFTABLE", "XDFCONSTANT"):
                continue
            node = self.item.node.find(f"XDFAXIS[@id='{which}']") if self.item.kind == "XDFTABLE" else self.item.node if which == "z" else None
            if node is not None:
                link = node.find("DALINK")
                value = spin(integer(link.get("index")) if link is not None else 0, 0, 2147483647)
                layout.addRow(title, value)
                self.da_links[which] = value
        notice = W.QLabel("Stores the original XDF data-acquisition association index. Live map tracing is not implemented yet.")
        notice.setWordWrap(True)
        layout.addRow(notice)
        self.tabs.addTab(page, "DA association")

    def collect(self):
        node = copy.deepcopy(self.item.node)
        if not self.title.text().strip():
            raise ValueError("A title is required.")
        set_text(node, "title", self.title.text().strip())
        set_text(node, "description", self.description.toPlainText())
        node.set("vislevel", str(self.visibility.currentData()))
        # Preserve memberships beyond the three displayed category slots.
        for old in list(node.findall("CATEGORYMEM")):
            if integer(old.get("index")) < 3:
                node.remove(old)
        for i, combo in enumerate(self.categories):
            if combo.currentData():
                ET.SubElement(node, "CATEGORYMEM", index=str(i), category=str(combo.currentData()))
        if self.numeric:
            axis = node.find("XDFAXIS[@id='z']") if self.item.kind == "XDFTABLE" else node
            data = axis.find("EMBEDDEDDATA")
            address = int(self.address.text(), 16)
            if address < 0:
                raise ValueError("Address must be nonnegative.")
            bits = self.size.currentData()
            if self.floating.isChecked() and bits not in (32, 64):
                raise ValueError("Floating point storage requires 32 or 64 bits.")
            flags = (self.item.flags & ~0x10007) | int(self.signed.isChecked()) | (2 if self.lsb.isChecked() else 0) | (0x10000 if self.floating.isChecked() else 0) | self.order.currentData()
            data.set("mmedaddress", hex(address))
            data.set("mmedelementsizebits", str(bits))
            data.set("mmedtypeflags", hex(flags))
            data.set("mmedmajorstridebits", str(self.major.value() * 8))
            data.set("mmedminorstridebits", str(self.minor.value() * 8))
            set_text(axis, "units", self.units.text())
            set_text(axis, "decimalpl", self.decimals.value())
            set_text(axis, "outputtype", self.output.currentData())
            for tag, use, widget in (("min", self.use_min, self.minimum), ("max", self.use_max, self.maximum)):
                if use.isChecked():
                    number = float(widget.text())
                    if not math.isfinite(number):
                        raise ValueError("Range limits must be finite numbers.")
                    set_text(axis, tag, widget.text())
                else:
                    for old in axis.findall(tag):
                        axis.remove(old)
            if self.use_min.isChecked() and self.use_max.isChecked() and float(self.minimum.text()) > float(self.maximum.text()):
                raise ValueError("Low range must not exceed high range.")
            if self.rows:
                rows, cols = self.rows.count.value(), self.columns.count.value()
                if rows * cols > 65536:
                    raise ValueError("Map dimensions exceed 65,536 cells.")
                data.set("mmedrowcount", str(rows))
                data.set("mmedcolcount", str(cols))
                for which, properties in (("y", self.rows), ("x", self.columns)):
                    old = node.find(f"XDFAXIS[@id='{which}']")
                    updated = properties.collect()
                    if old is not None:
                        index = list(node).index(old)
                        node.remove(old)
                        node.insert(index, updated)
                    else:
                        node.append(updated)
            # Preserve every untouched MATH node, including unsupported variables.
            scopes = {(None, None): self.equation.text().strip()}
            for row in range(self.equations.rowCount()):
                for col in range(self.equations.columnCount()):
                    cell = self.equations.item(row, col)
                    if (row or col) and cell and cell.text().strip():
                        scopes[(row - 1 if row else None, col - 1 if col else None)] = cell.text().strip()
            old_maths = {}
            for old in axis.findall("MATH"):
                key = (integer(old.get("row"), -1), integer(old.get("col"), -1))
                old_maths[key] = old
                axis.remove(old)
            for (row, col), equation in scopes.items():
                key = (-1 if row is None else row, -1 if col is None else col)
                old = old_maths.get(key)
                if old is not None and old.get("equation", "X") == equation:
                    axis.append(old)
                else:
                    Equation(equation)
                    attrs = {"equation": equation}
                    if row is not None:
                        attrs["row"] = str(row)
                    if col is not None:
                        attrs["col"] = str(col)
                    ET.SubElement(ET.SubElement(axis, "MATH", attrs), "VAR", id="X")
        for which, widget in self.da_links.items():
            axis = node.find(f"XDFAXIS[@id='{which}']") if self.item.kind == "XDFTABLE" else node
            link = axis.find("DALINK")
            if link is None:
                link = ET.SubElement(axis, "DALINK")
            link.set("index", str(widget.value()))
        return node

    def apply_changes(self):
        try:
            node = self.collect()
            candidate = self.definition.replace_item(self.item, node, len(self.owner.document.data) if self.owner.document else None)
            uid = self.item.uid.lower()
            self.owner.apply_definition(candidate)
            self.definition = candidate
            self.item = candidate.by_id[uid]
            self.applied = True
            self.message.clear()
            self.message.hide()
            return True
        except Exception as exc:
            self.message.setText(f"Cannot apply properties: {exc}")
            self.message.show()
            return False

    def accept_changes(self):
        if self.apply_changes():
            self.accept()
