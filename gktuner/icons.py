"""Small vector-drawn icons keep item types distinct in both themes."""
from PyQt5 import QtCore as C, QtGui as G

TYPES = {"XDFCONSTANT": ("Constant", "constant", "#2867bd"), "XDFTABLE": ("Table", "table", "#087b82"),
         "XDFFUNCTION": ("Function", "function", "#8b42b9"), "XDFPATCH": ("Patch", "patch", "#bd6512"),
         "XDFFLAG": ("Flag / switch", "switch", "#278046"), "XDFSWITCH": ("Flag / switch", "switch", "#278046")}


def item_type(kind):
    return TYPES.get(kind, ("Other item", "other", "#60758b"))[0]


def item_icon(kind):
    _, shape, color = TYPES.get(kind, ("Other item", "other", "#60758b"))
    pixmap = G.QPixmap(24, 24)
    pixmap.fill(C.Qt.transparent)
    painter = G.QPainter(pixmap)
    painter.setRenderHint(G.QPainter.Antialiasing)
    painter.setPen(G.QPen(G.QColor(color), 2))
    painter.setBrush(G.QColor("#ffffff"))
    if shape == "table":
        painter.drawRoundedRect(C.QRectF(3, 3, 18, 18), 2, 2)
        for offset in (9, 15):
            painter.drawLine(offset, 3, offset, 21)
            painter.drawLine(3, offset, 21, offset)
    elif shape == "constant":
        painter.drawRoundedRect(C.QRectF(3, 3, 18, 18), 4, 4)
        painter.setFont(G.QFont("Segoe UI", 12, G.QFont.Bold))
        painter.drawText(C.QRect(3, 1, 18, 21), C.Qt.AlignCenter, "1")
    elif shape == "function":
        painter.drawLine(3, 20, 21, 20)
        painter.drawLine(3, 20, 3, 3)
        path = G.QPainterPath(C.QPointF(5, 17))
        path.cubicTo(12, 17, 9, 5, 21, 5)
        painter.drawPath(path)
    elif shape == "patch":
        painter.setBrush(G.QColor("#ffe2ad"))
        painter.drawPolygon(G.QPolygonF([C.QPointF(13, 2), C.QPointF(5, 13), C.QPointF(11, 13), C.QPointF(10, 22), C.QPointF(20, 9), C.QPointF(14, 9)]))
    elif shape == "switch":
        painter.setBrush(G.QColor("#d1efdc"))
        painter.drawRoundedRect(C.QRectF(2, 6, 20, 12), 6, 6)
        painter.setBrush(G.QColor(color))
        painter.drawEllipse(C.QRectF(12, 8, 8, 8))
    else:
        painter.drawRoundedRect(C.QRectF(4, 2, 16, 20), 2, 2)
        painter.drawLine(8, 8, 16, 8)
        painter.drawLine(8, 13, 16, 13)
    painter.end()
    return G.QIcon(pixmap)


def tool_icon(name):
    pixmap = G.QPixmap(24, 24)
    pixmap.fill(C.Qt.transparent)
    p = G.QPainter(pixmap)
    p.setRenderHint(G.QPainter.Antialiasing)
    p.setPen(G.QPen(G.QColor("#167087"), 1.8))
    if name == 'checksum':
        p.setBrush(G.QColor('#e0edf4'))
        p.drawRoundedRect(C.QRectF(3, 2, 16, 20), 2, 2)
        p.drawLine(7, 6, 15, 6)
        p.drawLine(7, 10, 13, 10)
        p.setPen(G.QPen(G.QColor('#288552'), 2.8, C.Qt.SolidLine, C.Qt.RoundCap, C.Qt.RoundJoin))
        p.drawPolyline(G.QPolygonF([C.QPointF(8, 16), C.QPointF(12, 20), C.QPointF(21, 11)]))
    elif name == "hex":
        p.setBrush(G.QColor("#e0e9f4"))
        p.drawRoundedRect(C.QRectF(1, 3, 22, 18), 2, 2)
        font = G.QFont("Segoe UI")
        font.setPixelSize(10)
        font.setBold(True)
        p.setFont(font)
        p.drawText(C.QRect(2, 3, 20, 18), C.Qt.AlignCenter, "0x")
    elif name in ("load_bin", "load_xdf", "save_bin", "save_xdf"):
        definition = name.endswith("xdf")
        color = G.QColor("#7651ab" if definition else "#167087")
        p.setPen(G.QPen(color, 1.3))
        p.setBrush(G.QColor("#ede1fa" if definition else "#d1edf1"))
        if name.startswith("load"):
            p.drawRoundedRect(C.QRectF(1.5, 5, 21, 17), 2, 2)
            p.drawRect(C.QRectF(3, 2, 8, 5))
        else:
            p.drawRoundedRect(C.QRectF(2, 2, 20, 20), 2, 2)
            p.setBrush(G.QColor("#ffffff"))
            p.drawRect(C.QRectF(6, 2, 12, 6))
        font = G.QFont("Segoe UI")
        font.setPixelSize(8)
        font.setBold(True)
        p.setFont(font)
        p.drawText(C.QRect(4, 10, 16, 10), C.Qt.AlignCenter, "DEF" if definition else "010")
    elif name in ("undo", "redo"):
        p.setPen(G.QPen(G.QColor("#397baf"), 2.2, C.Qt.SolidLine, C.Qt.RoundCap, C.Qt.RoundJoin))
        if name == "redo":
            p.translate(24, 0)
            p.scale(-1, 1)
        path = G.QPainterPath(C.QPointF(20, 20))
        path.cubicTo(22, 8, 14, 6, 5, 8)
        p.drawPath(path)
        p.drawPolyline(G.QPolygonF([C.QPointF(9, 3), C.QPointF(4, 8), C.QPointF(10, 12)]))
    elif name in ("x", "y"):
        p.setPen(G.QColor("#2163af" if name == "x" else "#af356b"))
        font = G.QFont("Segoe UI")
        font.setPixelSize(19)
        font.setBold(True)
        p.setFont(font)
        p.drawText(C.QRect(0, 0, 24, 24), C.Qt.AlignCenter, name.upper())
    elif name == "graph":
        points = [[C.QPointF(3 + c * 4 + r * 2, 16 - r * 3 - (3 if c == 2 else 0)) for c in range(4)] for r in range(4)]
        for row in points:
            p.drawPolyline(G.QPolygonF(row))
        for col in range(4):
            p.drawPolyline(G.QPolygonF([row[col] for row in points]))
        p.drawLine(3, 20, 21, 20)
    elif name == "compare":
        # Matching documents with highlighted differing rows.
        p.setPen(G.QPen(G.QColor("#537b99"), 1.4))
        for x, color, row in ((2, "#087f8c", 9), (14, "#8651b5", 14)):
            p.setBrush(G.QColor("#f3f6fb"))
            p.drawRoundedRect(C.QRectF(x, 3, 8, 18), 1.2, 1.2)
            p.setPen(G.QPen(G.QColor("#8498ab"), 1.2))
            for y in (7, 11, 16):
                p.drawLine(x + 2, y, x + 6, y)
            p.setPen(G.QPen(G.QColor(color), 2.4))
            p.drawLine(x + 2, row, x + 6, row)
            p.setPen(G.QPen(G.QColor("#537b99"), 1.4))
    elif name == "menu":
        for y in (6, 12, 18):
            p.drawLine(3, y, 21, y)
    elif name in ("tile", "side", "cascade", "fit", "browser"):
        if name == "tile":
            for x, y in ((3, 3), (13, 3), (3, 13), (13, 13)):
                p.drawRect(x, y, 8, 8)
        elif name == "side":
            p.drawRect(3, 3, 8, 18)
            p.drawRect(13, 3, 8, 18)
        elif name == "cascade":
            for offset in (2, 6, 10):
                p.setBrush(G.QColor("#e3edf5"))
                p.drawRect(offset, offset, 12, 12)
        elif name == "browser":
            p.drawRect(2, 3, 20, 18)
            p.drawLine(8, 3, 8, 21)
            for y in (8, 12, 16):
                p.drawLine(11, y, 19, y)
        else:
            for x, y, dx, dy in ((3, 3, 6, 6), (21, 3, -6, 6), (3, 21, 6, -6), (21, 21, -6, -6)):
                p.drawLine(x, y, x + dx, y)
                p.drawLine(x, y, x, y + dy)
    else:
        p.drawEllipse(4, 4, 16, 16)
    p.end()
    return G.QIcon(pixmap)
