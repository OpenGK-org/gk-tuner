"""Independent item windows sharing one binary and definition document."""
import xml.etree.ElementTree as ET
from .core import format_number
from .appearance import heatmap_color, contrast_text
from .icons import tool_icon
from .graph import SurfacePlot, GraphWindow

from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W


def comparison_value(current, reference, mode):
    if mode == "Absolute":
        return reference
    if mode == "Difference":
        return current - reference
    if mode == "Percentage":
        return (current - reference) / reference * 100 if reference != 0 else None
    raise ValueError("Unknown comparison mode.")


class SelectionDelegate(W.QStyledItemDelegate):
    def __init__(self, editor):
        super().__init__(editor.table)
        self.editor = editor

    def createEditor(self, parent, option, index):
        widget = W.QLineEdit(parent)
        widget.targets = self.editor.selected_cells() or [(index.row(), index.column())]
        return widget

    def setEditorData(self, widget, index):
        widget.setText(str(index.data(C.Qt.EditRole)))
        widget.selectAll()

    def setModelData(self, widget, model, index):
        self.editor.owner.apply_table_value(self.editor, widget.targets, widget.text())


class TableEditor(W.QWidget):
    def __init__(self, owner, item):
        super().__init__()
        self.owner, self.item = owner, item
        self.loading = False
        self.compare_active = False
        self.compare_mode = "Absolute"
        self.axis_parent = None
        self.graph_window = None
        self.buffer = None
        self.source_document = None
        self.raw_view = False
        layout = W.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.setSizeConstraint(W.QLayout.SetNoConstraint)
        self.toolbar = W.QToolBar()
        icon_size = round(16 * getattr(owner, "appearance_scale", 1.))
        self.toolbar.setIconSize(C.QSize(icon_size, icon_size))
        self.toolbar.setToolButtonStyle(C.Qt.ToolButtonIconOnly)
        style = self.style()

        def action(title, icon, callback):
            result = self.toolbar.addAction(style.standardIcon(icon), title)
            result.triggered.connect(callback)
            return result

        self.save_action = action("Save table and close", W.QStyle.SP_DialogSaveButton, self.save_and_close)
        self.save_action.setIcon(tool_icon("save_bin"))
        self.save_action.setToolTip("Save this table to the working BIN and close. Save BIN writes the file.")
        self.close_action = action("Close", W.QStyle.SP_DialogCloseButton, lambda: owner.close_editor(self))
        self.close_action.setToolTip("Close this table; unsaved table edits require Save or Discard.")
        self.toolbar.addSeparator()
        self.graph_action = action("Show 3D Graph", W.QStyle.SP_ComputerIcon, self.toggle_graph)
        self.graph_action.setCheckable(True)
        self.graph_action.setIcon(tool_icon("graph"))
        self.compare_action = action("Compare", W.QStyle.SP_FileDialogDetailedView, self.toggle_compare)
        self.compare_action.setCheckable(True)
        self.compare_action.setIcon(tool_icon("compare"))
        self.compare_settings = W.QToolButton()
        self.compare_settings.setText("Absolute")
        self.compare_settings.setToolTip("Comparison settings: absolute reference values, working minus reference, or percentage difference.")
        self.compare_settings.setPopupMode(W.QToolButton.InstantPopup)
        menu = W.QMenu(self)
        group = W.QActionGroup(menu)
        group.setExclusive(True)
        for mode in ("Absolute", "Difference", "Percentage"):
            option = menu.addAction(mode)
            option.setCheckable(True)
            option.setChecked(mode == self.compare_mode)
            group.addAction(option)
            option.triggered.connect(lambda checked=False, value=mode: self.set_compare_mode(value))
        self.compare_settings.setMenu(menu)
        self.compare_settings_action = self.toolbar.addWidget(self.compare_settings)
        self.toolbar.addSeparator()
        self.x_action = action("Edit X axis", W.QStyle.SP_ArrowRight, lambda: owner.edit_axis(self, "x"))
        self.y_action = action("Edit Y axis", W.QStyle.SP_ArrowUp, lambda: owner.edit_axis(self, "y"))
        self.x_action.setIcon(tool_icon("x"))
        self.y_action.setIcon(tool_icon("y"))
        self.properties_action = action("Properties", W.QStyle.SP_FileDialogInfoView, lambda: owner.open_properties(self.item))
        self.raw_action = self.toolbar.addAction(tool_icon("hex"), "Raw hexadecimal (no conversion)")
        self.raw_action.setCheckable(True)
        self.raw_action.setToolTip("Show and edit zero-padded raw storage hex, bypassing conversion. + / − step one stored count; values do not wrap.")
        self.raw_action.triggered.connect(self.toggle_raw)
        layout.addWidget(self.toolbar)
        self.map_title = W.QLabel()
        self.map_title.setObjectName("tableTitle")
        self.map_title.setWordWrap(True)
        self.map_details = W.QLabel()
        self.map_details.setObjectName("muted")
        self.map_details.setWordWrap(True)
        layout.addWidget(self.map_title)
        layout.addWidget(self.map_details)
        self.views = W.QStackedWidget()
        self.table = W.QTableWidget()
        self.table.setSelectionMode(W.QAbstractItemView.ExtendedSelection)
        self.table.installEventFilter(self)
        self.table.setItemDelegate(SelectionDelegate(self))
        self.table.itemChanged.connect(lambda cell: owner.editor_cell_changed(self, cell))
        self.table.itemSelectionChanged.connect(self.sync_graph_selection)
        self.views.addWidget(self.table)
        self.surface = SurfacePlot(self)
        self.plot = self.surface
        self.inspect = W.QPlainTextEdit(self)
        self.inspect.setReadOnly(True)
        self.inspect.hide()
        layout.addWidget(self.views, 1)
        self.table.horizontalHeader().sectionDoubleClicked.connect(lambda index: owner.edit_axis_value(self, "x", index))
        self.table.verticalHeader().sectionDoubleClicked.connect(lambda index: owner.edit_axis_value(self, "y", index))
        operations = W.QHBoxLayout()
        self.op = W.QComboBox()
        self.op.addItems(["Set selected", "Add to selected", "Multiply selected", "Percent change", "Interpolate rows", "Interpolate columns"])
        self.amount = W.QDoubleSpinBox()
        self.amount.setRange(-1000000000, 1000000000)
        self.amount.setDecimals(5)
        self.amount.setLocale(C.QLocale.c())
        self.op.setMinimumContentsLength(7)
        self.op.setSizeAdjustPolicy(W.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.op.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Preferred)
        self.amount.setMinimumWidth(45)
        self.amount.setMaximumWidth(115)
        operations.addWidget(self.op)
        operations.addWidget(self.amount)
        self.apply_button = W.QPushButton("Apply")
        self.apply_button.clicked.connect(lambda: self.run_action(owner.batch_edit))
        operations.addWidget(self.apply_button)
        export = W.QPushButton("CSV")
        export.setToolTip("Export this item as CSV")
        export.clicked.connect(lambda: self.run_action(owner.export_map))
        operations.addWidget(export)
        self.operations = W.QWidget()
        self.operations.setLayout(operations)
        operations.setContentsMargins(0, 0, 0, 0)
        operations.setSpacing(3)
        layout.insertWidget(layout.indexOf(self.views), self.operations)
        self.change_info = W.QLabel()
        self.change_info.setObjectName("muted")
        self.change_info.setWordWrap(True)
        layout.addWidget(self.change_info)

    def run_action(self, callback):
        if hasattr(self, "subwindow"):
            self.owner.mdi.setActiveSubWindow(self.subwindow)
            self.owner.bind_editor(self)
        callback()

    @property
    def pending(self):
        return self.buffer is not None and self.buffer.dirty

    def sync_buffer(self):
        document = self.owner.document
        if document is None:
            self.buffer = self.source_document = None
        elif self.source_document is not document or self.buffer is None or not self.pending and bytes(document.data) != self.buffer.saved:
            self.source_document = document
            self.buffer = document.fork()

    def commit(self):
        if not self.pending:
            return True
        try:
            if self.source_document is not self.owner.document:
                raise ValueError("The working BIN changed; reopen this table.")
            before, after = self.buffer.saved, self.buffer.data
            segments, start = [], None
            for i in range(len(after) + 1):
                differs = i < len(after) and before[i] != after[i]
                if differs and start is None:
                    start = i
                elif not differs and start is not None:
                    segments.append((start, before[start:i], after[start:i]))
                    start = None
            self.owner.document.write_segments(segments)
            self.buffer = self.owner.document.fork()
            self.owner.refresh_map()
            return True
        except Exception as exc:
            self.owner.error(exc)
            return False

    def save_and_close(self):
        if self.commit():
            self.owner.close_editor(self)

    def eventFilter(self, obj, event):
        if obj is self.table and event.type() == C.QEvent.KeyPress and not event.modifiers() & (C.Qt.ControlModifier | C.Qt.AltModifier | C.Qt.MetaModifier):
            if event.key() in (C.Qt.Key_Plus, C.Qt.Key_Minus) or event.text() in ("+", "-"):
                self.nudge(1 if event.key() == C.Qt.Key_Plus or event.text() == "+" else -1)
                return True
        return super().eventFilter(obj, event)

    def nudge(self, direction):
        if self.compare_active or self.buffer is None or self.item is None or self.item.reason:
            return
        cells = self.selected_cells()
        if not cells:
            return
        try:
            self.buffer.edit_raw(self.item, [(r, c, self.item.raw_bits(self.buffer.data, r, c) + direction) for r, c in cells])
        except Exception as exc:
            self.owner.error(exc)
        self.owner.refresh_map()

    def toggle_raw(self, checked):
        self.raw_view = checked
        self.refresh()
        self.table.setFocus(C.Qt.OtherFocusReason)
        if hasattr(self, "subwindow"):
            self.owner.fit_editor(self)

    def can_close(self):
        if not self.pending:
            return True
        answer = W.QMessageBox.question(self, "Unsaved table changes", f"Changes to '{self.item.title}' have not been saved to the working BIN. Closing without saving will discard them.", W.QMessageBox.Save | W.QMessageBox.Discard | W.QMessageBox.Cancel, W.QMessageBox.Save)
        if answer == W.QMessageBox.Save:
            return self.commit()
        if answer == W.QMessageBox.Discard:
            self.buffer = self.owner.document.fork()
            self.refresh()
            return True
        return False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "toolbar"):
            self.toolbar.setToolButtonStyle(C.Qt.ToolButtonIconOnly)

    def toggle_graph(self, checked):
        if checked:
            if self.graph_window is None:
                self.graph_window = GraphWindow(self)
            self.graph_window.sync()
            self.graph_window.show()
            self.graph_window.raise_()
            self.graph_window.activateWindow()
        elif self.graph_window is not None:
            self.graph_window.close()

    def selected_cells(self):
        return sorted({(i.row(), i.column()) for i in self.table.selectedIndexes()})

    def sync_graph_selection(self):
        if not self.loading:
            self.surface.cancel_drag()
            self.surface.selected = set(self.selected_cells())
            self.surface.update()

    def close_graph(self):
        if self.graph_window is not None:
            self.graph_window.close()
            self.graph_window.deleteLater()
            self.graph_window = None

    def preferred_size(self):
        width = self.table.horizontalHeader().length() + self.table.verticalHeader().sizeHint().width() + 8
        height = self.table.verticalHeader().length() + self.table.horizontalHeader().sizeHint().height() + 8
        chrome = self.toolbar.sizeHint().height() + self.operations.sizeHint().height() + 12
        if self.map_details.isVisibleTo(self):
            chrome += self.map_details.sizeHint().height() + 3
        return C.QSize(max(285, width), max(110, height + chrome))

    def toggle_compare(self, checked):
        self.compare_active = checked
        if checked and self.owner.compare is None:
            self.owner.open_compare()
        if self.owner.compare is None:
            self.compare_active = False
            self.compare_action.setChecked(False)
        self.refresh()
        if hasattr(self, "subwindow"):
            self.owner.fit_editor(self)

    def set_compare_mode(self, mode):
        self.compare_mode = mode
        self.compare_settings.setText(mode)
        for option in self.compare_settings.menu().actions():
            option.setChecked(option.text() == mode)
        self.refresh()
        if hasattr(self, "subwindow"):
            self.owner.fit_editor(self)

    def refresh(self):
        self.sync_buffer()
        self.loading = True
        selection = [(i.row(), i.column()) for i in self.table.selectedIndexes()]
        current = (self.table.currentRow(), self.table.currentColumn())
        scroll = self.table.verticalScrollBar().value(), self.table.horizontalScrollBar().value()
        try:
            item, doc = self.item, self.buffer
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.plot.values = self.surface.values = []
            self.save_action.setEnabled(doc is not None)
            for control in (self.close_action, self.graph_action, self.compare_action, self.properties_action):
                control.setEnabled(item is not None)
            self.x_action.setEnabled(item is not None and item.kind == "XDFTABLE")
            self.y_action.setEnabled(item is not None and item.kind == "XDFTABLE")
            self.compare_settings.setEnabled(item is not None)
            self.raw_action.setEnabled(item is not None and not self.compare_active)
            self.compare_action.setEnabled(item is not None and not self.raw_view)
            self.compare_settings.setEnabled(item is not None and not self.raw_view)
            self.change_info.setText(self.owner.document_status)
            if item is None:
                self.map_title.setText("Open a definition item to begin")
                self.map_details.setText("Import an XDF to browse constants, tables, functions, patches, and flags / switches.")
                self.inspect.clear()
                return
            self.map_title.setText(item.title)
            comparing = self.compare_active and self.owner.compare is not None
            self.map_details.setObjectName("compareBanner" if comparing else "workingBanner")
            self.map_details.style().unpolish(self.map_details)
            self.map_details.style().polish(self.map_details)
            if hasattr(self, "subwindow"):
                self.subwindow.setWindowTitle((f"[COMPARE - {self.compare_mode}] " if comparing else "[HEX] " if self.raw_view else "") + item.title + (" *" if self.pending else ""))
            self.inspect.setPlainText(ET.tostring(item.node, encoding="unicode"))
            self.map_details.setText(item.reason or f"0x{item.address:X} - {item.rows} × {item.cols} - {item.bits}-bit {'little' if item.flags & 2 else 'big'} endian - {item.units or 'no units'} - {item.equation.source}")
            self.apply_button.setEnabled(not self.compare_active and not self.raw_view and not item.reason and doc is not None)
            for control in (self.op, self.amount):
                control.setEnabled(not self.raw_view)
            if item.reason or not doc:
                self.map_details.show()
                return
            working = [[(item.raw_bits if self.raw_view else item.value)(doc.data, r, c) for c in range(item.cols)] for r in range(item.rows)]
            comparing = self.compare_active and self.owner.compare is not None
            reference = [[item.value(self.owner.compare, r, c) for c in range(item.cols)] for r in range(item.rows)] if self.owner.compare is not None and not self.raw_view else None
            values = [[comparison_value(working[r][c], reference[r][c], self.compare_mode) for c in range(item.cols)] for r in range(item.rows)] if comparing else working
            if comparing:
                self.map_details.setText(f"COMPARE - {self.compare_mode} - {self.owner.compare_name} - Read only - " + ("working − reference" if self.compare_mode == "Difference" else "(working − reference) / reference × 100; — means reference is zero" if self.compare_mode == "Percentage" else "reference binary values"))
            self.map_details.setToolTip(self.map_details.text())
            self.map_details.setVisible(comparing)
            self.table.setRowCount(item.rows)
            self.table.setColumnCount(item.cols)
            self.table.setHorizontalHeaderLabels(self.owner.definition.axis_labels(item, "x", doc.data))
            self.table.setVerticalHeaderLabels(self.owner.definition.axis_labels(item, "y", doc.data))
            flat = [v for row in values for v in row if v is not None]
            low, high = (min(flat), max(flat)) if flat else (0, 0)
            for r in range(item.rows):
                for c in range(item.cols):
                    value = values[r][c]
                    text = "—" if value is None else f"{value:.{item.decimals}f}"
                    if self.raw_view:
                        text = f"{value:0{item.bits // 4}X}"
                    elif value is not None and not comparing:
                        text = format_number(value, item.output_type, item.decimals)
                    cell = W.QTableWidgetItem(text)
                    cell.setTextAlignment(C.Qt.AlignCenter)
                    color = heatmap_color(value, low, high, comparing, self.compare_mode, self.owner.active_palette)
                    cell.setBackground(color)
                    cell.setForeground(contrast_text(color))
                    offset, size = item.offset(r, c), item.bits // 8
                    tip = f"Address: 0x{offset:X}\nRaw: {item.raw(doc.data, r, c)}\nWorking: {working[r][c]:g}"
                    tip += f"\nEquation: {item.equation_for(r, c).source}"
                    if reference is not None:
                        tip += f"\nReference: {reference[r][c]:g}\nDifference: {working[r][c] - reference[r][c]:+g}"
                    cell.setToolTip(tip)
                    if doc.data[offset:offset + size] != doc.original[offset:offset + size]:
                        font = cell.font()
                        font.setBold(True)
                        cell.setFont(font)
                    editable = not comparing
                    if not self.raw_view:
                        try:
                            item.equation_for(r, c).affine()
                        except ValueError:
                            editable = False
                    if not editable:
                        cell.setFlags(cell.flags() & ~C.Qt.ItemIsEditable)
                    self.table.setItem(r, c, cell)
            self.table.resizeColumnsToContents()
            factor = getattr(self.owner, "appearance_scale", 1.)
            row_height = G.QFontMetrics(self.table.font()).height() + round(7 * factor)
            self.table.verticalHeader().setMinimumSectionSize(row_height)
            self.table.verticalHeader().setDefaultSectionSize(row_height)
            # Gaps caused by zero reference values have no defined percentage.
            self.surface.values = values
        except Exception as exc:
            self.map_details.setText(f"Cannot display this map: {exc}")
        finally:
            if 0 <= current[0] < self.table.rowCount() and 0 <= current[1] < self.table.columnCount():
                self.table.setCurrentCell(*current)
            self.table.clearSelection()
            for r, c in selection:
                if r < self.table.rowCount() and c < self.table.columnCount():
                    self.table.item(r, c).setSelected(True)
            self.table.verticalScrollBar().setValue(scroll[0])
            self.table.horizontalScrollBar().setValue(scroll[1])
            self.plot.update()
            self.surface.update()
            self.loading = False
            self.sync_graph_selection()
            if self.graph_window is not None:
                self.graph_window.sync()
