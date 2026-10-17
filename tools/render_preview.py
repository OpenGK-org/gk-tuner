"""Render desktop previews without opening hardware or changing user settings."""
import os
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt5 import QtWidgets as W, QtGui as G, QtTest as T
from gktuner.app import MainWindow, STYLE
from gktuner.properties import ItemProperties


def main():
    app = W.QApplication(["gktuner-check"])
    if not G.QFontDatabase().families():
        for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "consola.ttf", "trebuc.ttf"):
            G.QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + name)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.theme_choice.setCurrentText("Light")
    window.ui_scale.setValue(100)
    window.apply_appearance(persist=False)
    window.open_demo()
    window.show()
    output = Path(__file__).resolve().parents[1] / "artifacts"
    output.mkdir(exist_ok=True)
    for name, page, tab in (("calibration", 0, 0), ("wireframe", 0, 1), ("flashing", 2, 0), ("settings", 4, 0)):
        window.stack.setCurrentIndex(page)
        if name == "wireframe":
            window.active_editor.graph_action.trigger()
            window.active_editor.graph_window.mode.setCurrentText("Wireframe")
        app.processEvents()
        target = window.active_editor.graph_window if name == "wireframe" else window
        target.grab().save(str(output / f"gk-tuner-{name}.png"))
        if name == "wireframe":
            window.active_editor.graph_window.close()
    window.stack.setCurrentIndex(0)
    first = window.definition.maps[0]
    window.open_map(window.definition.maps[1])
    window.open_map(first)
    window.views.setCurrentIndex(0)
    window.tree.collapseAll()
    app.processEvents()
    window.grab().save(str(output / "gk-tuner-map-editor.png"))
    dialog = ItemProperties(window, first)
    dialog.show()
    for index, name in enumerate(("general", "rows", "columns", "conversion", "da")):
        dialog.tabs.setCurrentIndex(index)
        app.processEvents()
        dialog.grab().save(str(output / f"gk-tuner-properties-{name}.png"))
    dialog.reject()
    # A working table and a comparison table visible simultaneously.
    reference = bytearray(window.document.original)
    fuel = window.definition.maps[1]
    for r in range(fuel.rows):
        for c in range(fuel.cols):
            value = fuel.value(window.document.original, r, c) + .025 * (c - (fuel.cols - 1) / 2) / (fuel.cols / 2)
            offset = fuel.offset(r, c)
            reference[offset:offset + 2] = fuel.encode(value, r, c)
    window.compare = bytes(reference)
    window.compare_name = "Synthetic reference"
    compared = window.open_map(fuel)
    compared.set_compare_mode("Difference")
    compared.compare_action.trigger()
    app.processEvents()
    window.tile_editors(True)
    app.processEvents()
    window.grab().save(str(output / "gk-tuner-multi-window.png"))
    window.tile_editors(False)
    constant = window.open_map(window.definition.maps[2])
    constant.compare_action.trigger()
    app.processEvents()
    window.tile_editors(False)
    app.processEvents()
    window.grab().save(str(output / "gk-tuner-compact-workspace.png"))
    first_editor = window.open_map(first)
    first_editor.table.setCurrentCell(2, 3)
    first_editor.table.setRangeSelected(W.QTableWidgetSelectionRange(2, 3, 3, 4), True)
    first_editor.graph_action.trigger()
    app.processEvents()
    first_editor.graph_window.grab().save(str(output / "gk-tuner-graph-demo.png"))
    first_editor.graph_window.close()
    constant.subwindow.grab().save(str(output / "gk-tuner-constant.png"))
    window.drawer.set_open(True)
    window.drawer.animation.setCurrentTime(window.drawer.animation.duration())
    window.grab().save(str(output / "gk-tuner-navigation.png"))
    window.drawer.set_open(False)
    window.drawer.animation.setCurrentTime(window.drawer.animation.duration())
    window.stack.setCurrentIndex(4)
    window.ui_scale.setValue(125)
    window.theme_choice.setCurrentText("Dark")
    window.apply_appearance(persist=False)
    app.processEvents()
    window.grab().save(str(output / "gk-tuner-appearance.png"))
    window.stack.setCurrentIndex(0)
    window.ui_scale.setValue(100)
    window.apply_appearance(persist=False)
    T.QTest.qWait(60)
    window.grab().save(str(output / "gk-tuner-dark-workspace.png"))
    window.theme_choice.setCurrentText("Light")
    window.apply_appearance(persist=False)
    with tempfile.TemporaryDirectory() as temporary:
        paths = []
        for name in ("Stock", "Stage 1", "Stage 2", "Ignition test", "Fuel test", "Backup"):
            path = Path(temporary) / f"DEMO - {name}.bin"
            path.write_bytes(reference)
            paths.append(path)
        window.load_compare_paths(paths)
        app.processEvents()
        window.compare_menu.popup(window.compare_button.mapToGlobal(window.compare_button.rect().bottomLeft()))
        app.processEvents()
        window.compare_menu.grab().save(str(output / "gk-tuner-compare-menu.png"))
        window.compare_menu.hide()
    print(f"Saved workspace and property previews to {output}")


if __name__ == "__main__":
    main()
