"""Copy/paste definitions without copying or changing BIN contents."""
import copy
import uuid
import xml.etree.ElementTree as ET
from PyQt5 import QtCore as C, QtWidgets as W
from .core import integer
from .definition_tools import candidate_definition

MIME = "application/x-gktuner-xdf-items+xml"


class XdfClipboard:
    def copy_xdf_items(self):
        if self.definition is None:
            return False
        items = [row.data(0, C.Qt.UserRole) for row in self.tree.selectedItems() if row.data(0, C.Qt.UserRole) is not None]
        if not items:
            return False
        selected = {item.uid.lower() for item in items}
        root = ET.Element("GKTUNER_ITEMS", version="1", source=str(self.definition.source_path).casefold())
        header = ET.SubElement(root, "CATEGORIES")
        header.extend(copy.deepcopy(self.definition.root.find("XDFHEADER").findall("CATEGORY")))
        pending, seen = list(items), set()
        while pending:
            item = pending.pop(0)
            uid = item.uid.lower()
            if uid in seen:
                continue
            seen.add(uid)
            wrapper = ET.SubElement(root, "ITEM", selected=str(int(uid in selected)))
            node = copy.deepcopy(item.node)
            for data in node.iter("EMBEDDEDDATA"):
                if "mmedelementsizebits" not in data.attrib:
                    data.set("mmedelementsizebits", str(self.definition.default_bits))
                if "mmedtypeflags" not in data.attrib:
                    data.set("mmedtypeflags", str(self.definition.default_flags))
            wrapper.append(node)
            for link in item.node.iter("embedinfo"):
                target = self.definition.by_id.get(link.get("linkobjid", "").lower())
                if target is not None:
                    pending.append(target)
        data = ET.tostring(root, encoding="utf-8")
        mime = C.QMimeData()
        mime.setData(MIME, data)
        mime.setText(data.decode("utf-8"))
        W.QApplication.clipboard().setMimeData(mime)
        self.statusBar().showMessage(f"Copied {len(items)} XDF items")
        return True

    def paste_xdf_items(self):
        if self.definition is None:
            return self.error("Load an XDF first.")
        try:
            mime = W.QApplication.clipboard().mimeData()
            data = bytes(mime.data(MIME)) if mime.hasFormat(MIME) else mime.text().encode("utf-8")
            if not data or len(data) > 4 * 1024 * 1024 or b"<!" in data:
                raise ValueError("Clipboard does not contain a supported XDF item copy.")
            copied = ET.fromstring(data)
            if copied.tag != "GKTUNER_ITEMS" or copied.get("version") != "1":
                raise ValueError("Copy XDF items from the item browser first.")
            wrappers = copied.findall("ITEM")
            if not 1 <= len(wrappers) <= 4096:
                raise ValueError("Unsupported number of copied XDF items.")
            same_source = copied.get("source") == str(self.definition.source_path).casefold()
            included = [wrapper for wrapper in wrappers if wrapper.get("selected") == "1" or not same_source or not len(wrapper) or wrapper[0].get("uniqueid", "").lower() not in self.definition.by_id]
            nodes, ids, used = [], {}, set(self.definition.by_id)
            for wrapper in included:
                if len(wrapper) != 1 or wrapper[0].tag not in ("XDFTABLE", "XDFCONSTANT", "XDFFUNCTION", "XDFPATCH", "XDFFLAG", "XDFSWITCH"):
                    raise ValueError("Unsupported clipboard item format.")
                node = copy.deepcopy(wrapper[0])
                original = node.get("uniqueid", "").lower()
                if not original or original in ids:
                    raise ValueError("Clipboard item IDs must be unique.")
                uid = "0x" + uuid.uuid4().hex[:8]
                while uid.lower() in used:
                    uid = "0x" + uuid.uuid4().hex[:8]
                used.add(uid.lower())
                ids[original] = uid
                node.set("uniqueid", uid)
                title = node.find("title")
                if title is not None:
                    title.text = "Copy of " + (title.text or node.tag)
                nodes.append((node, wrapper.get("selected") == "1"))
            root = copy.deepcopy(self.definition.root)
            header = root.find("XDFHEADER")
            source_categories = {integer(n.get("index")) + 1: n.get("name", "") for n in copied.findall("CATEGORIES/CATEGORY")}
            target_categories = {n.get("name", ""): integer(n.get("index")) + 1 for n in header.findall("CATEGORY")}
            for node, _ in nodes:
                for membership in node.findall("CATEGORYMEM"):
                    old = integer(membership.get("category"))
                    if not old:
                        continue
                    name = source_categories.get(old, f"Imported category {old}")
                    if name not in target_categories:
                        category_id = max(target_categories.values(), default=0) + 1
                        ET.SubElement(header, "CATEGORY", index=str(category_id - 1), name=name)
                        target_categories[name] = category_id
                    membership.set("category", str(target_categories[name]))
                for link in node.iter("embedinfo"):
                    uid = link.get("linkobjid", "").lower()
                    if uid in ids:
                        link.set("linkobjid", ids[uid])
                    elif uid and not same_source:
                        raise ValueError("A copied item has an unresolved linked scale; fix its link before copying between XDF files.")
                root.append(node)
            result = candidate_definition(self.definition, root)
            for node, _ in nodes:
                item = result.by_id[node.get("uniqueid").lower()]
                if not item.reason and self.document is not None:
                    low, high = item.storage_bounds()
                    if low < 0 or high > len(self.document.data):
                        raise ValueError("A pasted item would be outside the current BIN.")
            self.apply_definition(result)
            selected_ids = {node.get("uniqueid").lower() for node, selected in nodes if selected}
            self.tree.clearSelection()
            for i in range(self.tree.topLevelItemCount()):
                group = self.tree.topLevelItem(i)
                for j in range(group.childCount()):
                    child = group.child(j)
                    if child.data(0, C.Qt.UserRole).uid.lower() in selected_ids:
                        child.setSelected(True)
                        group.setExpanded(True)
            self.statusBar().showMessage(f"Pasted {len(selected_ids)} XDF items; Save XDF to keep them")
            return True
        except (ValueError, TypeError, AttributeError, ET.ParseError) as exc:
            self.error(exc)
            return False
