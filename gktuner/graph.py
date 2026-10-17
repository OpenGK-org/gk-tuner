"""Theme-aware surface rendering and transactional point dragging."""
import math
from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W
from .appearance import heatmap_color
from .core import integer
from .icons import tool_icon


def axis_caption(definition, item, which):
    axis = item.node.find(f"XDFAXIS[@id='{which}']")
    if axis is None:
        return f"{which.upper()} axis"
    name = axis.findtext("title") or {6: "Engine speed", 23: "Load"}.get(integer(axis.findtext("datatype")), f"{which.upper()} axis")
    units = axis.findtext("units", "")
    link = axis.find("embedinfo")
    if not units and link is not None:
        target = definition.by_id.get(link.get("linkobjid", "").lower())
        units = target.units if target else ""
    return f"{name} ({units})" if units else name


class SurfacePlot(W.QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.values = []
        self.x_labels, self.y_labels = [], []
        self.x_title, self.y_title, self.z_title = "X axis", "Y axis", "Value"
        self.mode = "Heatmap + mesh"
        self.selected = set()
        self.yaw, self.pitch, self.zoom = -.65, .65, 1.
        self.points = {}
        self.drag = None
        self.rotation = None
        self.preview = None
        self.setMinimumSize(480, 360)
        self.setMouseTracking(True)
        self.setFocusPolicy(C.Qt.StrongFocus)
        self.hide()

    def domain(self):
        flat = [v for row in self.values for v in row if v is not None and math.isfinite(v)]
        if not flat:
            return 0., 1.
        low, high = min(flat), max(flat)
        if high == low:
            try:
                step = abs(self.editor.item.equation.affine()[0])
            except (AttributeError, ValueError):
                step = .05
            padding = max(.5, step * 10)
            return low - padding, high + padding
        return low, high

    def colors(self):
        palette = self.editor.owner.active_palette
        return tuple(G.QColor(palette[role]) for role in ('background', 'text', 'border'))

    def projection(self, low, high):
        cy, sy, cp, sp = math.cos(self.yaw), math.sin(self.yaw), math.cos(self.pitch), math.sin(self.pitch)
        def raw(x, y, z):
            return x * cy - y * sy, (x * sy + y * cy) * sp - z * cp, (x * sy + y * cy) * cp + z * sp
        corners = [raw(x, y, z) for x in (-.5, .5) for y in (-.5, .5) for z in (0., .8)]
        xs, ys = [p[0] for p in corners], [p[1] for p in corners]
        cx, cy0 = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        scale = min(max(1, self.width() - 260) / (max(xs) - min(xs)), max(1, self.height() - 160) / (max(ys) - min(ys))) * self.zoom
        def point(x, y, z):
            px, py, depth = raw(x, y, z)
            return C.QPointF(self.width() / 2 - 25 + (px - cx) * scale,
                            self.height() / 2 + (py - cy0) * scale), depth
        self.vertical_pixels = max(1, .8 * math.cos(self.pitch) * scale)
        return point

    def paintEvent(self, event):
        p = G.QPainter(self)
        p.setRenderHint(G.QPainter.Antialiasing)
        background, text, grid = self.colors()
        p.fillRect(self.rect(), background)
        self.points = {}
        p.setPen(text)
        if not self.values or not any(v is not None for row in self.values for v in row):
            p.drawText(self.rect(), C.Qt.AlignCenter, "No graph data available")
            return
        low, high = self.drag['domain'] if self.drag else self.domain()
        span = high - low
        project = self.projection(low, high)
        rows, cols = len(self.values), len(self.values[0])
        values = self.preview if self.preview is not None else self.values
        def at(row, col, value):
            return project(col / max(1, cols - 1) - .5, row / max(1, rows - 1) - .5, .8 * (value - low) / span)
        p.setPen(G.QPen(grid, 1, C.Qt.DashLine))
        for i in range(6):
            t = i / 5 - .5
            p.drawLine(project(t, -.5, 0)[0], project(t, .5, 0)[0])
            p.drawLine(project(-.5, t, 0)[0], project(.5, t, 0)[0])
        faces = []
        for r in range(rows):
            for c in range(cols):
                if values[r][c] is not None:
                    self.points[r, c] = at(r, c, values[r][c])[0]
                if r + 1 >= rows or c + 1 >= cols:
                    continue
                cells = ((r, c), (r, c + 1), (r + 1, c + 1), (r + 1, c))
                if any(values[y][x] is None for y, x in cells):
                    continue
                vertices = [at(y, x, values[y][x]) for y, x in cells]
                average = sum(values[y][x] for y, x in cells) / 4
                faces.append((sum(v[1] for v in vertices) / 4, [v[0] for v in vertices], average))
        comparing = self.editor.compare_active and self.editor.owner.compare is not None
        for _, vertices, value in sorted(faces, key=lambda f: f[0]):
            color = heatmap_color(value, low, high, comparing, self.editor.compare_mode, self.editor.owner.active_palette)
            if self.mode == "Wireframe":
                p.setBrush(C.Qt.NoBrush)
                p.setPen(G.QPen(text, 1.2))
            else:
                p.setBrush(color)
                p.setPen(G.QPen(text if self.mode == "Heatmap + mesh" else color, .8))
            p.drawPolygon(G.QPolygonF(vertices))
        # Functions represented as a one-row/column table still have a visible curve.
        if rows == 1 or cols == 1:
            keys = sorted(self.points)
            p.setPen(G.QPen(text, 2))
            for a, b in zip(keys, keys[1:]):
                p.drawLine(self.points[a], self.points[b])
        self.draw_axes(p, project, low, high, text, grid)
        for key, point in self.points.items():
            if key in self.selected:
                p.setPen(G.QPen(G.QColor("#162c42"), 2))
                p.setBrush(G.QColor(self.editor.owner.active_palette['graph_point']))
                p.drawEllipse(point, 5, 5)
        p.setPen(text)
        status = f"{len(self.selected)} selected points"
        if self.drag:
            status += f" - {self.drag.get('delta', 0):+.5g} {self.editor.item.units} (preview)" if self.drag['valid'] else " - Outside limits: release cancels"
        elif comparing:
            status += " - comparison is read only"
        p.drawText(15, 24, status)
        p.drawText(15, self.height() - 16, "Drag a selected point to raise/lower - Drag empty space to rotate - Wheel to zoom - Esc cancels")

    def draw_axes(self, p, project, low, high, text, grid):
        p.setPen(G.QPen(text, 1.2))
        base = project(-.5, -.5, 0)[0]
        for endpoint in ((.5, -.5, 0), (-.5, .5, 0), (-.5, -.5, .8)):
            p.drawLine(base, project(*endpoint)[0])
        p.drawLine(project(-.5, .5, 0)[0], project(.5, .5, 0)[0])
        def labels(values):
            return sorted(set(round(i * (len(values) - 1) / min(5, max(1, len(values) - 1))) for i in range(min(6, len(values))))) if values else []
        for index in labels(self.x_labels):
            point = project(index / max(1, len(self.x_labels) - 1) - .5, .5, 0)[0]
            p.drawText(C.QRectF(point.x() - 28, point.y() + 5, 56, 20), C.Qt.AlignCenter, self.x_labels[index])
        for index in labels(self.y_labels):
            point = project(-.5, index / max(1, len(self.y_labels) - 1) - .5, 0)[0]
            p.drawText(C.QRectF(point.x() - 64, point.y() - 9, 56, 20), C.Qt.AlignRight, self.y_labels[index])
        for i in range(1, 5):
            point = project(-.5, -.5, .8 * i / 4)[0]
            p.drawText(C.QRectF(point.x() - 72, point.y() - 11, 64, 20), C.Qt.AlignRight, f"{low + (high - low) * i / 4:.4g}")
        for title, position in (("X: " + self.x_title, project(.2, .5, 0)[0] + C.QPointF(0, 34)),
                                ("Y: " + self.y_title, project(-.5, .5, 0)[0] + C.QPointF(-55, 28)),
                                ("Z: " + self.z_title, project(-.5, -.5, .8)[0] + C.QPointF(-65, -26))):
            p.drawText(C.QRectF(position.x() - 65, position.y(), 220, 24), title)
        comparing = self.editor.compare_active and self.editor.owner.compare is not None
        for i in range(120):
            value = high - (high - low) * i / 119
            p.fillRect(C.QRect(self.width() - 90, 70 + i, 14, 1), heatmap_color(value, low, high, comparing, self.editor.compare_mode, self.editor.owner.active_palette))
        p.setPen(text)
        p.drawText(self.width() - 70, 79, f"{high:.4g}")
        p.drawText(self.width() - 70, 190, f"{low:.4g}")

    def hit_point(self, position):
        candidates = [(math.hypot(point.x() - position.x(), point.y() - position.y()), key) for key, point in self.points.items()]
        nearby = [(distance, key) for distance, key in candidates if distance <= 11]
        if not nearby:
            return None
        selected = [(distance, key) for distance, key in nearby if key in self.selected]
        return min(selected or nearby)[1]

    def mousePressEvent(self, event):
        if event.button() not in (C.Qt.LeftButton, C.Qt.RightButton):
            return
        self.setFocus()
        key = self.hit_point(event.pos()) if event.button() == C.Qt.LeftButton else None
        if key is None:
            self.rotation = event.pos()
            return
        if event.modifiers() & C.Qt.ControlModifier:
            cell = self.editor.table.item(*key)
            cell.setSelected(not cell.isSelected())
            return
        if key not in self.selected:
            self.editor.table.clearSelection()
            self.editor.table.item(*key).setSelected(True)
        self.begin_drag(event.pos())

    def begin_drag(self, position):
        owner, item = self.editor.owner, self.editor.item
        if self.editor.compare_active or self.editor.buffer is None or not self.selected:
            return False
        try:
            if not self.editor.raw_view:
                for row, col in self.selected:
                    item.equation_for(row, col).affine()
            self.drag = {"position": C.QPoint(position), "domain": self.domain(), "document": self.editor.buffer,
                         "item": item, "data": bytes(self.editor.buffer.data), "selection": set(self.selected), "valid": True}
            self.preview = [list(row) for row in self.values]
            self.setCursor(C.Qt.SizeVerCursor)
            return True
        except ValueError:
            self.setToolTip("The selected points use a view-only conversion.")
            return False

    def mouseMoveEvent(self, event):
        if self.drag:
            low, high = self.drag['domain']
            delta = (self.drag['position'].y() - event.pos().y()) * (high - low) / max(1, getattr(self, 'vertical_pixels', 250))
            self.drag['delta'] = delta
            candidate = [list(row) for row in self.values]
            try:
                for r, c in self.drag['selection']:
                    candidate[r][c] = self.values[r][c] + (round(delta) if self.editor.raw_view else delta)
                    if self.editor.raw_view:
                        if not 0 <= candidate[r][c] < (1 << self.editor.item.bits):
                            raise ValueError("Raw storage limit")
                    else:
                        self.editor.item.encode(candidate[r][c], r, c)
                self.preview = candidate
                self.drag['valid'] = True
                self.setToolTip(f"Adjustment: {delta:+.5g} {self.editor.item.units}")
            except (ValueError, OverflowError):
                self.drag['valid'] = False
                self.setToolTip("Outside storage or XDF limits. Release cancels this adjustment.")
            self.update()
        elif self.rotation is not None:
            delta = event.pos() - self.rotation
            self.yaw += delta.x() * .01
            self.pitch = max(.15, min(1.35, self.pitch + delta.y() * .01))
            self.rotation = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.drag:
            drag, preview = self.drag, self.preview
            self.cancel_drag()
            owner = self.editor.owner
            if drag['valid'] and self.editor.buffer is drag['document'] and self.editor.item is drag['item'] and bytes(self.editor.buffer.data) == drag['data'] and not self.editor.compare_active:
                try:
                    edit = self.editor.buffer.edit_raw if self.editor.raw_view else self.editor.buffer.edit
                    edit(self.editor.item, [(r, c, preview[r][c]) for r, c in sorted(drag['selection'])])
                    owner.refresh_map()
                except Exception as exc:
                    owner.error(exc)
        self.rotation = None

    def cancel_drag(self):
        self.drag = self.preview = None
        self.unsetCursor()
        self.update()

    def keyPressEvent(self, event):
        if event.key() == C.Qt.Key_Escape:
            self.cancel_drag()
            self.rotation = None
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        if not self.drag:
            self.zoom = max(.5, min(2., self.zoom * (1.12 if event.angleDelta().y() > 0 else 1 / 1.12)))
            self.update()


class GraphWindow(W.QMainWindow):
    def __init__(self, editor):
        super().__init__(editor.owner, C.Qt.Window)
        self.editor = editor
        self.resize(960, 740)
        self.setCentralWidget(editor.surface)
        editor.surface.show()
        bar = self.addToolBar("Graph view")
        bar.setMovable(False)
        bar.addAction(tool_icon("graph"), "Reset view", self.reset_view)
        self.mode = W.QComboBox()
        self.mode.addItems(["Heatmap + mesh", "Filled heatmap", "Wireframe"])
        self.mode.currentTextChanged.connect(self.set_mode)
        bar.addWidget(self.mode)
        undo = bar.addAction(tool_icon("undo"), "Undo", editor.owner.undo)
        undo.setShortcut("Ctrl+Z")
        redo = bar.addAction(tool_icon("redo"), "Redo", editor.owner.redo)
        redo.setShortcut("Ctrl+Y")
        self.axes = W.QLabel()
        bar.addWidget(self.axes)
        self.sync()

    def set_mode(self, mode):
        self.editor.surface.mode = mode
        self.editor.surface.update()

    def reset_view(self):
        surface = self.editor.surface
        surface.yaw, surface.pitch, surface.zoom = -.65, .65, 1.
        surface.update()

    def sync(self):
        e, owner = self.editor, self.editor.owner
        surface = e.surface
        surface.cancel_drag()
        surface.selected = {(i.row(), i.column()) for i in e.table.selectedIndexes()}
        if e.item is None or owner.definition is None:
            return
        item = e.item
        surface.x_title = axis_caption(owner.definition, item, "x")
        surface.y_title = axis_caption(owner.definition, item, "y")
        surface.x_labels = [e.table.horizontalHeaderItem(i).text() for i in range(e.table.columnCount())]
        surface.y_labels = [e.table.verticalHeaderItem(i).text() for i in range(e.table.rowCount())]
        surface.z_title = ("Change (%)" if e.compare_active and e.compare_mode == "Percentage" else ("Difference " if e.compare_active and e.compare_mode == "Difference" else "Value ") + (f"({item.units})" if item.units else ""))
        if e.raw_view:
            surface.z_title = "Raw storage (no conversion)"
        comparison = f" - COMPARE {e.compare_mode}: {owner.compare_name} - Read only" if e.compare_active else ""
        self.setWindowTitle(f"3D - {item.title}{comparison}")
        self.axes.setText(f"   X: {surface.x_title}   -   Y: {surface.y_title}   -   Z: {surface.z_title}")
        surface.update()

    def closeEvent(self, event):
        self.editor.surface.cancel_drag()
        self.editor.graph_action.setChecked(False)
        event.accept()
