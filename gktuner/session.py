"""Restore saved-file paths and window arrangement, never unsaved BIN bytes."""
import json
from pathlib import Path
from PyQt5 import QtCore as C
from .core import BinaryDocument, Definition


class WorkspaceSession:
    def save_workspace_session(self):
        entries = []
        for editor in self.open_editors.values():
            rect = editor.subwindow.geometry()
            entry = {"uid": editor.item.uid, "rect": [rect.x(), rect.y(), rect.width(), rect.height()]}
            entry["raw"] = getattr(editor, "raw_view", False)
            if hasattr(editor.item, "parent_uid"):
                entry.update(parent=editor.item.parent_uid, axis=editor.item.axis_which)
            entries.append(entry)
        state = {"bin": str(getattr(self, "session_bin_path", None) or self.document.path) if self.document else None,
                 "xdf": str(self.definition.path) if self.definition else None,
                 "auto_tile": self.auto_tile.isChecked(), "side_by_side": self.layout_side_by_side,
                 "geometry": bytes(self.saveGeometry().toBase64()).decode("ascii"),
                 "page": self.stack.currentIndex(), "windows": entries,
                 "splitter": self.map_splitter.sizes(),
                 "navigation_open": self.drawer.opened,
                 "active": self.current_map.uid if self.current_map else None}
        self.settings.setValue("workspace_session", json.dumps(state))
        self.settings.sync()

    def restore_session(self):
        errors = []
        try:
            state = json.loads(self.settings.value("workspace_session", "{}"))
            if not state:
                return
            for kind, cls in (("bin", BinaryDocument), ("xdf", Definition)):
                path = state.get(kind)
                if path:
                    try:
                        obj = cls(Path(path))
                        if kind == "bin":
                            self.document = obj
                            self.session_bin_path = str(obj.path)
                        else:
                            self.definition = obj
                    except (OSError, ValueError) as exc:
                        errors.append(f"{kind.upper()}: {exc}")
            if state.get("geometry"):
                self.restoreGeometry(C.QByteArray.fromBase64(state["geometry"].encode("ascii")))
            self.auto_tile.setChecked(False)
            self.layout_side_by_side = bool(state.get("side_by_side", False))
            if self.definition:
                self.populate_tree()
                for entry in state.get("windows", []):
                    item = self.definition.by_id.get(entry["uid"].lower())
                    if entry.get("parent"):
                        parent = self.definition.by_id.get(entry["parent"])
                        item = self.definition.internal_axis(parent, entry["axis"]) if parent else None
                    if item:
                        editor = self.open_map(item)
                        if entry.get("raw") and hasattr(editor, "raw_action"):
                            editor.raw_action.setChecked(True)
                            editor.toggle_raw(True)
                        rect = entry.get("rect", [])
                        if len(rect) == 4:
                            editor.subwindow.setGeometry(*[int(v) for v in rect])
                active = self.open_editors.get(str(state.get("active", "")).lower())
                if active:
                    self.mdi.setActiveSubWindow(active.subwindow)
            self.auto_tile.setChecked(bool(state.get("auto_tile", True)))
            if len(state.get("splitter", [])) == 2:
                self.map_splitter.setSizes([int(v) for v in state['splitter']])
            self.stack.setCurrentIndex(max(0, min(self.stack.count() - 1, int(state.get("page", 0)))))
            self.refresh_map()
            self.drawer.set_open(bool(state.get("navigation_open", False)))
            self.statusBar().showMessage("Session restored" if not errors else "Some session files could not be restored: " + "; ".join(errors))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            self.statusBar().showMessage(f"Session could not be fully restored: {exc}")
