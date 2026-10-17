from __future__ import annotations

import csv
import codecs
import json
import hashlib
import copy
import xml.etree.ElementTree as ET
import sys
from pathlib import Path

from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W

from . import __version__
from .core import ADXDefinition, BinaryDocument, Definition
from .integrations import DEFAULT_FLASHER, DEFAULT_LOGGER, flasher_command, load_can_backend
from .kline import KLineSession, Profile
from .process import ConsoleProcess
from .editor import TableEditor
from .properties import ItemProperties
from .appearance import stylesheet, read_palettes, palette_for
from .icons import item_icon, item_type, tool_icon
from .navigation import NavigationDrawer
from .workspace import ItemWorkspace, ItemWindow
from .item_tree import ItemTree
from .file_commands import FileCommands
from .session import WorkspaceSession
from .xdf_clipboard import XdfClipboard
from .logger_dashboard import LoggerDashboard
from .runtime import frozen, data_root, backend_setting


STYLE = stylesheet()


def label(text, name=None, wrap=False):
    widget = W.QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def button(text, callback, primary=False):
    widget = W.QPushButton(text)
    widget.clicked.connect(callback)
    if primary:
        widget.setObjectName("primary")
    return widget


def page_layout(title, subtitle):
    page = W.QWidget()
    layout = W.QVBoxLayout(page)
    layout.setContentsMargins(26, 22, 26, 18)
    layout.setSpacing(14)
    layout.addWidget(label(title, "title"))
    layout.addWidget(label(subtitle, "muted", True))
    return page, layout


class MainWindow(W.QMainWindow, FileCommands, WorkspaceSession, XdfClipboard):
    def __init__(self, settings=None):
        super().__init__()
        self.setWindowTitle("GK Tuner")
        self.logo_icon = G.QIcon(str(Path(__file__).parent / 'assets' / 'opengk.svg'))
        self.setWindowIcon(self.logo_icon)
        W.QApplication.instance().setWindowIcon(self.logo_icon)
        self.resize(1440, 900)
        self.setMinimumSize(1050, 680)
        self.settings = settings if settings is not None else C.QSettings("GK", "GK Tuner")
        self.palette_overrides = read_palettes(self.settings)
        self.active_palette = palette_for(self.settings.value('theme', 'Light'), self.palette_overrides.get(self.settings.value('theme', 'Light')))
        self.definition = self.document = self.current_map = self.compare = self.adx = None
        self.compare_name = "Reference binary"
        self.compare_slots = [None] * 6
        self.active_compare_slot = None
        self.open_editors = {}
        self.document_status = "No binary loaded"
        self.layout_side_by_side = False
        self.tile_timer = C.QTimer(self)
        self.tile_timer.setSingleShot(True)
        self.tile_timer.timeout.connect(lambda: self.tile_editors() if self.auto_tile.isChecked() else None)
        self.appearance_timer = C.QTimer(self)
        self.appearance_timer.setSingleShot(True)
        self.appearance_timer.timeout.connect(lambda: self.tile_editors() if self.auto_tile.isChecked() else None)
        self.backend = self.session = None
        self.kline_profile = None
        self.session_kind = 0
        self.log_rows = []
        self.log_next = 0
        self.flashing = False
        self.prompt_buffer = ""
        self.output_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.loading = False
        self.process = ConsoleProcess(self)
        self.process.readyReadStandardOutput.connect(self.process_output)
        self.process.finished.connect(self.process_finished)
        self.process.errorOccurred.connect(lambda _: self.error(self.process.errorString()))
        self.build_ui()
        self.build_menu()
        self.apply_appearance(persist=False)
        self.timer = C.QTimer(self)
        self.timer.timeout.connect(self.poll_logger)
        self.timer.start(150)
        self.statusBar().showMessage("Offline - No adapter connected")

    def build_ui(self):
        central = W.QWidget()
        root = W.QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = W.QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(190)
        nav = W.QVBoxLayout(sidebar)
        nav.setContentsMargins(18, 25, 18, 18)
        nav.setSpacing(13)
        brand = W.QHBoxLayout()
        self.brand_logo = W.QLabel()
        self.brand_logo.setPixmap(self.logo_icon.pixmap(40, 40))
        brand.addWidget(self.brand_logo)
        brand.addWidget(label("GK Tuner", "brand"), 1)
        nav.addLayout(brand)
        nav.addSpacing(25)
        self.stack = W.QStackedWidget()
        self.nav_group = W.QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for index, text in enumerate(("Map Editor", "Logging", "Flashing", "Live tuning", "Settings")):
            btn = button(text, lambda checked=False, i=index: self.select_navigation(i))
            btn.setCheckable(True)
            self.nav_group.addButton(btn, index)
            nav.addWidget(btn)
            if index == 0:
                btn.setChecked(True)
        nav.addStretch()
        nav.addWidget(label(f"v{__version__} - Preview", "muted"))
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.drawer = NavigationDrawer(central, sidebar)
        self.build_calibration()
        self.build_logging()
        self.build_flashing()
        page, layout = page_layout("Live tuning", "Planned for a future release")
        layout.addStretch()
        self.stack.addWidget(page)
        self.build_settings()
        self.stack.currentChanged.connect(lambda i: self.nav_group.button(i).setChecked(True))

    def select_navigation(self, index):
        self.stack.setCurrentIndex(index)
        self.drawer.set_open(False)

    def build_menu(self):
        menu = self.menuBar().addMenu("File")
        menu.addAction("Open demonstration", self.open_demo)
        self.load_bin_action = menu.addAction(tool_icon("load_bin"), "Load BIN…", self.open_binary)
        self.load_bin_action.setShortcut("Ctrl+O")
        self.recent_bin_menu = menu.addMenu("Recent BINs")
        self.save_bin_action = menu.addAction(tool_icon("save_bin"), "Save BIN as…", self.save_binary)
        self.save_bin_action.setShortcut("Ctrl+Shift+S")
        self.checksum_action = menu.addAction(tool_icon('checksum'), 'Correct BIN checksum…', self.correct_map_checksum)
        self.checksum_action.setEnabled(self.document is not None)
        xdf_menu = self.menuBar().addMenu("XDF")
        self.load_xdf_action = xdf_menu.addAction(tool_icon("load_xdf"), "Load XDF…", self.open_xdf)
        self.load_xdf_action.setShortcut("Ctrl+Shift+O")
        self.recent_xdf_menu = xdf_menu.addMenu("Recent XDFs")
        self.save_xdf_action = xdf_menu.addAction(tool_icon("save_xdf"), "Save XDF as…", self.save_xdf)
        self.save_xdf_current_action = xdf_menu.addAction(tool_icon("save_xdf"), "Save XDF", self.save_xdf_current)
        xdf_menu.insertAction(self.save_xdf_action, self.save_xdf_current_action)
        xdf_menu.addAction("Edit XDF header…", self.edit_header)
        xdf_menu.addAction("Add new item…", self.add_xdf_item)
        xdf_menu.addAction("Remove selected item…", self.remove_xdf_item)
        xdf_menu.addSeparator()
        self.refresh_recent_menus()
        self.build_compare_menu()
        edit = self.menuBar().addMenu("Edit")
        self.undo_action = edit.addAction(tool_icon("undo"), "Undo", self.undo)
        self.undo_action.setShortcut("Ctrl+Z")
        self.redo_action = edit.addAction(tool_icon("redo"), "Redo", self.redo)
        self.redo_action.setShortcut("Ctrl+Y")
        edit.addAction("Copy cells", self.copy_cells).setShortcut("Ctrl+C")
        edit.addAction("Paste cells", self.paste_cells).setShortcut("Ctrl+V")
        edit.addAction("Copy XDF items", self.copy_xdf_items).setShortcut("Ctrl+Shift+C")
        edit.addAction("Paste XDF items", self.paste_xdf_items).setShortcut("Ctrl+Shift+V")
        edit.addAction("Item properties…", lambda: self.open_properties())
        self.menuBar().addMenu("Acquisition").addAction("Import ADX…", self.open_adx)
        self.menuBar().addMenu("Help").addAction("Compatibility and roadmap", self.show_compatibility)
        self.menuBar().addMenu("Program").addAction("Program properties…", lambda: self.stack.setCurrentIndex(4))
        bar = self.addToolBar("Workspace")
        bar.setMovable(False)
        bar.setToolButtonStyle(C.Qt.ToolButtonIconOnly)
        self.command_bar = bar
        def command(text, icon, callback):
            action = bar.addAction(icon, text)
            action.triggered.connect(callback)
            return action
        command("GK Tuner navigation", tool_icon("menu"), lambda: self.drawer.set_open(not self.drawer.opened))
        for load, save in ((self.load_bin_action, self.save_bin_action), (self.load_xdf_action, self.save_xdf_current_action)):
            bar.addAction(load)
            bar.addAction(save)
            bar.addSeparator()
        bar.addAction(self.undo_action)
        bar.addAction(self.redo_action)
        bar.addAction(self.checksum_action)
        compare_button = W.QToolButton()
        self.compare_button = compare_button
        compare_button.setIcon(tool_icon("compare"))
        compare_button.setToolTip("Global comparison BIN selection (six slots)")
        compare_button.setMenu(self.compare_menu)
        compare_button.setPopupMode(W.QToolButton.InstantPopup)
        bar.addWidget(compare_button)
        bar.addSeparator()
        command("Tile windows to content", tool_icon("tile"), lambda: self.tile_editors(False))
        command("Side by side", tool_icon("side"), lambda: self.tile_editors(True))
        command("Cascade", tool_icon("cascade"), self.cascade_editors)
        command("Fit windows to data", tool_icon("fit"), lambda: [self.fit_editor(e) for e in self.open_editors.values()])
        bar.addAction(self.auto_tile)
        self.statusBar().addPermanentWidget(self.file_info, 1)

    def build_calibration(self):
        page = W.QWidget()
        layout = W.QVBoxLayout(page)
        layout.setContentsMargins(8, 3, 3, 3)
        self.file_info = label("No binary loaded   /   No definition imported", "accent", True)
        self.file_info.setWordWrap(False)
        self.file_info.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Preferred)
        self.auto_tile = W.QAction(tool_icon("tile"), "Auto arrange windows", self)
        self.auto_tile.setCheckable(True)
        self.auto_tile.setChecked(True)
        self.auto_tile.toggled.connect(lambda enabled: self.tile_editors() if enabled else None)
        split = W.QSplitter()
        self.map_splitter = split
        browser = W.QWidget()
        self.item_browser = browser
        left = W.QVBoxLayout(browser)
        left.setContentsMargins(0, 0, 8, 0)
        self.search = W.QLineEdit()
        self.search.setPlaceholderText("Search items, categories, addresses…")
        self.search.textChanged.connect(self.filter_maps)
        left.addWidget(self.search)
        self.tree = ItemTree()
        self.tree.setSelectionMode(W.QAbstractItemView.ExtendedSelection)
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self.select_map)
        self.tree.orderChanged.connect(self.remember_tree_order)
        self.tree.setContextMenuPolicy(C.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.tree_menu)
        left.addWidget(self.tree)
        self.map_count = label("Import an XDF to browse maps", "muted", True)
        left.addWidget(self.map_count)
        legend = W.QGridLayout()
        for index, kind in enumerate(("XDFCONSTANT", "XDFTABLE", "XDFFUNCTION", "XDFPATCH", "XDFFLAG")):
            row, col = divmod(index, 2)
            cell = W.QHBoxLayout()
            icon = W.QLabel()
            icon.setProperty("itemKind", kind)
            icon.setPixmap(item_icon(kind).pixmap(18, 18))
            cell.addWidget(icon)
            cell.addWidget(label(item_type(kind), "muted"))
            cell.addStretch()
            legend.addLayout(cell, row, col)
        left.addLayout(legend)
        split.addWidget(browser)
        self.editor_stack = W.QStackedWidget()
        self.empty_editor = TableEditor(self, None)
        self.empty_editor.setParent(self.editor_stack)
        self.empty_editor.hide()
        self.mdi = ItemWorkspace()
        self.mdi.subWindowActivated.connect(self.activate_editor)
        self.mdi.resized.connect(self.schedule_tile)
        self.editor_stack.addWidget(self.mdi)
        self.editor_stack.setCurrentWidget(self.mdi)
        self.bind_editor(self.empty_editor)
        self.empty_editor.refresh()
        split.addWidget(self.editor_stack)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([250, 1190])
        layout.addWidget(split, 1)
        self.stack.addWidget(page)

    def bind_editor(self, editor):
        self.active_editor = editor
        self.current_map = editor.item
        for name in ("table", "views", "plot", "surface", "inspect", "map_title", "map_details", "change_info", "op", "amount"):
            setattr(self, name, getattr(editor, name, None))
        if hasattr(self, "tree"):
            self.highlight_active_item()

    def highlight_active_item(self):
        uid = getattr(self.current_map, "parent_uid", None) or getattr(self.current_map, "uid", None)
        if uid is None:
            return
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            for j in range(group.childCount()):
                child = group.child(j)
                if child.data(0, C.Qt.UserRole).uid.lower() == uid.lower():
                    self.tree.setCurrentItem(child)
                    group.setExpanded(True)
                    return

    def activate_editor(self, subwindow):
        self.bind_editor(subwindow.editor if subwindow is not None else self.empty_editor)

    def open_map(self, item):
        self.editor_stack.setCurrentWidget(self.mdi)
        key = item.uid.lower()
        editor = self.open_editors.get(key)
        created = editor is None
        if editor is None:
            from .item_editors import make_editor
            editor = make_editor(self, item)
            if isinstance(editor, TableEditor):
                editor.map_title.hide()
                editor.change_info.hide()
                editor.map_details.setWordWrap(False)
                editor.map_details.setSizePolicy(W.QSizePolicy.Ignored, W.QSizePolicy.Preferred)
            self.open_editors[key] = editor
            subwindow = ItemWindow(self, editor)
            editor.subwindow = subwindow
            subwindow.setWindowTitle(item.title)
            subwindow.setWindowIcon(item_icon(item.kind))
            self.mdi.addSubWindow(subwindow)
            subwindow.show()
        self.editor_stack.setCurrentWidget(self.mdi)
        editor.subwindow.show()
        self.mdi.setActiveSubWindow(editor.subwindow)
        self.bind_editor(editor)
        self.refresh_map()
        if created:
            self.fit_editor(editor)
        if self.auto_tile.isChecked():
            self.tile_editors()
        return editor

    def close_editor(self, editor):
        if editor is not None and editor.item is not None:
            editor.subwindow.close()

    def remove_item_window(self, subwindow):
        editor = subwindow.editor
        if hasattr(editor, "close_graph"):
            editor.close_graph()
        self.open_editors.pop(editor.item.uid.lower(), None)
        self.mdi.removeSubWindow(subwindow)
        remaining = self.mdi.subWindowList()
        if not remaining:
            self.bind_editor(self.empty_editor)
            self.empty_editor.refresh()
        else:
            self.mdi.setActiveSubWindow(remaining[-1])
            self.bind_editor(remaining[-1].editor)
            if self.auto_tile.isChecked():
                self.tile_editors()

    def clear_editors(self):
        for editor in list(self.open_editors.values()):
            if not editor.subwindow.close():
                return False
        self.bind_editor(self.empty_editor)
        return True

    def tile_editors(self, side_by_side=None):
        if side_by_side is not None:
            self.layout_side_by_side = bool(side_by_side)
        windows = self.mdi.subWindowList()
        if not windows:
            return
        area = self.mdi.viewport().rect()
        x, y, line_height = 0, 0, 0
        for window in windows:
            window.showNormal()
            self.fit_editor(window.editor)
            if not self.layout_side_by_side and x and x + window.width() > area.width():
                x, y, line_height = 0, y + line_height + 6, 0
            window.move(x, y)
            x += window.width() + 6
            line_height = max(line_height, window.height())

    def fit_editor(self, editor):
        if not hasattr(editor, "subwindow"):
            return
        editor.layout().activate()
        size = editor.preferred_size()
        frame = round(6 * getattr(self, "appearance_scale", 1))
        title = editor.subwindow.style().pixelMetric(W.QStyle.PM_TitleBarHeight)
        available = self.mdi.viewport().size()
        editor.subwindow.resize(min(max(260, size.width() + 2 * frame), max(260, available.width())),
                                min(max(120, size.height() + 2 * frame + title), max(120, available.height())))

    def schedule_tile(self):
        if self.auto_tile.isChecked():
            self.tile_timer.start(0)

    def cascade_editors(self):
        self.auto_tile.setChecked(False)
        self.mdi.cascadeSubWindows()

    def tree_menu(self, position):
        selected = self.tree.itemAt(position)
        item = selected.data(0, C.Qt.UserRole) if selected else None
        menu = W.QMenu(self)
        menu.addAction("Add new item…", self.add_xdf_item)
        menu.addAction("Copy XDF items", self.copy_xdf_items)
        menu.addAction("Paste XDF items", self.paste_xdf_items)
        if item is not None:
            menu.addAction("Properties…", lambda: self.open_properties(item))
            menu.addAction("Remove item…", lambda: self.remove_xdf_item(item))
        menu.exec_(self.tree.viewport().mapToGlobal(position))

    def open_properties(self, item=None, initial_tab=0):
        item = item or self.current_map
        if item is None or not self.definition:
            return
        editor = self.open_editors.get(item.uid.lower())
        if editor is not None and hasattr(editor, "can_close") and not editor.can_close():
            return
        if hasattr(item, "parent_uid"):
            initial_tab = 2 if item.axis_which == "x" else 1
            item = self.definition.by_id[item.parent_uid]
        if item.kind == "XDFPATCH":
            from .patch_editor import PatchDefinitionDialog
            PatchDefinitionDialog(self, item).exec_()
            return
        dialog = ItemProperties(self, item, initial_tab)
        dialog.exec_()

    def edit_axis(self, editor, which):
        item = editor.item
        if item is None or not self.definition:
            return
        try:
            axis = item.node.find(f"XDFAXIS[@id='{which}']")
            link = axis.find("embedinfo") if axis is not None else None
            if link is not None and link.get("type") == "3":
                target = self.definition.by_id.get(link.get("linkobjid", "").lower())
                count = item.cols if which == "x" else item.rows
                if target is None or target.reason or target.rows * target.cols != count:
                    raise ValueError("The linked axis is missing, unsupported, or has a different size. Correct its link in Properties.")
                self.open_map(target)
                return
            target = self.definition.internal_axis(item, which)
            if target is not None:
                self.open_map(target)
            else:
                self.open_properties(item, 2 if which == "x" else 1)
        except Exception as exc:
            self.error(exc)

    def edit_axis_value(self, editor, which, index):
        if not self.document or not self.definition or editor.compare_active:
            return
        try:
            item = editor.item
            axis = item.node.find(f"XDFAXIS[@id='{which}']")
            link = axis.find("embedinfo") if axis is not None else None
            count = item.cols if which == "x" else item.rows
            target = self.definition.by_id.get(link.get("linkobjid", "").lower()) if link is not None and link.get("type") == "3" else self.definition.internal_axis(item, which)
            if target is None:
                raise ValueError("This axis uses labels stored in the XDF, with no binary address. Edit its labels in Properties.")
            if target.reason or target.rows * target.cols != count or not 0 <= index < count:
                raise ValueError("The axis definition is unsupported or has a different size.")
            row, col = divmod(index, target.cols)
            value, accepted = W.QInputDialog.getText(self, f"Edit {which.upper()} axis value", f"{target.title} - value {index + 1}", text=str(target.value(editor.buffer.data, row, col)))
            if accepted:
                editor.buffer.edit(target, [(row, col, float(value))])
                self.refresh_map()
        except Exception as exc:
            self.error(exc)

    def apply_definition(self, definition):
        self.definition = definition
        reopen = []
        for editor in list(self.open_editors.values()):
            item = editor.item
            if hasattr(item, "parent_uid"):
                parent = definition.by_id.get(item.parent_uid)
                try:
                    updated = definition.internal_axis(parent, item.axis_which) if parent else None
                except ValueError:
                    updated = None
                if updated is None:
                    self.close_editor(editor)
                    continue
            else:
                updated = definition.by_id.get(item.uid.lower())
                if updated is None:
                    self.close_editor(editor)
                    continue
            if bool(getattr(editor, "is_text_editor", False)) != bool(updated.output_type == 4 and not updated.reason):
                self.close_editor(editor)
                reopen.append(updated)
            else:
                editor.item = updated
        self.populate_tree()
        for item in reopen:
            self.open_map(item)
        self.bind_editor(self.mdi.activeSubWindow().editor if self.mdi.activeSubWindow() else self.empty_editor)
        self.refresh_map()

    def save_xdf_current(self):
        if self.definition is None:
            return False
        try:
            self.definition.save()
            self.remember_file("xdf", self.definition.path)
            self.refresh_map()
            self.statusBar().showMessage("XDF saved")
            return True
        except Exception as exc:
            self.error(exc)
            return False

    def edit_header(self):
        if self.definition is None:
            return self.error("Load an XDF first.")
        for editor in self.open_editors.values():
            if hasattr(editor, "can_close") and not editor.can_close():
                return
        from .definition_tools import HeaderEditor
        HeaderEditor(self).exec_()

    def add_xdf_item(self):
        if self.definition is None:
            return self.error("Load an XDF first.")
        from .definition_tools import NewItemDialog
        dialog = NewItemDialog(self)
        if dialog.exec_() == W.QDialog.Accepted:
            self.configure_new_item(dialog.kind.currentData())

    def configure_new_item(self, kind):
        from .definition_tools import new_item_candidate
        definition, item = new_item_candidate(self, kind)
        if kind == "XDFPATCH":
            from .patch_editor import PatchDefinitionDialog
            dialog = PatchDefinitionDialog(self, item, definition=definition)
        else:
            dialog = ItemProperties(self, item, definition=definition)
        dialog.exec_()
        saved = self.definition.by_id.get(item.uid.lower())
        if saved is not None:
            self.open_map(saved)

    def remove_xdf_item(self, item=None):
        if self.definition is None:
            return
        selected = self.tree.currentItem()
        item = item if item is not None and not isinstance(item, bool) else selected.data(0, C.Qt.UserRole) if selected else None
        if item is None:
            return
        for node in self.definition.root.iter("embedinfo"):
            if node.get("linkobjid", "").lower() == item.uid.lower():
                return self.error("This item is linked by an axis. Reassign the axis link before removing it.")
        if W.QMessageBox.question(self, "Remove XDF item", f"Remove '{item.title}' from the XDF? BIN bytes are unchanged.", W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.No) != W.QMessageBox.Yes:
            return
        editor = self.open_editors.get(item.uid.lower())
        if editor and not editor.subwindow.close():
            return
        from .definition_tools import candidate_definition
        root = copy.deepcopy(self.definition.root)
        for node in list(root):
            if node.get("uniqueid", "").lower() == item.uid.lower():
                root.remove(node)
                break
        self.apply_definition(candidate_definition(self.definition, root))

    def save_xdf(self):
        if not self.definition:
            return False
        path = W.QFileDialog.getSaveFileName(self, "Save XDF properties", str(self.definition.path.with_stem(self.definition.path.stem + "_gktuner")), "TunerPro definition (*.xdf)")[0]
        if not path:
            return False
        try:
            self.definition.save_as(path)
            self.remember_file("xdf", path)
            self.refresh_map()
            self.statusBar().showMessage(f"Saved definition {path}")
            return True
        except Exception as exc:
            self.error(exc)
            return False

    def guard_definition(self):
        if self.definition and self.definition.dirty:
            answer = W.QMessageBox.question(self, "Unsaved XDF properties", "Save your definition properties before continuing?", W.QMessageBox.Save | W.QMessageBox.Discard | W.QMessageBox.Cancel, W.QMessageBox.Save)
            if answer == W.QMessageBox.Cancel:
                return False
            if answer == W.QMessageBox.Save:
                return self.save_xdf()
        return True

    def choose_file(self, title, pattern):
        return W.QFileDialog.getOpenFileName(self, title, self.settings.value("last_folder", str(Path.cwd())), pattern)[0]

    def error(self, message):
        W.QMessageBox.warning(self, "GK Tuner", str(message))

    def guard_unsaved(self, include_definition=True):
        for editor in self.open_editors.values():
            if hasattr(editor, "can_close") and not editor.can_close():
                return False
        if self.document and self.document.dirty:
            answer = W.QMessageBox.question(self, "Unsaved calibration", "Save your edited binary before continuing?", W.QMessageBox.Save | W.QMessageBox.Discard | W.QMessageBox.Cancel, W.QMessageBox.Save)
            if answer == W.QMessageBox.Cancel:
                return False
            if answer == W.QMessageBox.Save:
                if not self.save_binary():
                    return False
        return self.guard_definition() if include_definition else True

    def open_binary(self):
        path = self.choose_file("Open binary", "ECU binary (*.bin *.rom);;All files (*)")
        if path:
            self.load_binary_path(path)

    def load_binary_path(self, path):
        if not self.guard_unsaved(include_definition=False):
            return False
        try:
            document = BinaryDocument(path)
            self.document = document
            self.session_bin_path = str(Path(path).resolve())
            self.clear_comparisons()
            self.remember_file("bin", path)
            self.refresh_map()
            return True
        except Exception as exc:
            self.error(exc)
            return False

    def open_demo(self):
        if not self.guard_unsaved():
            return
        try:
            from .demo import create_demo
            binary, xdf = create_demo(data_root() / 'Demo' if frozen() else Path(__file__).resolve().parents[1] / "examples")
            if not self.clear_editors():
                return
            self.document = BinaryDocument(binary)
            self.session_bin_path = str(binary)
            self.definition = Definition(xdf)
            self.clear_comparisons()
            self.current_map = None
            self.populate_tree()
            for i in range(self.tree.topLevelItemCount()):
                group = self.tree.topLevelItem(i)
                if group.text(0) == "Ignition":
                    self.open_map(group.child(0).data(0, C.Qt.UserRole))
                    break
            self.tree.collapseAll()
            self.stack.setCurrentIndex(0)
            self.statusBar().showMessage("DEMONSTRATION - Synthetic data, not for use in an ECU")
        except Exception as exc:
            self.error(exc)

    def open_xdf(self):
        path = self.choose_file("Import XDF", "TunerPro definition (*.xdf);;All files (*)")
        if path:
            self.load_xdf_path(path)

    def load_xdf_path(self, path):
        if not self.guard_definition():
            return False
        try:
            definition = Definition(path)
            if not self.clear_editors():
                return False
            self.definition = definition
            self.current_map = None
            self.populate_tree()
            self.remember_file("xdf", path)
            self.refresh_map()
            return True
        except Exception as exc:
            self.error(exc)
            return False

    def populate_tree(self):
        self.tree.clear()
        groups = {}
        used_categories = {item.category for item in self.definition.maps}
        categories = list(dict.fromkeys(list(self.definition.categories.values()) + [m.category for m in self.definition.maps]))
        for category in categories:
            if category not in used_categories:
                continue
            groups[category] = W.QTreeWidgetItem(self.tree, [category])
            icon = G.QIcon(self.style().standardIcon(W.QStyle.SP_DirClosedIcon))
            icon.addPixmap(self.style().standardIcon(W.QStyle.SP_DirOpenIcon).pixmap(16, 16), G.QIcon.Normal, G.QIcon.On)
            groups[category].setIcon(0, icon)
        for item in self.definition.maps:
            child = W.QTreeWidgetItem(groups[item.category], [("○ " if item.reason and item.kind != "XDFPATCH" else "") + item.title])
            child.setData(0, C.Qt.UserRole, item)
            child.setFlags(child.flags() & ~C.Qt.ItemIsDropEnabled)
            child.setIcon(0, item_icon(item.kind))
            child.setToolTip(0, "Editable overwrite patch; expected-byte checks before applying" if item.kind == "XDFPATCH" else item_type(item.kind) + " - " + (item.reason or f"0x{item.address:X} - {item.rows} × {item.cols} - {item.units}"))
            if item.reason:
                child.setForeground(0, G.QColor("#8996a8"))
        self.apply_tree_order()
        supported = sum(not m.reason for m in self.definition.maps)
        patches = sum(item.kind == "XDFPATCH" for item in self.definition.maps)
        self.map_count.setText(f"{len(self.definition.maps)} items - {supported} numeric definitions - {patches} patches\n○ Inspection only")
        self.tree.collapseAll()
        self.filter_maps(self.search.text())

    def filter_maps(self, text):
        query = text.casefold()
        self.tree.is_searching = bool(query)
        if not query:
            self.tree.collapseAll()
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            visible = False
            for j in range(parent.childCount()):
                child = parent.child(j)
                item = child.data(0, C.Qt.UserRole)
                match = query in f"{item.title} {item.category} {item.address:x}".casefold()
                child.setHidden(not match)
                visible |= match
            parent.setHidden(not visible)
            if query:
                parent.setExpanded(True)

    def tree_order_key(self):
        source = str(self.definition.source_path).casefold()
        return "item_order/" + hashlib.sha256(source.encode("utf-8")).hexdigest()

    def remember_tree_order(self):
        if self.definition is None:
            return
        order = []
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            order.append([group.text(0), [group.child(j).data(0, C.Qt.UserRole).uid for j in range(group.childCount())]])
        self.settings.setValue(self.tree_order_key(), json.dumps(order))
        self.settings.sync()

    def apply_tree_order(self):
        try:
            order = json.loads(self.settings.value(self.tree_order_key(), "[]"))
            groups = {self.tree.topLevelItem(i).text(0): self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())}
            for index, (name, uids) in enumerate(order):
                group = groups.get(name)
                if group is None:
                    continue
                self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(group))
                self.tree.insertTopLevelItem(min(index, self.tree.topLevelItemCount()), group)
                children = {group.child(j).data(0, C.Qt.UserRole).uid: group.child(j) for j in range(group.childCount())}
                for position, uid in enumerate(uids):
                    child = children.get(uid)
                    if child is not None:
                        group.takeChild(group.indexOfChild(child))
                        group.insertChild(min(position, group.childCount()), child)
        except (ValueError, TypeError):
            pass

    def select_map(self, selected, previous=None):
        item = selected.data(0, C.Qt.UserRole) if selected else None
        if item is not None:
            self.open_map(item)

    def refresh_map(self):
        doc = self.document
        self.checksum_action.setEnabled(doc is not None)
        changed = sum(a != b for a, b in zip(doc.original, doc.data)) if doc else 0
        self.document_status = f"{'Unsaved binary changes' if doc and doc.dirty else 'Binary saved / unchanged'} - {changed} bytes changed from source"
        definition_name = self.definition.path.name + (' *' if self.definition.dirty else '') if self.definition else 'No XDF'
        self.file_info.setText(f"{doc.path.name if doc else 'No binary'}   /   {definition_name}")
        self.setWindowTitle(f"GK Tuner{' - ' + doc.path.name if doc else ''}{' *' if (doc and doc.dirty) or (self.definition and self.definition.dirty) else ''}")
        for editor in self.open_editors.values():
            editor.subwindow.setWindowIcon(item_icon(editor.item.kind))
            editor.refresh()
        self.empty_editor.refresh()
        self.update_item_colors()

    def update_item_colors(self):
        if self.definition is None or self.document is None:
            return
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            for j in range(group.childCount()):
                child = group.child(j)
                item = child.data(0, C.Qt.UserRole)
                changed = False
                try:
                    if not item.reason:
                        targets = [item]
                        for which in ("x", "y"):
                            axis = item.node.find(f"XDFAXIS[@id='{which}']")
                            link = axis.find("embedinfo") if axis is not None else None
                            target = self.definition.by_id.get(link.get("linkobjid", "").lower()) if link is not None and link.get("type") == "3" else self.definition.internal_axis(item, which)
                            if target is not None and not target.reason:
                                targets.append(target)
                        changed = any(self.document.data[target.offset(r, c):target.offset(r, c) + target.bits // 8] != self.document.original[target.offset(r, c):target.offset(r, c) + target.bits // 8] for target in targets for r in range(target.rows) for c in range(target.cols))
                    elif item.kind == "XDFPATCH":
                        from .patches import PatchPlan
                        plan = PatchPlan(item.node, self.definition.base)
                        changed = any(self.document.data[e.address:e.address + len(e.data)] != self.document.original[e.address:e.address + len(e.data)] for e in plan.entries)
                except ValueError:
                    pass
                child.setForeground(0, G.QColor(self.active_palette['changed'] if changed else self.active_palette['muted'] if item.reason and item.kind != "XDFPATCH" else self.active_palette['text']))

    def editor_cell_changed(self, editor, cell):
        if editor.loading or not self.document or editor.item is None:
            return
        if editor.compare_active:
            return
        targets = editor.selected_cells()
        if (cell.row(), cell.column()) not in targets:
            targets = [(cell.row(), cell.column())]
        self.apply_table_value(editor, targets, cell.text())

    def apply_table_value(self, editor, targets, text):
        if editor.loading or not self.document or editor.item is None or editor.compare_active:
            return
        try:
            if editor.raw_view:
                value = int(text.strip(), 16)
                editor.buffer.edit_raw(editor.item, [(row, col, value) for row, col in targets])
            else:
                value = float(int(text, 16)) if editor.item.output_type == 3 else float(text)
                editor.buffer.edit(editor.item, [(row, col, value) for row, col in targets])
        except Exception as exc:
            self.error(exc)
        self.refresh_map()

    def cell_changed(self, cell):
        self.editor_cell_changed(self.active_editor, cell)

    def batch_edit(self):
        if not self.document or not self.current_map or self.table is None:
            return
        if self.active_editor.compare_active:
            return self.error("Turn off Compare before editing the working map.")
        cells = sorted({(i.row(), i.column()) for i in self.table.selectedIndexes()})
        if not cells:
            return self.error("Select cells in the table first.")
        try:
            item, doc = self.current_map, self.active_editor.buffer
            op, amount = self.op.currentIndex(), self.amount.value()
            edits = []
            if op in (4, 5):
                rows, cols = [r for r, c in cells], [c for r, c in cells]
                if len(cells) != (max(rows) - min(rows) + 1) * (max(cols) - min(cols) + 1):
                    raise ValueError("Interpolation needs one rectangular selection.")
                for r, c in cells:
                    start = (r, min(cols)) if op == 4 else (min(rows), c)
                    end = (r, max(cols)) if op == 4 else (max(rows), c)
                    f = (c - min(cols)) / (max(cols) - min(cols) or 1) if op == 4 else (r - min(rows)) / (max(rows) - min(rows) or 1)
                    a, b = item.value(doc.data, *start), item.value(doc.data, *end)
                    edits.append((r, c, a + (b - a) * f))
            else:
                for r, c in cells:
                    old = item.value(doc.data, r, c)
                    value = (amount, old + amount, old * amount, old * (1 + amount / 100))[op]
                    edits.append((r, c, value))
            doc.edit(item, edits)
        except Exception as exc:
            self.error(exc)
        self.refresh_map()

    def undo(self):
        if self.document:
            draft = getattr(self.active_editor, "buffer", None)
            (draft if draft is not None and draft.undo_stack else self.document).undo()
            self.refresh_map()

    def redo(self):
        if self.document:
            draft = getattr(self.active_editor, "buffer", None)
            (draft if draft is not None and draft.redo_stack else self.document).redo()
            self.refresh_map()

    def copy_cells(self):
        focus = W.QApplication.focusWidget()
        if self.tree.hasFocus() or focus is not None and self.tree.isAncestorOf(focus):
            return self.copy_xdf_items()
        if self.stack.currentIndex() != 0 or self.table is None or not self.table.selectedIndexes():
            return
        cells = self.table.selectedIndexes()
        rows, cols = [i.row() for i in cells], [i.column() for i in cells]
        selected = {(i.row(), i.column()) for i in cells}
        text = "\n".join("\t".join(self.table.item(r, c).text() if (r, c) in selected else "" for c in range(min(cols), max(cols) + 1)) for r in range(min(rows), max(rows) + 1))
        W.QApplication.clipboard().setText(text)

    def paste_cells(self):
        focus = W.QApplication.focusWidget()
        if self.tree.hasFocus() or focus is not None and self.tree.isAncestorOf(focus):
            return self.paste_xdf_items()
        if self.stack.currentIndex() != 0 or not self.document or not self.current_map or self.table is None or self.table.currentRow() < 0:
            return
        if self.active_editor.compare_active:
            return self.error("Turn off Compare before pasting into the working map.")
        try:
            start_r, start_c = self.table.currentRow(), self.table.currentColumn()
            raw = self.active_editor.raw_view
            edits = [(start_r + r, start_c + c, int(value, 16) if raw else float(int(value, 16)) if self.current_map.output_type == 3 else float(value)) for r, line in enumerate(W.QApplication.clipboard().text().strip().splitlines()) for c, value in enumerate(line.split("\t")) if value.strip()]
            (self.active_editor.buffer.edit_raw if raw else self.active_editor.buffer.edit)(self.current_map, edits)
        except Exception as exc:
            self.error(exc)
        self.refresh_map()

    def save_binary(self):
        if not self.document:
            return False
        path = W.QFileDialog.getSaveFileName(self, "Save edited binary", str(self.document.path.with_stem(self.document.path.stem + "_gktuned")), "Binary (*.bin)")[0]
        if not path:
            return False
        for editor in self.open_editors.values():
            if hasattr(editor, "can_close") and not editor.can_close():
                return False
        try:
            self.document.save_as(path)
            self.session_bin_path = str(Path(path).resolve())
            self.remember_file("bin", path)
            self.flash_binary.setText(path)
            self.refresh_map()
            self.statusBar().showMessage(f"Saved {path}")
            return True
        except Exception as exc:
            self.error(exc)
            return False

    def export_map(self):
        if not self.document or not self.current_map or self.current_map.reason:
            return
        path = W.QFileDialog.getSaveFileName(self, "Export map", "map.csv", "CSV (*.csv)")[0]
        if path:
            try:
                draft = getattr(self.active_editor, "buffer", None)
                item, data = self.current_map, draft.data if draft is not None else self.document.data
                with open(path, "w", newline="", encoding="utf-8-sig") as stream:
                    writer = csv.writer(stream)
                    writer.writerow([item.title + " / " + item.units] + self.definition.axis_labels(item, "x", data))
                    labels = self.definition.axis_labels(item, "y", data)
                    for r in range(item.rows):
                        writer.writerow([labels[r]] + [item.value(data, r, c) for c in range(item.cols)])
            except Exception as exc:
                self.error(exc)

    def build_logging(self):
        page = W.QWidget()
        root = W.QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        transport = W.QHBoxLayout()
        controls = W.QHBoxLayout()
        self.log_mode = W.QComboBox()
        self.log_mode.addItems(["CAN - CCP / CA663056", "K-line - ADX serial"])
        transport.addWidget(self.log_mode)
        transport.addStretch()
        root.addLayout(transport)
        self.logging_pages = W.QStackedWidget()
        self.ccp_dashboard = LoggerDashboard(self)
        self.logging_pages.addWidget(self.ccp_dashboard)
        serial_page = W.QWidget()
        layout = W.QVBoxLayout(serial_page)
        self.logging_pages.addWidget(serial_page)
        root.addWidget(self.logging_pages, 1)
        self.log_mode.currentIndexChanged.connect(self.logging_mode_changed)
        self.channel = W.QLineEdit("0")
        self.channel.setPlaceholderText("Adapter channel")
        controls.addWidget(self.channel)
        # Retained for the legacy capture entry point; the CCP dashboard owns
        # its visible DAQ-rate selector. Never let this become a top-level UI.
        self.rate = W.QComboBox(serial_page)
        for prescaler, hz in ((1, 100), (2, 50), (4, 25), (5, 20), (10, 10), (20, 5), (100, 1)):
            self.rate.addItem(f"{hz} Hz", prescaler)
        self.rate.hide()
        controls.addWidget(button("Import ADX", self.open_adx))
        layout.addLayout(controls)
        options = W.QHBoxLayout()
        self.verify_sum = W.QCheckBox("K-line: verify trailing additive checksum")
        self.verify_sum.setToolTip("Use only when the ADX body includes the final checksum byte and the frame uses an 8-bit additive checksum.")
        options.addWidget(self.verify_sum)
        self.verify_sum.setVisible(False)
        options.addStretch()
        self.review_adx_button = button("Review ADX transport", self.review_adx)
        self.review_adx_button.setVisible(False)
        options.addWidget(self.review_adx_button)
        layout.addLayout(options)
        self.log_notice = label("K-line serial support is experimental and has not been bench-tested.", "accent", True)
        layout.addWidget(self.log_notice)
        splitter = W.QSplitter()
        self.signals = W.QListWidget()
        splitter.addWidget(self.signals)
        self.log_table = W.QTableWidget()
        self.log_table.setColumnCount(2)
        self.log_table.setHorizontalHeaderLabels(["Channel", "Latest value"])
        self.log_table.horizontalHeader().setStretchLastSection(True)
        self.log_table.setEditTriggers(W.QAbstractItemView.NoEditTriggers)
        splitter.addWidget(self.log_table)
        splitter.setSizes([340, 600])
        layout.addWidget(splitter, 1)
        bar = W.QHBoxLayout()
        self.record_button = button("Start recording", self.start_logging, True)
        bar.addWidget(self.record_button)
        bar.addWidget(button("Stop recording", self.stop_logging))
        bar.addWidget(button("Open CSV log", self.open_log_csv))
        bar.addWidget(button("Export visible log", self.export_log))
        bar.addStretch()
        layout.addLayout(bar)
        self.stack.addWidget(page)

    def logging_mode_changed(self, index):
        if self.session and self.session.snapshot()["state"] in ("connecting", "recording", "stopping"):
            self.log_mode.blockSignals(True)
            self.log_mode.setCurrentIndex(self.session_kind)
            self.log_mode.blockSignals(False)
            return self.error("Stop the current capture before changing transport.")
        self.logging_pages.setCurrentIndex(index)
        self.signals.clear()
        if index:
            self.channel.setPlaceholderText("Serial port, e.g. COM3")
            if self.channel.text() == "0":
                self.channel.setText("COM3")
            self.log_notice.setText("Import an ADX, select supported channels, and review its transport commands. K-line serial support is experimental and has not been bench-tested.")
            if self.kline_profile:
                for channel in self.kline_profile.channels:
                    item = W.QListWidgetItem(f"{'○ ' if channel.reason else ''}{channel.title}   {channel.unit}")
                    item.setData(C.Qt.UserRole, channel.id)
                    item.setToolTip(channel.reason or f"Offset {channel.offset} - {channel.bits} bits - {channel.equation.source}")
                    if not channel.reason:
                        item.setFlags(item.flags() | C.Qt.ItemIsUserCheckable)
                        item.setCheckState(C.Qt.Unchecked)
                    else:
                        item.setForeground(G.QColor("#8996a8"))
                    self.signals.addItem(item)
        else:
            self.channel.setPlaceholderText("CAN adapter channel")
            if self.channel.text().upper().startswith("COM"):
                self.channel.setText("0")
            self.log_notice.setText("CAN - CCP / CA663056 - Load channels to connect your existing backend.")
            if self.backend:
                self.populate_can_channels()
        self.verify_sum.setEnabled(index == 1)
        self.verify_sum.setVisible(index == 1)
        self.review_adx_button.setVisible(index == 1)

    def populate_can_channels(self):
        self.signals.clear()
        for signal in self.backend.SIGNAL_BY_NAME.values():
            item = W.QListWidgetItem(f"{signal.name}   {signal.unit or ''}")
            item.setData(C.Qt.UserRole, signal.name)
            item.setToolTip(signal.note or "")
            item.setFlags(item.flags() | C.Qt.ItemIsUserCheckable)
            item.setCheckState(C.Qt.Checked if signal.name in self.backend.DEFAULT_SIGNALS else C.Qt.Unchecked)
            self.signals.addItem(item)

    def review_adx(self):
        if not self.kline_profile:
            return self.error("Import an ADX first.")
        try:
            plan = self.kline_profile.plan()
            lines = ["Fixed-frame serial transport plan", f"Initial baud: {self.kline_profile.baud}", ""]
            for phase, steps in plan.items():
                lines.append(phase.upper())
                for node in steps:
                    line = f"  {node.get('id')} - {node.tag}"
                    if node.findtext("baud"):
                        line += f" - baud {node.findtext('baud')}"
                    if node.tag == "ADXCSENDCOMMAND":
                        line += " - TX " + node.findtext("bytestring", "")
                        if node.find("SNDCMDCHECKSUM") is not None:
                            line += " + additive checksum"
                    elif node.tag == "ADXCLISTENPACKET":
                        line += f" - header {node.findtext('headerstring')} - body {node.findtext('packetbodylength')} - payload {node.findtext('packetoffsetinbody')}+{node.findtext('packetsize')}"
                    else:
                        line += f" - pause {node.findtext('totaltimeout')} ms"
                    lines.append(line)
                lines.append("")
            lines.append("Serial timing and vehicle behavior have not been validated on hardware.")
            dialog = W.QDialog(self)
            dialog.setWindowTitle("ADX transport compatibility")
            dialog.resize(950, 600)
            layout = W.QVBoxLayout(dialog)
            text = W.QPlainTextEdit("\n".join(lines))
            text.setReadOnly(True)
            layout.addWidget(text)
            dialog.exec_()
        except Exception as exc:
            self.error(f"ADX cannot run with this transport: {exc}")

    def load_can(self):
        if self.session and self.session.snapshot()["state"] in ("connecting", "recording", "stopping"):
            return self.error("Stop the current capture before reloading the logger.")
        try:
            backend = load_can_backend(self.logger_path.text())
            self.backend = backend
            self.session = backend.Session()
            self.ccp_dashboard.bridge.attach(backend, self.session)
            self.session_kind = 0
            self.log_mode.setCurrentIndex(0)
            self.populate_can_channels()
            self.log_notice.setText(f"{self.signals.count()} channels loaded - No device connection has been opened")
        except Exception as exc:
            self.error(f"CAN backend could not load: {exc}")

    def start_logging(self):
        if self.flasher_panel.busy:
            return self.error("Wait for GKFlasher to finish before starting a capture.")
        if self.process.state() != C.QProcess.NotRunning:
            return self.error("Wait for GKFlasher to finish before starting a capture.")
        if self.session and self.session.snapshot()["state"] in ("connecting", "recording", "stopping"):
            return self.error("A recording is already running or releasing its adapter.")
        try:
            if self.log_mode.currentIndex() == 1:
                if not self.kline_profile:
                    raise ValueError("Import an ADX first.")
                names = [self.signals.item(i).data(C.Qt.UserRole) for i in range(self.signals.count()) if self.signals.item(i).checkState() == C.Qt.Checked]
                if not names:
                    raise ValueError("Choose at least one channel.")
                self.kline_profile.plan()
                path = W.QFileDialog.getSaveFileName(self, "Record K-line to a new CSV file", "kline_log.csv", "CSV (*.csv)")[0]
                if not path:
                    return
                session = KLineSession(self.kline_profile)
                session.start(names, self.channel.text(), path, self.verify_sum.isChecked())
                self.session = session
                self.session_kind = 1
            else:
                if not self.backend:
                    self.load_can()
                if not self.backend:
                    return
                names = [self.signals.item(i).data(C.Qt.UserRole) for i in range(self.signals.count()) if self.signals.item(i).checkState() == C.Qt.Checked]
                if not names:
                    raise ValueError("Choose at least one channel.")
                self.session = self.ccp_dashboard.bridge.session
                self.session_kind = 0
                self.session.start(names, self.channel.text(), self.bitrate.value(), self.rate.currentData(), "record")
            self.log_next = 0
            self.log_rows = []
        except Exception as exc:
            self.error(exc)

    def stop_logging(self):
        if self.session:
            self.session.stop()

    def poll_logger(self):
        if not self.session:
            return
        state = self.session.snapshot()
        if state["state"] == "idle" and not state["count"] and not state["error"]:
            return
        transport = "K-line" if self.session_kind else "CAN"
        self.log_notice.setText(f"{transport} {state['state']} - {state['count']} samples - {state['incomplete']} incomplete - {state['output']} {state['error']}")
        result = self.session.samples(self.log_next)
        if result["rows"]:
            self.log_next = result["next"]
            self.log_rows.extend(result["rows"])
            self.log_rows = self.log_rows[-10000:]
            self.display_log_row(result["rows"][-1])

    def display_log_row(self, row):
        self.log_table.setRowCount(len(row))
        for index, (name, value) in enumerate(row.items()):
            self.log_table.setItem(index, 0, W.QTableWidgetItem(str(name)))
            self.log_table.setItem(index, 1, W.QTableWidgetItem(f"{value:.5g}" if isinstance(value, (int, float)) else str(value)))
        self.log_table.resizeColumnsToContents()

    def open_adx(self):
        path = self.choose_file("Import ADX", "TunerPro acquisition definition (*.adx)")
        if path:
            try:
                self.adx = ADXDefinition.load(path)
                profile = Profile(path)
                dialog = W.QDialog(self)
                dialog.setWindowTitle("ADX definition - " + Path(path).name)
                dialog.resize(900, 650)
                layout = W.QVBoxLayout(dialog)
                layout.addWidget(label(f"{len(self.adx.channels)} channels - {self.adx.baud} baud - {len(self.adx.commands)} commands / macros", "accent"))
                supported = sum(not channel.reason for channel in profile.channels)
                layout.addWidget(label(f"{supported} numeric channels supported for experimental serial acquisition. Review ADX transport before connecting. Other channel types remain inspection-only.", "muted", True))
                tabs = W.QTabWidget()
                table = W.QTableWidget(len(self.adx.channels), 6)
                table.setHorizontalHeaderLabels(["Channel", "ID", "Packet offset", "Bits", "Equation", "Parent command"])
                table.setEditTriggers(W.QAbstractItemView.NoEditTriggers)
                for r, channel in enumerate(self.adx.channels):
                    for c, key in enumerate(("name", "id", "offset", "bits", "equation", "parent")):
                        table.setItem(r, c, W.QTableWidgetItem(str(channel[key])))
                table.resizeColumnsToContents()
                tabs.addTab(table, "Channels")
                commands = W.QPlainTextEdit("\n\n".join(self.adx.commands))
                commands.setReadOnly(True)
                tabs.addTab(commands, "Commands and macros")
                layout.addWidget(tabs)
                dialog.exec_()
                if self.session and self.session.snapshot()["state"] in ("connecting", "recording", "stopping"):
                    return self.error("Stop the current recording before selecting a new ADX transport.")
                self.kline_profile = profile
                self.log_mode.setCurrentIndex(1)
                self.logging_mode_changed(1)
                self.stack.setCurrentIndex(1)
            except Exception as exc:
                self.error(exc)

    def open_log_csv(self):
        if self.session and self.session.snapshot()["state"] in ("connecting", "recording", "stopping"):
            return self.error("Stop the recording before opening a log.")
        path = self.choose_file("Open recorded log", "CSV (*.csv)")
        if path:
            try:
                with open(path, encoding="utf-8-sig", newline="") as stream:
                    rows = list(csv.DictReader(stream))
                if not rows:
                    raise ValueError("Log has no samples.")
                self.log_rows = rows[-10000:]
                self.display_log_row(rows[-1])
                self.log_notice.setText(f"{Path(path).name} - {len(rows)} samples - showing final sample")
            except Exception as exc:
                self.error(exc)

    def export_log(self):
        if not self.log_rows:
            return self.error("There are no samples to export.")
        path = W.QFileDialog.getSaveFileName(self, "Export buffered samples", "gktuner_log.csv", "CSV (*.csv)")[0]
        if path:
            try:
                fields = list(dict.fromkeys(key for row in self.log_rows for key in row))
                with open(path, "w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(self.log_rows)
            except Exception as exc:
                self.error(exc)

    def build_flashing(self):
        from .flashing import FlashingPanel
        self.flasher_panel = FlashingPanel(self)
        self.flashing_scroll = W.QScrollArea()
        self.flashing_scroll.setFrameShape(W.QFrame.NoFrame)
        self.flashing_scroll.setWidgetResizable(True)
        self.flashing_scroll.setAlignment(C.Qt.AlignLeft | C.Qt.AlignTop)
        self.flashing_scroll.setWidget(self.flasher_panel)
        self.flashing_scroll.viewport().installEventFilter(self.flasher_panel)
        self.stack.addWidget(self.flashing_scroll)

    def browse_flash_binary(self):
        path = self.choose_file("Choose saved binary", "Binary (*.bin);;All files (*)")
        if path:
            self.flash_binary.setText(path)

    def run_flash(self):
        if self.flasher_panel.busy:
            return self.error('Wait for the current GKFlasher operation to finish.')
        if self.session:
            state = self.session.snapshot()["state"]
            if state in ("connecting", "recording", "stopping"):
                return self.error("Stop the CAN capture and wait for the adapter to release before using GKFlasher.")
        if self.process.state() != C.QProcess.NotRunning:
            return
        operation = self.flash_operation.currentText()
        output = None
        if operation.startswith("Read"):
            output = W.QFileDialog.getSaveFileName(self, "Read ECU binary to a new file", "ecu_read.bin", "Binary (*.bin)")[0]
            if not output:
                return
        try:
            args = flasher_command(self.flasher_path.text(), self.flash_protocol.currentData(), self.flash_interface.text(), operation, self.flash_binary.text(), output)
            if operation.startswith("Flash"):
                if self.document and self.document.dirty:
                    raise ValueError("Save or discard calibration changes before starting a flash operation.")
                binary = Path(self.flash_binary.text()).resolve()
                import hashlib
                digest = hashlib.sha256(binary.read_bytes()).hexdigest()
                answer = W.QMessageBox.warning(self, "Review flash operation", f"{operation}\n\nFile: {binary}\nSize: {binary.stat().st_size:,} bytes\nSHA-256: {digest}\nProtocol: {self.flash_protocol.currentText()}\nInterface: {self.flash_interface.text()}\n\nContinue to GKFlasher's identification and confirmation?", W.QMessageBox.Yes | W.QMessageBox.Cancel, W.QMessageBox.Cancel)
                if answer != W.QMessageBox.Yes:
                    return
            self.flashing = operation.startswith("Flash")
            self.prompt_buffer = ""
            self.output_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            self.console.clear()
            self.console.insertPlainText(f"Starting: {operation}\n")
            self.process.setWorkingDirectory(str(Path(self.flasher_path.text()).resolve()))
            self.process.start(sys.executable, ['--gkflasher-cli', *args[2:]] if frozen() else args)
            if not self.process.waitForStarted(3000):
                self.flashing = False
                raise ValueError(self.process.errorString())
            self.flash_run.setEnabled(False)
        except Exception as exc:
            self.error(exc)

    def process_output(self):
        value = self.output_decoder.decode(bytes(self.process.readAllStandardOutput()))
        self.console.moveCursor(G.QTextCursor.End)
        self.console.insertPlainText(value)
        self.console.ensureCursorVisible()
        self.prompt_buffer = (self.prompt_buffer + value)[-4096:]
        tail = self.prompt_buffer.rstrip()
        confirmation = "[y/n]" in tail.split("\n")[-1] and tail.endswith(":")
        selection = tail.endswith("ECU or any other char to abort:")
        self.confirm_yes.setEnabled(confirmation)
        self.confirm_no.setEnabled(confirmation)
        self.flash_response.setEnabled(selection)
        self.send_response.setEnabled(selection)
        self.flasher_panel.prompt_widget.setVisible(confirmation or selection)

    def respond_flash_prompt(self, value):
        if self.process.state() == C.QProcess.NotRunning:
            return
        if not (self.confirm_yes.isEnabled() or self.send_response.isEnabled()):
            return
        # One response per visible prompt; never queue confirmations in advance.
        self.process.write((value + "\n").encode("utf-8"))
        self.prompt_buffer = ""
        self.confirm_yes.setEnabled(False)
        self.confirm_no.setEnabled(False)
        self.flash_response.setEnabled(False)
        self.send_response.setEnabled(False)
        self.flash_response.clear()
        self.flasher_panel.prompt_widget.hide()

    def process_finished(self, code, status):
        self.process_output()
        self.console.appendPlainText(f"\nGKFlasher exited with code {code}.")
        self.flashing = False
        self.flash_run.setEnabled(True)
        self.confirm_yes.setEnabled(False)
        self.confirm_no.setEnabled(False)
        self.flash_response.setEnabled(False)
        self.send_response.setEnabled(False)

    def build_settings(self):
        page, layout = page_layout("Program properties", "Choose readable display settings and configure your existing device backends.")
        self.settings_content = page
        appearance = W.QGroupBox("Appearance")
        display_form = W.QFormLayout(appearance)
        display_form.setFieldGrowthPolicy(W.QFormLayout.FieldsStayAtSizeHint)
        self.theme_choice = W.QComboBox()
        self.theme_choice.addItems(["Light", "Dark"])
        self.theme_choice.setCurrentText(self.settings.value("theme", "Light"))
        self.ui_scale = W.QSpinBox()
        self.ui_scale.setRange(75, 200)
        self.ui_scale.setSingleStep(5)
        self.ui_scale.setSuffix(" %")
        self.ui_scale.setValue(int(self.settings.value("ui_scale", 100)))
        self.ui_scale.setToolTip("Scale text, controls, table cells and icons relative to the system DPI. Applies immediately and is remembered.")
        display_form.addRow("Color theme", self.theme_choice)
        display_form.addRow("Interface scaling", self.ui_scale)
        self.appearance_apply = button("Apply appearance", lambda: self.apply_appearance(persist=True), True)
        display_form.addRow('', self.appearance_apply)
        layout.addWidget(appearance)
        from .palette_editor import PaletteEditor
        self.palette_editor = PaletteEditor(self)
        layout.addWidget(self.palette_editor)
        form = W.QFormLayout()
        self.logger_path = W.QLineEdit(str(backend_setting(self.settings, 'CANLogger')))
        self.flasher_path = W.QLineEdit(str(backend_setting(self.settings, 'GKFlasher')))
        for title, field in (("CAN Logger folder", self.logger_path), ("GKFlasher folder", self.flasher_path)):
            row = W.QHBoxLayout()
            row.addWidget(field)
            row.addWidget(button("Browse…", lambda checked=False, f=field: self.browse_folder(f)))
            form.addRow(title, row)
        self.bitrate = W.QSpinBox()
        self.bitrate.setRange(10000, 2000000)
        self.bitrate.setValue(int(self.settings.value("bitrate", 500000)))
        self.bitrate.setSingleStep(50000)
        form.addRow("CAN bitrate", self.bitrate)
        layout.addLayout(form)
        layout.addWidget(button("Save settings", self.save_settings, True), 0, C.Qt.AlignLeft)
        layout.addWidget(label("ADX serial acquisition supports a fixed-frame subset and is experimental. Live tuning is planned.", "muted", True))
        layout.addWidget(button("View compatibility and roadmap", self.show_compatibility), 0, C.Qt.AlignLeft)
        layout.addStretch()
        self.settings_scroll = W.QScrollArea()
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setAlignment(C.Qt.AlignLeft | C.Qt.AlignTop)
        self.settings_scroll.setFrameShape(W.QFrame.NoFrame)
        self.settings_scroll.setWidget(page)
        self.stack.addWidget(self.settings_scroll)

    def browse_folder(self, field):
        path = W.QFileDialog.getExistingDirectory(self, "Choose backend folder", field.text())
        if path:
            field.setText(path)

    def save_settings(self):
        self.settings.setValue("logger_path", self.logger_path.text())
        self.settings.setValue("flasher_path", self.flasher_path.text())
        self.settings.setValue("bitrate", self.bitrate.value())
        self.apply_appearance(persist=True)
        self.statusBar().showMessage("Settings saved")

    def apply_appearance(self, persist=False):
        scale = self.ui_scale.value()
        self.appearance_scale = scale / 100
        theme = self.theme_choice.currentText()
        custom = self.palette_overrides.get(theme, {})
        self.active_palette = palette_for(theme, custom)
        W.QApplication.instance().setStyleSheet(stylesheet(theme, scale, custom))
        self.mdi.setBackground(G.QBrush(G.QColor(self.active_palette['workspace'])))
        self.flasher_panel.setMaximumWidth(round(1100 * self.appearance_scale))
        self.flasher_panel.setMaximumHeight(round(1000 * self.appearance_scale))
        for buttons in self.flasher_panel.actions.values():
            for action_button in buttons:
                action_button.setMaximumWidth(round(280 * self.appearance_scale))
        self.settings_content.setMaximumWidth(round(860 * self.appearance_scale))
        self.bitrate.setMaximumWidth(round(180 * self.appearance_scale))
        self.appearance_apply.setMaximumWidth(round(220 * self.appearance_scale))
        self.drawer.width = round(240 * self.appearance_scale)
        self.brand_logo.setPixmap(self.logo_icon.pixmap(round(40 * self.appearance_scale), round(40 * self.appearance_scale)))
        self.drawer.reposition()
        self.command_bar.setIconSize(C.QSize(round(20 * self.appearance_scale), round(20 * self.appearance_scale)))
        self.tree.setIconSize(C.QSize(round(20 * self.appearance_scale), round(20 * self.appearance_scale)))
        for icon_label in self.findChildren(W.QLabel):
            kind = icon_label.property("itemKind")
            if kind:
                icon_label.setPixmap(item_icon(kind).pixmap(round(18 * self.appearance_scale), round(18 * self.appearance_scale)))
        for table in self.findChildren(W.QTableWidget):
            height = G.QFontMetrics(table.font()).height() + round(7 * self.appearance_scale)
            table.verticalHeader().setDefaultSectionSize(height)
            table.verticalHeader().setMinimumSectionSize(height)
            table.resizeColumnsToContents()
        for editor in self.open_editors.values():
            editor.toolbar.setIconSize(C.QSize(round(16 * self.appearance_scale), round(16 * self.appearance_scale)))
            editor.refresh()
        if persist:
            self.settings.setValue("theme", theme)
            self.settings.setValue("ui_scale", scale)
            self.settings.setValue('colour_palettes', json.dumps(self.palette_overrides))
            self.settings.sync()
        self.schedule_tile()

        # Qt finishes inherited font/layout changes on the following event passes.
        # Refit once after those settle, without disturbing a manual arrangement.
        self.appearance_timer.start(25)
        self.update_item_colors()
        self.palette_editor.refresh()
        self.ccp_dashboard.apply_appearance()
        self.flasher_panel.layout_for_width(self.flashing_scroll.viewport().width(), self.appearance_scale)

    def show_compatibility(self):
        dialog = W.QDialog(self)
        dialog.setWindowTitle("GK Tuner - Compatibility and roadmap")
        dialog.resize(850, 650)
        layout = W.QVBoxLayout(dialog)
        text = W.QTextBrowser()
        path = Path(__file__).resolve().parents[1] / "COMPATIBILITY.md"
        text.setMarkdown(path.read_text(encoding="utf-8", errors='replace') if path.is_file() else "# GK Tuner compatibility\nNumeric XDF map editing, CAN logger integration, experimental ADX serial acquisition, and GKFlasher operations. Full TunerPro parity and live tuning are not available in this preview. GKFlasher checksum correction is available in Flashing File tools. See the source repository's COMPATIBILITY.md for details.")
        layout.addWidget(text)
        dialog.exec_()

    def closeEvent(self, event):
        if self.flasher_panel.busy:
            self.error("Wait for the GKFlasher operation to finish before closing GK Tuner.")
            event.ignore()
            return
        if self.process.state() != C.QProcess.NotRunning:
            self.error("Wait for the GKFlasher operation to finish before closing GK Tuner.")
            event.ignore()
            return
        if self.session:
            state = self.session.snapshot()["state"]
            if state in ("connecting", "recording", "stopping"):
                self.session.stop()
                self.error("Stopping the capture. Close GK Tuner once the adapter has been released.")
                event.ignore()
                return
        if not self.guard_unsaved():
            event.ignore()
            return
        self.save_settings()
        self.save_workspace_session()
        event.accept()


def main():
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('OpenGK.GKTuner')
    C.QCoreApplication.setAttribute(C.Qt.AA_EnableHighDpiScaling)
    app = W.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.restore_session()
    window.show()
    return app.exec_()
