"""Synthetic data only; never a calibration for a real ECU."""
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, indent, tostring


def create_demo(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    root = Element("XDFFORMAT", version="1.80")
    header = SubElement(root, "XDFHEADER")
    SubElement(header, "deftitle").text = "GK Tuner - Synthetic demonstration"
    SubElement(header, "BASEOFFSET", offset="0", subtract="0")
    for index, name in enumerate(("Ignition", "Fuel", "Engine speed")):
        SubElement(header, "CATEGORY", index=str(index), name=name)
    binary = bytearray(1024)
    specs = [("Base ignition advance - DEMO", 0, 8, 12, "° BTDC", "X*0.25-32", 1),
             ("Target lambda - DEMO", 192, 8, 12, "λ", "X/10000", 2),
             ("Engine speed limit - DEMO", 384, 1, 1, "rpm", "X", 3)]
    rpm = [800, 1200, 1600, 2000, 2500, 3000, 3500, 4000, 4500, 5000, 6000, 7000]
    load = [20, 30, 40, 50, 65, 80, 95, 110]
    for uid, (title, address, rows, cols, units, equation, category) in enumerate(specs, 1):
        table = SubElement(root, "XDFTABLE", uniqueid=hex(uid))
        SubElement(table, "title").text = title
        SubElement(table, "description").text = "Synthetic demonstration. Not for flashing to an ECU."
        SubElement(table, "CATEGORYMEM", category=str(category))
        for which, labels in (("x", rpm[:cols]), ("y", load[:rows])):
            axis = SubElement(table, "XDFAXIS", id=which)
            for i, value in enumerate(labels):
                SubElement(axis, "LABEL", index=str(i), value=str(value))
        axis = SubElement(table, "XDFAXIS", id="z")
        SubElement(axis, "EMBEDDEDDATA", mmedaddress=hex(address), mmedelementsizebits="16", mmedtypeflags="0x02", mmedrowcount=str(rows), mmedcolcount=str(cols))
        SubElement(axis, "units").text = units
        SubElement(axis, "decimalpl").text = "2"
        SubElement(axis, "min").text = "-32" if uid == 1 else "0"
        SubElement(axis, "max").text = "80" if uid == 1 else "2" if uid == 2 else "10000"
        SubElement(SubElement(axis, "MATH", equation=equation), "VAR", id="X")
        for r in range(rows):
            for c in range(cols):
                raw = round((9 + c * 2.2 - r * 1.4 + 32) * 4) if uid == 1 else round((1 - r * .02) * 10000) if uid == 2 else 6800
                offset = address + (r * cols + c) * 2
                binary[offset:offset + 2] = raw.to_bytes(2, "little")
    indent(root)
    xdf_path, bin_path = folder / "demonstration.xdf", folder / "demonstration.bin"
    # Reopening the demo preserves any file the user might already have edited.
    if not xdf_path.exists():
        xdf_path.write_bytes(tostring(root, encoding="utf-8", xml_declaration=True))
    if not bin_path.exists():
        bin_path.write_bytes(binary)
    return bin_path, xdf_path
