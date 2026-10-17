"""Render definition/patch workflows using disposable synthetic files only."""
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W, QtTest as T
from gktuner.app import MainWindow
from gktuner.core import BinaryDocument, Definition
from gktuner.demo import create_demo
from gktuner.definition_tools import HeaderEditor, NewItemDialog, candidate_definition
from gktuner.patch_editor import PatchDefinitionDialog, MapPatchDialog


def main():
    app = W.QApplication(["gktuner-check"])
    app.setStyle("Fusion")
    for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
        G.QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + name)
    output = Path(__file__).resolve().parents[1] / "artifacts"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        binary, xdf = create_demo(folder)
        window = MainWindow(settings=C.QSettings(str(folder / "preview.ini"), C.QSettings.IniFormat))
        window.document = BinaryDocument(binary)
        window.definition = Definition(xdf)
        root = ET.fromstring(ET.tostring(window.definition.root))
        patch = ET.SubElement(root, "XDFPATCH", uniqueid="0x777")
        ET.SubElement(patch, "title").text = "Example overwrite patch · DEMO"
        ET.SubElement(patch, "description").text = "Synthetic demonstration of expected-byte checks."
        ET.SubElement(patch, "CATEGORYMEM", category="1", index="0")
        ET.SubElement(patch, "XDFPATCHENTRY", name="Example memory bytes", address="0x258", datasize="0x2", patchdata="1122", basedata="0000")
        window.apply_definition(candidate_definition(window.definition, root))
        window.show()
        first = window.open_map(window.definition.maps[0])
        first.table.item(0, 0).setText("25")
        first.commit()
        second = window.open_map(window.definition.maps[1])
        T.QTest.qWait(60)
        window.grab().save(str(output / "gk-tuner-saved-table.png"))
        first.raw_action.trigger()
        app.processEvents()
        first.subwindow.grab().save(str(output / "gk-tuner-raw-hex.png"))
        first.raw_action.trigger()
        patch_item = window.definition.by_id['0x777']
        patch_window = window.open_map(patch_item)
        T.QTest.qWait(60)
        patch_window.subwindow.grab().save(str(output / "gk-tuner-patch-ready.png"))
        patch_window.apply_patch()
        patch_window.subwindow.grab().save(str(output / "gk-tuner-patch-applied.png"))
        window.document.undo()
        window.document.data[600] = 0x7F
        window.refresh_map()
        window.fit_editor(patch_window)
        app.processEvents()
        patch_window.subwindow.grab().save(str(output / "gk-tuner-patch-mismatches.png"))
        window.document.data[600] = 0
        window.refresh_map()
        dialog = PatchDefinitionDialog(window, patch_item)
        dialog.show()
        app.processEvents()
        dialog.grab().save(str(output / "gk-tuner-patch-properties.png"))
        map_dialog = MapPatchDialog(dialog)
        map_dialog.show()
        map_dialog.table.item(0, 0).setText("30")
        app.processEvents()
        map_dialog.grab().save(str(output / "gk-tuner-patch-from-map.png"))
        map_dialog.reject()
        dialog.reject()
        header = HeaderEditor(window)
        header.show()
        app.processEvents()
        header.grab().save(str(output / "gk-tuner-header.png"))
        header.reject()
        new = NewItemDialog(window)
        new.show()
        app.processEvents()
        new.grab().save(str(output / "gk-tuner-new-item.png"))
        new.reject()
        assert binary.read_bytes() == window.document.original
        print("Rendered saved table, patch status/properties/map entry, header and item creation previews. Source BIN untouched.")


if __name__ == "__main__":
    main()
