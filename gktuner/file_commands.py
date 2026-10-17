"""Recent files and the shared six-slot reference binary selection."""
import os
from pathlib import Path
from PyQt5 import QtCore as C, QtWidgets as W


class FileCommands:
    def correct_map_checksum(self):
        if self.document is None:
            return self.error('Open a BIN before correcting its checksum.')
        if self.flasher_panel.busy or self.process.state() != C.QProcess.NotRunning:
            return self.error('Wait for the current GKFlasher operation to finish.')
        pending = [editor for editor in self.open_editors.values() if getattr(editor, 'pending', False)]
        if self.document.dirty or pending:
            answer = W.QMessageBox.question(self, 'Save before checksum correction',
                'Save all edited tables and the working BIN before calculating its checksum?',
                W.QMessageBox.Save | W.QMessageBox.Cancel, W.QMessageBox.Save)
            if answer != W.QMessageBox.Save:
                return
            for editor in pending:
                if not editor.commit():
                    return
            if not self.save_binary():
                return
        try:
            from .checksum import checksum_proposal
            segments, preview = checksum_proposal(self.flasher_path.text(), bytes(self.document.data))
            if not segments:
                W.QMessageBox.information(self, 'Checksum already correct', preview + '\n\nNo correction is needed.')
                return
            answer = W.QMessageBox.question(self, 'Correct BIN checksum', preview +
                '\n\nApply these checksums to the working BIN? Use Save BIN to write the corrected file.',
                W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.No)
            if answer != W.QMessageBox.Yes:
                return
            self.document.write_segments(segments)
            self.refresh_map()
            self.statusBar().showMessage('Checksum corrected - save the BIN to write the corrected file.')
        except Exception as exc:
            self.error(exc)

    def recent_paths(self, kind):
        value = self.settings.value(f"recent_{kind}", [])
        return [value] if isinstance(value, str) else list(value or [])

    def remember_file(self, kind, path):
        path = str(Path(path).resolve())
        paths = [p for p in self.recent_paths(kind) if os.path.normcase(p) != os.path.normcase(path)]
        self.settings.setValue(f"recent_{kind}", [path] + paths[:9])
        self.settings.setValue("last_folder", str(Path(path).parent))
        self.settings.sync()
        self.refresh_recent_menus()

    def refresh_recent_menus(self):
        for kind, menu, callback in (("bin", self.recent_bin_menu, self.load_binary_path),
                                     ("xdf", self.recent_xdf_menu, self.load_xdf_path)):
            menu.clear()
            paths = self.recent_paths(kind)
            for index, path in enumerate(paths):
                action = menu.addAction(f"&{index + 1}  {Path(path).name}")
                action.setToolTip(path)
                action.setStatusTip(path)
                action.triggered.connect(lambda checked=False, p=path, load=callback: load(p))
            if not paths:
                menu.addAction("No recent files").setEnabled(False)
            else:
                menu.addSeparator()
                menu.addAction("Clear recent list", lambda checked=False, k=kind: self.clear_recent(k))

    def clear_recent(self, kind):
        self.settings.setValue(f"recent_{kind}", [])
        self.settings.sync()
        self.refresh_recent_menus()

    def build_compare_menu(self):
        self.compare_menu = W.QMenu("Compare", self)
        load = self.compare_menu.addAction("Load compare BINs…", self.open_compare)
        load.setShortcut("Ctrl+F1")
        self.addAction(load)
        load.setStatusTip("Load into slots 1 onward. Use each slot's options to replace or reload a single BIN.")
        self.compare_menu.addSeparator()
        self.compare_group = W.QActionGroup(self)
        self.compare_group.setExclusive(True)
        self.compare_slot_actions = []
        self.compare_slot_menus = []
        self.slot_manage_actions = []
        for index in range(6):
            menu = self.compare_menu.addMenu("")
            self.compare_slot_menus.append(menu)
            action = menu.addAction("Use this BIN")
            action.setCheckable(True)
            action.setShortcut(f"Ctrl+{index + 1}")
            action.triggered.connect(lambda checked=False, i=index: self.select_compare_slot(i))
            self.compare_group.addAction(action)
            self.addAction(action)
            self.compare_slot_actions.append(action)
            menu.addSeparator()
            menu.addAction("Load / replace…", lambda checked=False, i=index: self.replace_compare_slot(i))
            reload_action = menu.addAction("Reload from disk", lambda checked=False, i=index: self.reload_compare_slot(i))
            clear_action = menu.addAction("Unload", lambda checked=False, i=index: self.clear_compare_slot(i))
            self.slot_manage_actions.append((reload_action, clear_action))
        self.compare_menu.addSeparator()
        self.compare_menu.addAction("Unload all compare BINs", self.clear_comparisons)
        self.update_compare_menu()

    def update_compare_menu(self):
        active = self.active_compare_slot
        self.compare_menu.setTitle(f"Compare - Bin {active + 1}" if active is not None else "Compare")
        for index, action in enumerate(self.compare_slot_actions):
            slot = self.compare_slots[index]
            menu_action = self.compare_slot_menus[index].menuAction()
            menu_action.setText(f"Bin {index + 1} ({Path(slot['path']).name if slot else 'No BIN'})")
            menu_action.setCheckable(True)
            menu_action.setChecked(index == active)
            action.setEnabled(slot is not None)
            action.setText("Use this BIN")
            action.setToolTip(slot['path'] if slot else "Load a reference into this slot")
            action.setStatusTip(action.toolTip())
            action.setChecked(index == active)
            for control in self.slot_manage_actions[index]:
                control.setEnabled(slot is not None)

    def read_compare(self, path):
        if self.document is None:
            raise ValueError("Open a working binary first.")
        path = Path(path).resolve()
        data = path.read_bytes()
        if len(data) != len(self.document.data):
            raise ValueError(f"{path.name}: comparison binary must have the same size as the working binary.")
        return {"path": str(path), "data": data}

    def load_compare_paths(self, paths):
        try:
            if not 1 <= len(paths) <= 6:
                raise ValueError("Choose between one and six comparison binaries.")
            slots = [self.read_compare(path) for path in paths]
            # Validate the complete selection before replacing any existing reference.
            self.compare_slots[:len(slots)] = slots
            self.activate_compare_slot(0)
            return True
        except Exception as exc:
            self.error(exc)
            return False

    def open_compare(self):
        if self.document is None:
            return self.error("Open a working binary first.")
        paths, _ = W.QFileDialog.getOpenFileNames(self, "Load compare BINs (up to six)",
                                               self.settings.value("last_folder", str(Path.cwd())),
                                               "Binary (*.bin *.rom);;All files (*)")
        if paths:
            return self.load_compare_paths(paths)

    def select_compare_slot(self, index):
        if self.compare_slots[index] is None:
            self.replace_compare_slot(index)
        else:
            self.activate_compare_slot(index)
        self.update_compare_menu()

    def activate_compare_slot(self, index):
        slot = self.compare_slots[index]
        if slot is None:
            return
        self.active_compare_slot = index
        self.compare, self.compare_name = slot['data'], Path(slot['path']).name
        self.update_compare_menu()
        self.refresh_map()
        for editor in self.open_editors.values():
            self.fit_editor(editor)
        self.statusBar().showMessage(f"Compare Bin {index + 1}: {slot['path']}")

    def replace_compare_slot(self, index):
        if self.document is None:
            return self.error("Open a working binary first.")
        path = self.choose_file(f"Load compare Bin {index + 1}", "Binary (*.bin *.rom);;All files (*)")
        if path:
            try:
                slot = self.read_compare(path)
                self.compare_slots[index] = slot
                self.activate_compare_slot(index)
            except Exception as exc:
                self.error(exc)

    def reload_compare_slot(self, index):
        slot = self.compare_slots[index]
        if slot is None:
            return
        try:
            updated = self.read_compare(slot['path'])
            self.compare_slots[index] = updated
            if self.active_compare_slot == index:
                self.activate_compare_slot(index)
            self.update_compare_menu()
        except Exception as exc:
            self.error(exc)

    def clear_compare_slot(self, index):
        self.compare_slots[index] = None
        if self.active_compare_slot == index:
            next_slot = next((i for i, slot in enumerate(self.compare_slots) if slot), None)
            if next_slot is None:
                self.clear_comparisons()
                return
            self.activate_compare_slot(next_slot)
        self.update_compare_menu()

    def clear_comparisons(self):
        self.compare_slots = [None] * 6
        self.active_compare_slot = None
        self.compare = None
        self.compare_name = "Reference binary"
        for editor in self.open_editors.values():
            editor.compare_active = False
            editor.compare_action.setChecked(False)
        self.update_compare_menu()
        self.refresh_map()
