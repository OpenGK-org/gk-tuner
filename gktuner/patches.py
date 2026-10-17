"""Overwrite patch definitions with expected-byte checks and atomic writes."""
from dataclasses import dataclass
from .core import integer, address_value


@dataclass
class PatchEntry:
    name: str
    address: int
    data: bytes
    base: bytes | None


class PatchPlan:
    def __init__(self, node, base_offset=0):
        self.entries = []
        occupied = set()
        for entry in node.findall("XDFPATCHENTRY"):
            if any(entry.get(key, "overwrite").lower() not in ("overwrite", "0", "0x0") for key in ("operation", "op", "type")):
                raise ValueError("Only overwrite patch entries are supported.")
            if "address" not in entry.attrib:
                raise ValueError("Patch entry is missing its address.")
            address = address_value(entry.get("address")) + base_offset
            data = bytes.fromhex(entry.get("patchdata", ""))
            base_text = entry.get("basedata", "").strip()
            base = bytes.fromhex(base_text) if base_text else None
            if not data or integer(entry.get("datasize"), len(data)) != len(data) or base is not None and len(base) != len(data):
                raise ValueError("Patch data, base data and declared size must have matching lengths.")
            addresses = set(range(address, address + len(data)))
            if address < 0 or occupied & addresses:
                raise ValueError("Patch entries overlap or have invalid addresses.")
            occupied.update(addresses)
            self.entries.append(PatchEntry(entry.get("name", "Entry"), address, data, base))
        if not self.entries:
            raise ValueError("Add at least one patch entry.")

    def entry_states(self, data):
        states = []
        for entry in self.entries:
            if entry.address + len(entry.data) > len(data):
                raise ValueError(f"{entry.name}: address is outside the BIN.")
            current = bytes(data[entry.address:entry.address + len(entry.data)])
            states.append("Applied" if current == entry.data else "Base matches" if entry.base is not None and current == entry.base else "Unverified: no base data" if entry.base is None else "Mismatch")
        return states

    def state(self, data):
        states = self.entry_states(data)
        if all(s == "Applied" for s in states):
            return "Applied"
        if "Mismatch" in states:
            return "Unsafe: data does not match expected base or patch"
        if any(s.startswith("Unverified") for s in states):
            return "Unverified: base data missing"
        return "Not applied: base matches" if all(s == "Base matches" for s in states) else "Partially applied: remaining base data matches"

    def mismatches(self, data):
        """Only byte positions differing from supplied base data, including applied bytes."""
        self.entry_states(data)
        return [(entry.name, entry.address + index, base, data[entry.address + index], entry.data[index])
                for entry in self.entries if entry.base is not None
                for index, base in enumerate(entry.base) if data[entry.address + index] != base]

    def apply(self, document, remove=False, allow_unverified=False, force=False):
        states = self.entry_states(document.data)
        segments = []
        for entry, state in zip(self.entries, states):
            if state == "Mismatch" and (not force or remove):
                raise ValueError(f"{entry.name}: BIN does not match expected base or patch data. Nothing changed.")
            if remove and entry.base is None:
                raise ValueError("Cannot remove a patch without its original base data.")
            if state.startswith("Unverified") and not allow_unverified:
                raise ValueError("Base data is missing; explicit unverified application is required.")
            current = bytes(document.data[entry.address:entry.address + len(entry.data)])
            target = entry.base if remove else entry.data
            segments.append((entry.address, current, target))
        document.write_segments(segments)


def map_entries(item, before, after, base_offset=0):
    """Capture map cells, grouping contiguous bytes while preserving stride gaps."""
    addresses = sorted({offset for r in range(item.rows) for c in range(item.cols)
                        for offset in range(item.offset(r, c), item.offset(r, c) + item.bits // 8)})
    if not addresses or addresses[0] < 0 or addresses[-1] >= len(before) or len(before) != len(after):
        raise ValueError("Map is outside the BIN.")
    if all(before[i] == after[i] for i in addresses):
        raise ValueError("Change at least one map value before creating a patch entry.")
    import xml.etree.ElementTree as ET
    runs, start, last = [], addresses[0], addresses[0]
    for address in addresses[1:] + [addresses[-1] + 2]:
        if address != last + 1:
            runs.append((start, last + 1))
            start = address
        last = address
    return [ET.Element("XDFPATCHENTRY", name=item.title + (f" ({i + 1})" if len(runs) > 1 else ""),
                       address=hex(start - base_offset), datasize=hex(end - start),
                       patchdata=bytes(after[start:end]).hex().upper(), basedata=bytes(before[start:end]).hex().upper())
            for i, (start, end) in enumerate(runs)]
