"""Compact editors tailored to definition item types."""
import math
import xml.etree.ElementTree as ET
from PyQt5 import QtCore as C, QtWidgets as W
from .core import integer, address_value, format_number
from .editor import TableEditor
from .icons import tool_icon, item_type


class ItemEditor(W.QWidget):
    def __init__(self, owner, item):
        super().__init__()
        self.owner, self.item = owner, item
        self.compare_active = False
        self.loading = False
        layout = W.QVBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 6)
        layout.setSpacing(5)
        self.toolbar = W.QToolBar()
        size = round(16 * getattr(owner, "appearance_scale", 1))
        self.toolbar.setIconSize(C.QSize(size, size))
        self.toolbar.setToolButtonStyle(C.Qt.ToolButtonIconOnly)
        style = self.style()
        self.toolbar.addAction(style.standardIcon(W.QStyle.SP_DialogCloseButton), "Close", lambda: owner.close_editor(self))
        self.compare_action = self.toolbar.addAction(tool_icon("compare"), "Compare")
        self.compare_action.setCheckable(True)
        self.compare_action.triggered.connect(self.toggle_compare)
        self.toolbar.addAction(style.standardIcon(W.QStyle.SP_FileDialogInfoView), "Properties", lambda: owner.open_properties(self.item))
        layout.addWidget(self.toolbar)
        self.title = W.QLabel(item.title)
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.info = W.QLabel()
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.inspect = W.QPlainTextEdit()
        self.inspect.setReadOnly(True)
        self.inspect.hide()

    def preferred_size(self):
        return C.QSize(350, self.layout().sizeHint().height())

    def toggle_compare(self, checked):
        if checked and self.owner.compare is None:
            self.owner.open_compare()
        self.compare_active = checked and self.owner.compare is not None
        self.compare_action.setChecked(self.compare_active)
        self.refresh()
        self.owner.fit_editor(self)

    def refresh(self):
        self.title.setText(self.item.title)
        self.inspect.setPlainText(ET.tostring(self.item.node, encoding="unicode"))
        if hasattr(self, "subwindow"):
            self.subwindow.setWindowTitle(("[COMPARE] " if self.compare_active else "") + self.item.title)


class ConstantEditor(ItemEditor):
    def __init__(self, owner, item):
        super().__init__(owner, item)
        self.pending = False
        self.slider = W.QSlider(C.Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.input = W.QDoubleSpinBox()
        self.input.setLocale(C.QLocale.c())
        self.input.setDecimals(max(item.decimals, 5))
        self.input.setRange(-1e15, 1e15)
        self.input.setSuffix(" " + item.units if item.units else "")
        self.reference = W.QLabel()
        self.reference.setObjectName("compareBanner")
        self.copy_button = W.QPushButton("Copy reference")
        self.copy_button.clicked.connect(self.copy_reference)
        self.save_button = W.QPushButton("Save")
        self.save_button.setToolTip("Apply this value to the working binary. Save binary as… writes it to a file.")
        self.save_button.clicked.connect(self.commit)
        self.cancel_button = W.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel)
        layout = self.layout()
        layout.addWidget(self.slider)
        layout.addWidget(self.input)
        layout.addWidget(self.reference)
        row = W.QHBoxLayout()
        for widget in (self.copy_button, self.save_button, self.cancel_button):
            row.addWidget(widget)
        layout.addLayout(row)
        self.input.valueChanged.connect(self.value_changed)
        self.slider.valueChanged.connect(self.slider_changed)
        self.bounds = None

    def value_changed(self, value):
        if self.loading:
            return
        self.pending = True
        self.info.setText("Value pending - Save applies it to the working binary")
        if self.bounds:
            low, high = self.bounds
            self.slider.blockSignals(True)
            self.slider.setValue(round(1000 * (value - low) / (high - low)))
            self.slider.blockSignals(False)

    def slider_changed(self, value):
        if self.bounds and not self.loading:
            low, high = self.bounds
            self.input.setValue(low + (high - low) * value / 1000)

    def refresh(self):
        super().refresh()
        self.loading = True
        try:
            item, doc = self.item, self.owner.document
            if item.reason or doc is None:
                raise ValueError(item.reason or "Open a binary to edit this constant.")
            value = item.value(doc.data, 0, 0)
            a, b = item.equation.affine()
            if item.flags & 0x10000:
                low, high = -1e15, 1e15
            else:
                raw_low = -(1 << (item.bits - 1)) if item.flags & 1 else 0
                raw_high = (1 << (item.bits - (1 if item.flags & 1 else 0))) - 1
                low, high = sorted((a * raw_low + b, a * raw_high + b))
            low = max(low, item.minimum) if item.minimum is not None else low
            high = min(high, item.maximum) if item.maximum is not None else high
            if not math.isfinite(low + high) or low > high:
                raise ValueError("Invalid constant limits.")
            # Include an existing out-of-limit value so merely opening does not alter it.
            self.input.setRange(min(low, value), max(high, value))
            if not self.pending:
                self.input.setValue(value)
            self.bounds = (low, high) if low < high and high - low < 1e12 else None
            self.slider.setVisible(self.bounds is not None)
            if self.bounds:
                self.slider.setValue(round(1000 * (self.input.value() - low) / (high - low)))
            self.input.setEnabled(True)
            self.save_button.setEnabled(True)
            ref = item.value(self.owner.compare, 0, 0) if self.owner.compare is not None else None
            self.reference.setText(f"Reference: {format_number(ref, item.output_type, item.decimals)} {item.units}" if ref is not None else "No comparison binary")
            self.reference.setVisible(self.compare_active)
            self.copy_button.setVisible(self.compare_active)
            self.copy_button.setEnabled(ref is not None)
            self.info.setText("Value pending - Save applies it to the working binary" if self.pending else f"0x{item.address:X} - {item.bits}-bit - {item.units}")
        except Exception as exc:
            self.info.setText(str(exc))
            self.input.setEnabled(False)
            self.slider.hide()
            self.save_button.setEnabled(False)
            self.copy_button.setEnabled(False)
        finally:
            self.loading = False

    def copy_reference(self):
        if self.owner.compare is not None:
            self.input.setValue(self.item.value(self.owner.compare, 0, 0))

    def commit(self):
        if not self.pending:
            return True
        try:
            self.owner.document.edit(self.item, [(0, 0, self.input.value())])
            self.pending = False
            self.owner.refresh_map()
            return True
        except Exception as exc:
            self.owner.error(exc)
            return False

    def cancel(self):
        self.pending = False
        self.refresh()
        self.owner.close_editor(self)

    def can_close(self):
        if not self.pending:
            return True
        answer = W.QMessageBox.question(self, "Pending constant value", "Apply this value to the working binary?", W.QMessageBox.Save | W.QMessageBox.Discard | W.QMessageBox.Cancel, W.QMessageBox.Save)
        if answer == W.QMessageBox.Save:
            return self.commit()
        if answer == W.QMessageBox.Discard:
            self.pending = False
            self.refresh()
            return True
        return False


class DefinitionInspector(ItemEditor):
    """Dedicated, honest inspection for formats without validated write adapters."""
    def __init__(self, owner, item):
        super().__init__(owner, item)
        self.compare_action.setVisible(False)
        self.fields = W.QFormLayout()
        self.layout().addLayout(self.fields)
        self.layout().addWidget(self.inspect)
        self.inspect.show()
        self.inspect.setMaximumHeight(150)

    def refresh(self):
        super().refresh()
        while self.fields.rowCount():
            self.fields.removeRow(0)
        self.info.setText(f"{item_type(self.item.kind)} - Inspection only - {self.item.reason}")
        node = self.item.node
        if self.item.kind == "XDFFLAG":
            control = W.QCheckBox("Enabled")
            control.setEnabled(False)
            data = node.find("EMBEDDEDDATA")
            try:
                address = address_value(data.get("mmedaddress")) + self.owner.definition.base
                bits = integer(data.get("mmedelementsizebits"), 8)
                mask = integer(node.findtext("mask"))
                flags = integer(data.get("mmedtypeflags"), self.owner.definition.default_flags)
                if bits not in (8, 16, 32, 64) or not self.owner.document or address < 0 or address + bits // 8 > len(self.owner.document.data):
                    raise ValueError("Flag storage unavailable")
                raw = int.from_bytes(self.owner.document.data[address:address + bits // 8], "little" if flags & 2 else "big")
                control.setChecked(bool(mask) and raw & mask == mask)
                self.fields.addRow("Address", W.QLabel(f"0x{address:X}"))
                self.fields.addRow("Mask", W.QLabel(hex(mask)))
            except (ValueError, AttributeError):
                control.setText("State unavailable")
            self.fields.addRow("Switch", control)
        elif self.item.kind == "XDFPATCH":
            entries = node.findall("XDFPATCHENTRY")
            self.fields.addRow("Patch entries", W.QLabel(str(len(entries))))
            for entry in entries[:6]:
                text = f"{entry.get('address', '?')} - {entry.get('datasize', '?')} bytes"
                self.fields.addRow(entry.get("name", "Entry"), W.QLabel(text))
        elif self.item.kind == "XDFFUNCTION":
            for axis in node.findall("XDFAXIS"):
                self.fields.addRow(axis.get("id", "Axis").upper(), W.QLabel(axis.findtext("units", "See definition below")))

    def preferred_size(self):
        return C.QSize(420, min(420, self.layout().sizeHint().height()))


class FlagEditor(DefinitionInspector):
    pass


class TextEditor(TableEditor):
    is_text_editor = True

    def __init__(self, owner, item):
        super().__init__(owner, item)
        for widget in (self.views, self.operations, self.map_title, self.map_details, self.change_info):
            widget.hide()
        for action in (self.graph_action, self.x_action, self.y_action, self.raw_action):
            action.setVisible(False)
        self.compare_settings_action.setVisible(False)
        self.text_title = W.QLabel(item.title)
        self.text_title.setWordWrap(True)
        self.text_title.setObjectName("tableTitle")
        self.body = W.QLineEdit()
        self.body.setMaxLength(65536)
        self.body.setToolTip("Single-byte Latin-1 text; ASCII characters use their normal byte values")
        self.padding = W.QComboBox()
        self.padding.addItem("Pad with 00", 0)
        self.padding.addItem("Pad with spaces (20)", 32)
        self.text_info = W.QLabel()
        self.text_info.setWordWrap(True)
        self.layout().addWidget(self.text_title)
        self.layout().addWidget(self.body)
        self.layout().addWidget(self.padding)
        self.layout().addWidget(self.text_info)
        self.body.textEdited.connect(self.edit_text)
        self.padding.currentIndexChanged.connect(lambda: self.edit_text(self.body.text()))

    def preferred_size(self):
        return C.QSize(550, 190)

    def edit_text(self, text):
        if self.loading or self.compare_active or self.buffer is None:
            return
        try:
            data = text.encode("latin-1")
            item = self.item
            capacity = item.rows * item.cols
            if len(data) > capacity:
                raise ValueError(f"Text exceeds this item's {capacity}-byte storage.")
            data = data.ljust(capacity, bytes([self.padding.currentData()]))
            self.buffer.edit_raw(item, [(r, c, data[r * item.cols + c]) for r in range(item.rows) for c in range(item.cols)])
        except (ValueError, UnicodeError) as exc:
            self.owner.error(exc)
        self.owner.refresh_map()

    def refresh(self):
        self.sync_buffer()
        self.loading = True
        try:
            item = self.item
            self.text_title.setText(item.title)
            self.save_action.setEnabled(self.buffer is not None)
            comparing = self.compare_active and self.owner.compare is not None
            data = self.owner.compare if comparing else self.buffer.data if self.buffer is not None else None
            self.body.setReadOnly(comparing or data is None)
            self.padding.setEnabled(not comparing and data is not None)
            if data is not None:
                raw = bytes(item.raw_bits(data, r, c) for r in range(item.rows) for c in range(item.cols))
                position = self.body.cursorPosition()
                self.body.setText(raw.decode("latin-1").rstrip("\x00"))
                self.body.setCursorPosition(min(position, len(self.body.text())))
                self.text_info.setText(f"{len(raw)} bytes - single-byte text - 0x{item.address:X}" + (f" - Reference: {self.owner.compare_name} (read only)" if comparing else " - Save accepts this text into the working BIN"))
            else:
                self.body.clear()
                self.text_info.setText("Open a BIN to edit this text.")
            if hasattr(self, "subwindow"):
                self.subwindow.setWindowTitle(("[COMPARE] " if comparing else "") + item.title + (" *" if self.pending else ""))
        except Exception as exc:
            self.text_info.setText(str(exc))
        finally:
            self.loading = False


class PatchEditor(ItemEditor):
    def __init__(self, owner, item):
        super().__init__(owner, item)
        self.title.setObjectName("patchTitle")
        self.info.setObjectName("patchStatus")
        self.description = W.QLabel()
        self.description.setWordWrap(True)
        self.layout().insertWidget(2, self.description)
        self.reference = W.QLabel()
        self.reference.setWordWrap(True)
        self.layout().addWidget(self.reference)
        self.layout().addWidget(W.QLabel("Entries differing from base"))
        self.empty = W.QLabel()
        self.empty.setWordWrap(True)
        self.layout().addWidget(self.empty)
        self.entries = W.QTableWidget(0, 2)
        self.entries.setHorizontalHeaderLabels(["Entry", "Address"])
        self.entries.setEditTriggers(W.QAbstractItemView.NoEditTriggers)
        self.entries.horizontalHeader().setStretchLastSection(True)
        self.entries.setMaximumHeight(300)
        self.layout().addWidget(self.entries)
        row = W.QHBoxLayout()
        self.apply_button, self.remove_button = W.QPushButton("Apply patch"), W.QPushButton("Remove patch")
        self.force_button = W.QPushButton("Force apply…")
        self.force_button.setToolTip("Override base-data mismatches after reviewing a warning.")
        edit = W.QPushButton("Edit patch…")
        self.apply_button.clicked.connect(lambda: self.apply_patch())
        self.force_button.clicked.connect(lambda: self.apply_patch(force=True))
        self.remove_button.clicked.connect(lambda: self.apply_patch(remove=True))
        edit.clicked.connect(lambda: owner.open_properties(self.item))
        for control in (self.apply_button, self.force_button, self.remove_button, edit):
            row.addWidget(control)
        self.layout().addLayout(row)

    def preferred_size(self):
        return C.QSize(730, min(620, 310 + self.entries.rowCount() * 27))

    def refresh(self):
        super().refresh()
        self.description.setText(self.item.node.findtext("description", ""))
        self.description.setVisible(bool(self.description.text()))
        self.apply_button.setEnabled(False)
        self.force_button.setEnabled(False)
        self.remove_button.setEnabled(False)
        self.entries.setRowCount(0)
        try:
            from .patches import PatchPlan
            plan = PatchPlan(self.item.node, self.owner.definition.base)
            if self.owner.document is None:
                raise ValueError("Open a BIN to check or apply this patch.")
            states = plan.entry_states(self.owner.document.data)
            state = plan.state(self.owner.document.data)
            self.info.setText("Working BIN: " + state)
            self.reference.setText((self.owner.compare_name + ": " + plan.state(self.owner.compare)) if self.owner.compare is not None else "No compare BIN")
            mismatches = [entry for entry in plan.entries if entry.base is not None and bytes(self.owner.document.data[entry.address:entry.address + len(entry.base)]) != entry.base]
            self.entries.setRowCount(len(mismatches))
            for row, entry in enumerate(mismatches):
                for col, text in enumerate((entry.name, f"0x{entry.address:X}")):
                    self.entries.setItem(row, col, W.QTableWidgetItem(text))
            self.entries.resizeColumnsToContents()
            missing = sum(entry.base is None for entry in plan.entries)
            count = len(mismatches)
            self.empty.setText((f"{count} entry differs from supplied base data." if count == 1 else f"{count} entries differ from supplied base data.") if mismatches else "All supplied base bytes match." if any(entry.base is not None for entry in plan.entries) else "No base data supplied for comparison.")
            if missing:
                self.empty.setText(self.empty.text() + f" {missing} entries have no base data.")
            self.entries.setVisible(bool(mismatches))
            safe = "Mismatch" not in states
            self.force_button.setEnabled(not safe)
            self.apply_button.setEnabled(safe and not all(s == "Applied" for s in states))
            self.remove_button.setEnabled(safe and any(s == "Applied" for s in states) and all(e.base is not None for e in plan.entries))
        except Exception as exc:
            self.info.setText(str(exc))

    def apply_patch(self, remove=False, force=False):
        try:
            from .patches import PatchPlan
            plan = PatchPlan(self.item.node, self.owner.definition.base)
            unknown = any(entry.base is None for entry in plan.entries)
            if force and not remove:
                differences = plan.mismatches(self.owner.document.data)
                answer = W.QMessageBox.warning(self, "Force apply patch", f"Expected base data does not match the working BIN ({self.owner.document.path.name}).\n\nForce apply will overwrite every entry with its patch bytes, including mismatched bytes. The listed entries contain {len(differences)} differing bytes. Review those entries before continuing.\n\nUndo restores the exact previous bytes. Remove patch restores the declared base data, which may differ from those previous bytes.\n\nForce apply to the working BIN?", W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.No)
                if answer != W.QMessageBox.Yes:
                    return False
            elif unknown and not remove:
                answer = W.QMessageBox.question(self, "Patch has no complete base data", "Some original bytes are unknown. Expected-byte safety cannot be verified for those entries. Apply these overwrite entries to the working BIN?", W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.No)
                if answer != W.QMessageBox.Yes:
                    return False
            plan.apply(self.owner.document, remove=remove, allow_unverified=(unknown or force) and not remove, force=force)
            self.owner.refresh_map()
            self.owner.fit_editor(self)
            return True
        except Exception as exc:
            self.owner.error(exc)
            return False


class FunctionEditor(DefinitionInspector):
    pass


def make_editor(owner, item):
    if item.output_type == 4 and not item.reason:
        return TextEditor(owner, item)
    if item.kind == "XDFCONSTANT" or item.kind == "XDFTABLE" and item.rows == item.cols == 1 and not item.reason:
        return ConstantEditor(owner, item)
    if item.kind == "XDFTABLE":
        return TableEditor(owner, item)
    return {"XDFFLAG": FlagEditor, "XDFPATCH": PatchEditor, "XDFFUNCTION": FunctionEditor}.get(item.kind, DefinitionInspector)(owner, item)
