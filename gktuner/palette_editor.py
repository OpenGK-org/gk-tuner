"""User-editable theme colours with live heatmap previews."""
from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W
from .appearance import palette_for, contrast_text, heatmap_color


class GradientPreview(W.QWidget):
    def __init__(self, owner, comparing=False):
        super().__init__()
        self.owner, self.comparing = owner, comparing
        self.setMinimumHeight(30)

    def paintEvent(self, event):
        p = G.QPainter(self)
        palette = self.owner.selected_palette()
        for x in range(self.width()):
            p.fillRect(x, 0, 1, self.height(), heatmap_color(x / max(1, self.width()-1), 0, 1, self.comparing, palette=palette))


class PaletteEditor(W.QGroupBox):
    def __init__(self, owner):
        super().__init__('Colours')
        self.owner, self.dialog = owner, None
        self.colour_buttons = {}
        layout = W.QVBoxLayout(self)
        layout.addWidget(W.QLabel('Working heatmap'))
        self.working = GradientPreview(self)
        layout.addWidget(self.working)
        layout.addWidget(W.QLabel('Comparison heatmap'))
        self.comparison = GradientPreview(self, True)
        layout.addWidget(self.comparison)
        row = W.QHBoxLayout()
        edit = W.QPushButton('Edit palette…')
        edit.clicked.connect(self.open_dialog)
        reset = W.QPushButton('Reset this theme')
        reset.clicked.connect(self.reset)
        row.addWidget(edit)
        row.addWidget(reset)
        row.addStretch()
        layout.addLayout(row)
        owner.theme_choice.currentTextChanged.connect(self.refresh)

    def selected_palette(self):
        theme = self.owner.theme_choice.currentText()
        return palette_for(theme, self.owner.palette_overrides.get(theme))

    def set_colour(self, role, value):
        color = G.QColor(value)
        if not color.isValid():
            return
        theme = self.owner.theme_choice.currentText()
        self.owner.palette_overrides.setdefault(theme, {})[role] = color.name()
        self.owner.apply_appearance(persist=True)

    def choose_colour(self, role, title):
        color = W.QColorDialog.getColor(G.QColor(self.selected_palette()[role]), self.dialog, title, W.QColorDialog.DontUseNativeDialog)
        if color.isValid():
            self.set_colour(role, color)

    def reset(self):
        self.owner.palette_overrides[self.owner.theme_choice.currentText()] = {}
        self.owner.apply_appearance(persist=True)

    def refresh(self, *args):
        self.working.update()
        self.comparison.update()
        if self.dialog:
            for preview in self.dialog.findChildren(GradientPreview):
                preview.update()
        palette = self.selected_palette()
        for role, button in self.colour_buttons.items():
            value = palette[role]
            button.setText(value.upper())
            button.setStyleSheet(f'background: {value}; color: {contrast_text(value).name()}; padding: 7px 12px;')
        if self.dialog:
            self.dialog.setWindowTitle(self.owner.theme_choice.currentText() + ' palette')

    def open_dialog(self):
        if self.dialog is None:
            self.dialog = W.QDialog(self.owner)
            scale = self.owner.appearance_scale
            self.dialog.resize(round(520 * scale), round(610 * scale))
            layout = W.QVBoxLayout(self.dialog)
            tabs = W.QTabWidget()
            layout.addWidget(tabs)
            groups = [
                ('Interface', [('background', 'Page background'), ('surface', 'Fields and panels'), ('text', 'Text'),
                               ('muted', 'Secondary text'), ('accent', 'Primary buttons'), ('hover', 'Button hover'),
                               ('selection', 'Selection'), ('border', 'Borders'), ('workspace', 'Map workspace'),
                               ('changed', 'Changed items'), ('graph_point', 'Selected 3D points')]),
                ('Working heatmap', [('heat_low', 'Low'), ('heat_mid', 'Middle'), ('heat_high', 'High'), ('heat_invalid', 'Unavailable values')]),
                ('Comparison heatmap', [('compare_low', 'Low / negative'), ('compare_mid', 'Middle / zero'), ('compare_high', 'High / positive')]),
            ]
            for title, roles in groups:
                page = W.QWidget()
                form = W.QFormLayout(page)
                form.setFieldGrowthPolicy(W.QFormLayout.FieldsStayAtSizeHint)
                for role, caption in roles:
                    button = W.QPushButton()
                    button.setMinimumWidth(130)
                    button.clicked.connect(lambda checked=False, role=role, caption=caption: self.choose_colour(role, caption))
                    self.colour_buttons[role] = button
                    form.addRow(caption, button)
                if title != 'Interface':
                    form.addRow(GradientPreview(self, title.startswith('Comparison')))
                scroll = W.QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setWidget(page)
                tabs.addTab(scroll, title)
            buttons = W.QDialogButtonBox(W.QDialogButtonBox.Close | W.QDialogButtonBox.RestoreDefaults)
            buttons.rejected.connect(self.dialog.hide)
            buttons.button(W.QDialogButtonBox.RestoreDefaults).clicked.connect(self.reset)
            layout.addWidget(buttons)
        self.refresh()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
