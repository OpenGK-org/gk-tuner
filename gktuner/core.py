"""Conservative XDF reader and transactional binary editor. No hardware access."""
from __future__ import annotations

import ast
import copy
import math
import operator
import os
import struct
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


def integer(value, default=0):
    if value is None or value == "":
        return default
    return int(value, 16) if str(value).lower().startswith(("0x", "-0x")) else int(value)


def address_value(value, default=0):
    return default if value is None or str(value).strip() == "" else int(str(value).strip(), 16)


def format_number(value, output_type=1, decimals=None):
    if output_type == 4:
        number = round(value)
        if not 0 <= number <= 255:
            raise ValueError("Text output requires a single-byte character.")
        return chr(number)
    if output_type == 2:
        return str(round(value))
    if output_type == 3:
        return f"0x{round(value):X}"
    return f"{value:.{decimals}f}" if decimals is not None else f"{value:g}"


def xml_file(path, root_tag):
    data = Path(path).read_bytes()
    if len(data) > 32 * 1024 * 1024:
        raise ValueError("Definition exceeds the 32 MB limit.")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("XML entities and document types are not supported.")
    root = ET.fromstring(data)
    if root.tag != root_tag:
        raise ValueError(f"Expected {root_tag}, found {root.tag}.")
    return root


class Equation:
    """Small arithmetic language; never executes Python from a definition."""
    OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv}

    def __init__(self, source="X"):
        self.source = source
        self.tree = ast.parse(source.strip(), mode="eval").body
        if len(list(ast.walk(self.tree))) > 100:
            raise ValueError("Equation is too complex.")
        self._eval(self.tree, 1.0)

    def _eval(self, node, x):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.Name) and node.id.upper() == "X":
            return x
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return self._eval(node.operand, x) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.BinOp) and type(node.op) in self.OPS:
            return self.OPS[type(node.op)](self._eval(node.left, x), self._eval(node.right, x))
        raise ValueError(f"Unsupported equation: {self.source}")

    def __call__(self, x):
        value = float(self._eval(self.tree, x))
        if not math.isfinite(value):
            raise ValueError("Equation produced a non-finite value.")
        return value

    def affine(self):
        def coeff(node):
            if isinstance(node, ast.Constant):
                return 0., float(node.value)
            if isinstance(node, ast.Name):
                return 1., 0.
            if isinstance(node, ast.UnaryOp):
                a, b = coeff(node.operand)
                sign = -1 if isinstance(node.op, ast.USub) else 1
                return a * sign, b * sign
            a, b = coeff(node.left)
            c, d = coeff(node.right)
            if isinstance(node.op, ast.Add):
                return a + c, b + d
            if isinstance(node.op, ast.Sub):
                return a - c, b - d
            if isinstance(node.op, ast.Mult) and not (a and c):
                return a * d + b * c, b * d
            if isinstance(node.op, ast.Div) and not c and d:
                return a / d, b / d
            raise ValueError("Nonlinear equations are view-only in this version.")
        a, b = coeff(self.tree)
        if not a:
            raise ValueError("Constant equations cannot be inverted.")
        return a, b


@dataclass
class Map:
    uid: str
    title: str
    category: str
    kind: str
    node: ET.Element
    address: int = 0
    bits: int = 8
    flags: int = 0
    rows: int = 1
    cols: int = 1
    decimals: int = 2
    units: str = ""
    equation: Equation | None = None
    reason: str = ""
    row_stride: int = 0
    col_stride: int = 0
    minimum: float | None = None
    maximum: float | None = None
    cell_equations: dict = field(default_factory=dict)
    output_type: int = 1
    origin_adjust: int = 0

    def equation_for(self, row, col):
        return self.cell_equations.get((row, col), self.cell_equations.get((row, None), self.cell_equations.get((None, col), self.equation)))

    def offset(self, row, col):
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise ValueError("Cell is outside the map.")
        return self.address + self.origin_adjust + row * self.row_stride + col * self.col_stride

    def storage_bounds(self):
        corners = [self.offset(r, c) for r in (0, self.rows - 1) for c in (0, self.cols - 1)]
        return min(corners), max(corners) + self.bits // 8

    def raw(self, data, row, col):
        start = self.offset(row, col)
        size = self.bits // 8
        if start < 0 or start + size > len(data):
            raise ValueError(f"Map address 0x{start:X} is outside this binary.")
        value = data[start:start + size]
        endian = "little" if self.flags & 2 else "big"
        if self.flags & 0x10000:
            return struct.unpack(("<" if self.flags & 2 else ">") + {32: "f", 64: "d"}[self.bits], value)[0]
        return int.from_bytes(value, endian, signed=bool(self.flags & 1))

    def raw_bits(self, data, row, col):
        start, size = self.offset(row, col), self.bits // 8
        if start < 0 or start + size > len(data):
            raise ValueError("Cell storage is outside the binary.")
        return int.from_bytes(data[start:start + size], "little" if self.flags & 2 else "big")

    def value(self, data, row, col):
        if self.reason:
            raise ValueError(self.reason)
        return self.equation_for(row, col)(self.raw(data, row, col))

    def encode(self, value, row=0, col=0):
        if self.reason:
            raise ValueError(self.reason)
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("Enter a finite number.")
        if self.minimum is not None and value < self.minimum or self.maximum is not None and value > self.maximum:
            raise ValueError(f"Value must be within XDF limits: {self.minimum} to {self.maximum}.")
        a, b = self.equation_for(row, col).affine()
        raw = (value - b) / a
        if self.flags & 0x10000:
            return struct.pack(("<" if self.flags & 2 else ">") + {32: "f", 64: "d"}[self.bits], raw)
        try:
            return round(raw).to_bytes(self.bits // 8, "little" if self.flags & 2 else "big", signed=bool(self.flags & 1))
        except OverflowError:
            raise ValueError("Value cannot be represented by this cell's storage type.") from None


class Definition:
    def __init__(self, path, root=None):
        self.path = Path(path).resolve()
        self.root = xml_file(path, "XDFFORMAT") if root is None else copy.deepcopy(root)
        self.saved_xml = ET.tostring(self.root)
        self.source_path = self.path
        header = self.root.find("XDFHEADER")
        if header is None:
            raise ValueError("XDF header is missing.")
        self.title = header.findtext("deftitle", self.path.stem)
        defaults = header.find("DEFAULTS")
        default_flags = 0
        if defaults is not None:
            default_flags = (1 if integer(defaults.get("signed")) else 0) | (2 if integer(defaults.get("lsbfirst")) else 0) | (0x10000 if integer(defaults.get("float")) else 0)
        self.default_flags = default_flags
        self.default_bits = integer(defaults.get("datasizeinbits"), 8) if defaults is not None else 8
        base = header.find("BASEOFFSET")
        self.base = integer(base.get("offset")) * (-1 if integer(base.get("subtract")) else 1) if base is not None else 0
        categories = {integer(c.get("index")) + 1: c.get("name", "Uncategorized") for c in header.findall("CATEGORY")}
        self.categories = categories
        self.maps = []
        self.by_id = {}
        for node in self.root:
            if node.tag == "XDFHEADER":
                continue
            memberships = sorted(node.findall("CATEGORYMEM"), key=lambda c: integer(c.get("index")))
            category = next((categories.get(integer(c.get("category")), "Uncategorized") for c in memberships if integer(c.get("category"))), "Uncategorized")
            item = Map(node.get("uniqueid", ""), node.findtext("title", node.tag), category, node.tag, node)
            try:
                if node.tag not in ("XDFTABLE", "XDFCONSTANT"):
                    raise ValueError(f"{node.tag} is preserved for inspection; editing is not implemented yet.")
                axis = node.find("XDFAXIS[@id='z']") if node.tag == "XDFTABLE" else node
                data = axis.find("EMBEDDEDDATA")
                if data is None or "mmedaddress" not in data.attrib:
                    raise ValueError("No embedded binary address.")
                item.address = address_value(data.get("mmedaddress")) + self.base
                item.bits = integer(data.get("mmedelementsizebits"), integer(defaults.get("datasizeinbits"), 8) if defaults is not None else 8)
                item.flags = integer(data.get("mmedtypeflags"), default_flags)
                if item.flags & ~0x10007:
                    raise ValueError(f"Unsupported data flags 0x{item.flags:X}.")
                if item.bits not in (8, 16, 32, 64) or item.flags & 0x10000 and item.bits not in (32, 64):
                    raise ValueError("Unsupported element storage size.")
                item.rows = integer(data.get("mmedrowcount"), 1)
                item.cols = integer(data.get("mmedcolcount"), 1)
                if not (1 <= item.rows * item.cols <= 65536) or min(item.rows, item.cols) < 1:
                    raise ValueError("Invalid map dimensions.")
                major = integer(data.get("mmedmajorstridebits"))
                minor = integer(data.get("mmedminorstridebits"))
                if major % 8 or minor % 8:
                    raise ValueError("Bit-level strides are inspection-only.")
                element = item.bits // 8
                step = major // 8 or element
                gap_setting = minor // 8
                line_count, line_length = (item.cols, item.rows) if item.flags & 4 else (item.rows, item.cols)
                if line_length > 1 and abs(step) < element:
                    raise ValueError("Overlapping storage elements are inspection-only.")
                gap = min(abs(gap_setting), abs(gap_setting - element))
                pitch = (line_length - 1) * abs(step) + element + gap
                position_stride = abs(step) * (-1 if step < 0 else 1)
                line_stride = pitch * (-1 if gap_setting < 0 else 1)
                item.origin_adjust = ((line_length - 1) * abs(step) if step < 0 else 0) + ((line_count - 1) * pitch if gap_setting < 0 else 0)
                item.row_stride, item.col_stride = (position_stride, line_stride) if item.flags & 4 else (line_stride, position_stride)
                item.units = axis.findtext("units", "")
                item.decimals = max(0, min(8, integer(axis.findtext("decimalpl"), 2)))
                item.output_type = integer(axis.findtext("outputtype"), 1)
                if item.output_type not in (0, 1, 2, 3, 4):
                    raise ValueError("Unsupported output type.")
                if item.output_type == 4 and (item.bits != 8 or item.flags & 0x10000):
                    raise ValueError("Text output currently requires 8-bit character storage.")
                maths = axis.findall("MATH")
                scopes = {}
                for equation in maths:
                    for var in equation.findall("VAR"):
                        if var.get("id", "X").upper() != "X" or len(var) or len(var.attrib) > 1:
                            raise ValueError("External equation variables require a compatibility adapter.")
                    row = integer(equation.get("row"), -1)
                    col = integer(equation.get("col"), -1)
                    if row < -1 or col < -1 or row >= item.rows or col >= item.cols:
                        raise ValueError("Equation scope is outside the map dimensions.")
                    scope = (None if row == -1 else row, None if col == -1 else col)
                    if scope in scopes:
                        raise ValueError("Duplicate equation scope.")
                    scopes[scope] = Equation(equation.get("equation", "X"))
                item.equation = scopes.pop((None, None), Equation("X"))
                item.cell_equations = scopes
                for row, col in scopes:
                    if row is not None and col is None:
                        for other_row, other_col in scopes:
                            if other_row is None and other_col is not None and (row, other_col) not in scopes:
                                raise ValueError("Overlapping row/column equations need an explicit cell equation.")
                for key in ("min", "max"):
                    text = axis.findtext(key)
                    if text:
                        setattr(item, "minimum" if key == "min" else "maximum", float(text))
            except (ValueError, SyntaxError, TypeError, AttributeError, ZeroDivisionError) as exc:
                item.reason = str(exc)
            self.maps.append(item)
            self.by_id[item.uid.lower()] = item

    @property
    def dirty(self):
        return ET.tostring(self.root) != self.saved_xml

    def replace_item(self, item, node, binary_size=None):
        root = copy.deepcopy(self.root)
        index = list(self.root).index(item.node)
        root.remove(root[index])
        root.insert(index, copy.deepcopy(node))
        candidate = Definition(self.path, root)
        updated = candidate.maps[self.maps.index(item)]
        if not item.reason and updated.reason:
            raise ValueError(updated.reason)
        if binary_size is not None and not updated.reason:
            start, end = updated.storage_bounds()
            if start < 0 or end > binary_size:
                raise ValueError("The new storage layout is outside the loaded binary.")
            for which in ("x", "y"):
                axis = candidate.internal_axis(updated, which)
                if axis is not None:
                    start, end = axis.storage_bounds()
                    if start < 0 or end > binary_size:
                        raise ValueError("The internal axis storage is outside the loaded binary.")
        candidate.saved_xml = self.saved_xml
        candidate.source_path = self.source_path
        return candidate

    def save_as(self, path):
        target = Path(path).resolve()
        if target == self.source_path:
            raise ValueError("Choose a new XDF filename to preserve the imported definition.")
        self._save(target)

    def save(self):
        self._save(self.path)

    def _save(self, target):
        data = ET.tostring(self.root, encoding="utf-8", xml_declaration=True)
        handle, tmp = tempfile.mkstemp(dir=target.parent, prefix=".gktuner-xdf-")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        self.path = target
        self.saved_xml = ET.tostring(self.root)

    def axis_labels(self, item, which, data):
        count = item.cols if which == "x" else item.rows
        axis = item.node.find(f"XDFAXIS[@id='{which}']")
        if axis is None:
            return [str(i + 1) for i in range(count)]
        labels = {integer(n.get("index")): n.get("value", "") for n in axis.findall("LABEL")}
        output = integer(axis.findtext("outputtype"), 1)
        precision = integer(axis.findtext("decimalpl")) if axis.findtext("decimalpl") is not None else None
        link = axis.find("embedinfo")
        if link is not None and link.get("type") == "3":
            target = self.by_id.get(link.get("linkobjid", "").lower())
            if target is not None and not target.reason and target.rows * target.cols == count:
                try:
                    return [format_number(target.value(data, i // target.cols, i % target.cols), output, precision) for i in range(count)]
                except ValueError:
                    pass
            return [f"#{i + 1}" for i in range(count)]
        if not labels and (link is None or link.get("type") != "0"):
            try:
                target = self.internal_axis(item, which)
                if target:
                    return [format_number(target.value(data, i // target.cols, i % target.cols), output, precision) for i in range(count)]
            except ValueError:
                pass
        # Unresolved embedded axes must not be presented as real physical values.
        return [labels.get(i, f"#{i + 1}") for i in range(count)]

    def internal_axis(self, item, which):
        axis = item.node.find(f"XDFAXIS[@id='{which}']")
        if axis is None:
            return None
        link = axis.find("embedinfo")
        if link is not None and link.get("type") in ("0", "3"):
            return None
        if axis.findall("LABEL"):
            return None
        data = axis.find("EMBEDDEDDATA")
        if data is None or "mmedaddress" not in data.attrib:
            return None
        count = item.cols if which == "x" else item.rows
        step = integer(data.get("mmedmajorstridebits"))
        if step % 8 or integer(data.get("mmedminorstridebits")) < 0:
            raise ValueError("Bit-level axis steps and negative minor axis strides are inspection-only.")
        wrapper = ET.Element("XDFTABLE", uniqueid=item.uid + ":" + which)
        ET.SubElement(wrapper, "title").text = f"{item.title} - {which.upper()} axis"
        z = copy.deepcopy(axis)
        z.set("id", "z")
        embedded = z.find("EMBEDDEDDATA")
        embedded.set("mmedrowcount", "1" if which == "x" else str(count))
        embedded.set("mmedcolcount", str(count) if which == "x" else "1")
        flags = integer(embedded.get("mmedtypeflags"), self.default_flags)
        embedded.set("mmedtypeflags", hex((flags | 4) if which == "y" else (flags & ~4)))
        embedded.set("mmedmajorstridebits", str(step))
        embedded.set("mmedminorstridebits", "0")
        set_output = z.find("outputtype")
        if set_output is not None and set_output.text == "4":
            set_output.text = "1"
        wrapper.append(z)
        root = ET.Element("XDFFORMAT")
        root.append(copy.deepcopy(self.root.find("XDFHEADER")))
        root.append(wrapper)
        target = Definition(self.path, root).maps[0]
        if target.reason:
            raise ValueError(target.reason)
        target.parent_uid, target.axis_which = item.uid.lower(), which
        return target


class BinaryDocument:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.original = self.path.read_bytes()
        if not self.original:
            raise ValueError("Binary is empty.")
        self.data = bytearray(self.original)
        self.saved = bytes(self.data)
        self.undo_stack = []
        self.redo_stack = []

    @property
    def dirty(self):
        return self.data != self.saved

    def fork(self):
        draft = object.__new__(BinaryDocument)
        draft.path = self.path
        draft.original = self.original
        draft.data = bytearray(self.data)
        draft.saved = bytes(self.data)
        draft.undo_stack, draft.redo_stack = [], []
        return draft

    def write_segments(self, segments):
        """Validate expected bytes and all ranges before one undoable write."""
        changes, occupied = [], set()
        for start, expected, replacement in segments:
            expected, replacement = bytes(expected), bytes(replacement)
            if not replacement or len(expected) != len(replacement) or start < 0 or start + len(replacement) > len(self.data):
                raise ValueError("Invalid binary write range or data length.")
            addresses = set(range(start, start + len(replacement)))
            if addresses & occupied:
                raise ValueError("Binary write ranges overlap.")
            occupied.update(addresses)
            current = bytes(self.data[start:start + len(replacement)])
            if current != expected:
                raise ValueError(f"Data at 0x{start:X} changed. Reload or reconcile this edit before saving.")
            if current != replacement:
                changes.append((start, current, replacement))
        if changes:
            self._apply(changes, True)
            self.undo_stack.append(changes)
            self.redo_stack.clear()

    def edit(self, item, cells):
        changes = []
        # Validate the whole operation before mutating any byte.
        occupied = set()
        for row, col, value in cells:
            start = item.offset(row, col)
            item.raw(self.data, row, col)
            after = item.encode(value, row, col)
            addresses = set(range(start, start + len(after)))
            if occupied & addresses:
                raise ValueError("Selected cells overlap in binary storage.")
            occupied.update(addresses)
            before = bytes(self.data[start:start + len(after)])
            if before != after:
                changes.append((start, before, after))
        if changes:
            self._apply(changes, True)
            self.undo_stack.append(changes)
            self.redo_stack.clear()

    def edit_raw(self, item, cells):
        segments = []
        if item.reason:
            raise ValueError(item.reason)
        for row, col, value in cells:
            if not isinstance(value, int) or not 0 <= value < (1 << item.bits):
                raise ValueError(f"Raw value must fit in {item.bits} bits; values do not wrap.")
            start, size = item.offset(row, col), item.bits // 8
            item.raw_bits(self.data, row, col)
            after = value.to_bytes(size, "little" if item.flags & 2 else "big")
            segments.append((start, bytes(self.data[start:start + size]), after))
        self.write_segments(segments)

    def _apply(self, changes, forward):
        for offset, before, after in changes:
            value = after if forward else before
            self.data[offset:offset + len(value)] = value

    def undo(self):
        if self.undo_stack:
            changes = self.undo_stack.pop()
            self._apply(changes, False)
            self.redo_stack.append(changes)

    def redo(self):
        if self.redo_stack:
            changes = self.redo_stack.pop()
            self._apply(changes, True)
            self.undo_stack.append(changes)

    def save_as(self, path):
        target = Path(path).resolve()
        if target == self.path:
            raise ValueError("Choose a new filename to preserve the source binary.")
        handle, tmp = tempfile.mkstemp(dir=target.parent, prefix=".gktuner-")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(self.data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        self.saved = bytes(self.data)


@dataclass
class ADXDefinition:
    path: Path
    title: str
    baud: int
    channels: list = field(default_factory=list)
    commands: list = field(default_factory=list)

    @classmethod
    def load(cls, path):
        root = xml_file(path, "ADXFORMAT")
        header = root.find("ADXHEADER")
        if header is None:
            raise ValueError("ADX header is missing.")
        result = cls(Path(path).resolve(), header.findtext("desc", Path(path).stem), integer(header.findtext("baud"), 10400))
        for node in root.findall("ADXVALUE"):
            result.channels.append({"name": node.get("title", node.get("id", "")), "id": node.get("id", ""),
                                    "offset": node.findtext("packetoffset", "0"), "bits": node.findtext("sizeinbits", "8"),
                                    "equation": node.find("MATH").get("equation", "X") if node.find("MATH") is not None else "X",
                                    "parent": node.findtext("parentcmdidhash", "default")})
        result.commands = [ET.tostring(n, encoding="unicode") for n in root if n.tag.startswith("ADXC") or n.tag == "ADXMACRO"]
        return result
