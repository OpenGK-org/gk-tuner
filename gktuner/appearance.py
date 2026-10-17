"""Application themes and scalable, high-contrast item heatmaps."""
import re
import json
from PyQt5 import QtGui as G


DEFAULT_PALETTES = {
    'Light': {'background': '#eef2f6', 'surface': '#ffffff', 'text': '#17263c', 'muted': '#4c6077',
              'accent': '#126b75', 'selection': '#215f95', 'border': '#acbdcf', 'workspace': '#b9c7d4',
              'hover': '#d5e8f4', 'changed': '#ba2028', 'graph_point': '#ffda52'},
    'Dark': {'background': '#182330', 'surface': '#223344', 'text': '#eef4fb', 'muted': '#b6c9dc',
             'accent': '#126b75', 'selection': '#215f95', 'border': '#acbdcf', 'workspace': '#182330',
             'hover': '#3a5269', 'changed': '#ff9292', 'graph_point': '#ffda52'},
}
for _palette in DEFAULT_PALETTES.values():
    _palette.update(heat_low='#9ce7ee', heat_mid='#fff5d6', heat_high='#f58c84',
                    compare_low='#b9a0e5', compare_mid='#f1e7fc', compare_high='#ffd083', heat_invalid='#e3e7ed')


def clean_palette(values):
    if not isinstance(values, dict):
        return {}
    return {key: G.QColor(value).name() for key, value in values.items()
            if key in DEFAULT_PALETTES['Light'] and isinstance(value, str) and G.QColor(value).isValid()}


def read_palettes(settings):
    try:
        saved = json.loads(settings.value('colour_palettes', '{}'))
        return {theme: clean_palette(saved.get(theme, {})) for theme in DEFAULT_PALETTES}
    except (TypeError, ValueError, AttributeError):
        return {theme: {} for theme in DEFAULT_PALETTES}


def palette_for(theme='Light', overrides=None):
    return dict(DEFAULT_PALETTES.get(theme, DEFAULT_PALETTES['Light']), **clean_palette(overrides))


def contrast_text(color):
    def luminance(value):
        c = G.QColor(value)
        channels = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in (c.redF(), c.greenF(), c.blueF())]
        return sum(v * w for v, w in zip(channels, (.2126, .7152, .0722)))
    light = luminance(color)
    dark = luminance('#102235')
    return G.QColor('#102235' if (light + .05) / (dark + .05) >= 1.05 / (light + .05) else '#ffffff')


LIGHT = """
QWidget { background: #eef2f6; color: #17263c; font-family: 'Segoe UI'; font-size: 13px; }
QLabel { background: transparent; }
QLabel#brand { font-family: 'Trebuchet MS'; font-size: 24px; font-weight: 600; color: #132b49; }
QLabel#title { font-size: 24px; font-weight: 600; }
QLabel#tableTitle { font-size: 17px; font-weight: 600; }
QLabel#patchTitle { font-size: 21px; font-weight: 700; padding: 5px 2px; }
QLineEdit#patchName { font-size: 16px; font-weight: 600; }
QLabel#patchStatus { font-size: 16px; font-weight: 600; background: #e1e9f1; border: 1px solid #aabccc; padding: 12px; border-radius: 5px; }
QLabel#muted { color: #4c6077; }
QLabel#accent { color: #075f61; font-weight: 600; }
QFrame#sidebar { background: #dce5ee; border-right: 1px solid #acbdcf; }
QPushButton { background: #ffffff; border: 1px solid #acbdcf; border-radius: 4px; padding: 7px 11px; }
QPushButton:hover, QToolButton:hover { background: #d5e8f4; border-color: #38829f; }
QPushButton:checked, QPushButton#primary { background: #126b75; color: white; border-color: #126b75; }
QWidget:disabled { color: #788797; }
QPushButton:disabled { background: #e5eaf0; border-color: #c4cfdb; }
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox { background: white; border: 1px solid #a6b9cd; border-radius: 4px; padding: 5px; selection-background-color: #215f95; selection-color: white; }
QComboBox QAbstractItemView { background: white; selection-background-color: #215f95; selection-color: white; }
QTreeWidget, QTableWidget, QListWidget, QPlainTextEdit, QTextBrowser { background: white; alternate-background-color: #eef4fa; border: 1px solid #aabccc; selection-background-color: #215f95; selection-color: white; }
QTreeWidget::item { padding: 5px 2px; }
QTableWidget { gridline-color: #9baebe; }
QTableWidget::item:selected { background: #174b78; color: white; }
QHeaderView::section { background: #e2eaf2; color: #172b42; padding: 4px; border: none; border-right: 1px solid #aebfcf; border-bottom: 1px solid #aebfcf; }
QTabWidget::pane { border: 1px solid #aabccc; }
QTabBar::tab { background: #e0e8f0; padding: 6px 12px; }
QTabBar::tab:selected { background: white; color: #0a5062; }
QToolBar { background: #f7f9fc; border: none; spacing: 3px; padding: 2px; }
QToolButton { background: transparent; padding: 4px; border: 1px solid transparent; border-radius: 3px; }
QToolButton:checked { background: #e7d5fa; color: #522184; border-color: #9a62c9; }
QGroupBox { border: 1px solid #adbdcd; border-radius: 4px; margin-top: 12px; padding-top: 12px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; }
QStatusBar { background: #e1e9f1; color: #243e57; border-top: 1px solid #acbdcf; }
QMenuBar, QMenu { background: #f5f8fc; }
QMenu::item:selected { background: #d5e8f4; }
QSplitter::handle { background: #bbc9d7; }
QMdiArea { background: #b9c7d4; }
QMdiSubWindow { background: #eef2f6; border: 6px solid #7a94ae; }
QLabel#compareBanner { background: #eadbfa; color: #461469; border: 1px solid #9661ba; padding: 4px; font-weight: 600; }
QLabel#workingBanner { background: #e2f1ee; color: #164d48; border: 1px solid #92bfb5; padding: 4px; }
"""


def stylesheet(theme="Light", scale=100, palette=None):
    style = LIGHT
    if theme == "Dark":
        for old, new in {"#eef2f6": "#182330", "#17263c": "#eef4fb", "#132b49": "#ffffff", "#4c6077": "#b6c9dc",
                         "#075f61": "#80e0d0", "#dce5ee": "#101a25", "#ffffff": "#263749", "background: white": "background: #223344",
                         "#e5eaf0": "#22303f", "#eef4fa": "#293b4e", "#e2eaf2": "#30465d", "#172b42": "#ffffff",
                         "#e0e8f0": "#25384b", "#0a5062": "#77d8df", "#f7f9fc": "#22303f", "#e1e9f1": "#203144",
                         "#243e57": "#dce8f4", "#f5f8fc": "#1e2c3b", "#b9c7d4": "#0e1823", "#d5e8f4": "#3a5269"}.items():
            style = style.replace(old, new)
        style += "\nQLabel#brand { color: #ffffff; }\n"
    custom = clean_palette(palette)
    selectors = {
        'background': 'QWidget, QMenu, QMenuBar, QToolBar, QStatusBar, QFrame#sidebar',
        'surface': 'QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPushButton, QTreeWidget, QTableWidget, QListWidget, QPlainTextEdit, QTextBrowser, QComboBox QAbstractItemView, QHeaderView::section, QTabBar::tab',
        'text': 'QWidget, QLabel#brand, QLabel#title, QLabel#tableTitle, QHeaderView::section, QStatusBar, QComboBox QAbstractItemView',
        'muted': 'QLabel#muted, QWidget:disabled',
        'border': 'QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPushButton, QTreeWidget, QTableWidget, QPlainTextEdit, QTextBrowser, QGroupBox, QTabWidget::pane, QHeaderView::section',
    }
    for role, selector in selectors.items():
        if role in custom:
            prop = 'color' if role in ('text', 'muted') else 'border-color' if role == 'border' else 'background'
            style += f'\n{selector} {{ {prop}: {custom[role]}; }}'
    if 'background' in custom:
        style += '\nQLabel { background: transparent; }'
    if 'accent' in custom:
        color = custom['accent']
        style += f'\nQPushButton:checked, QPushButton#primary, QToolButton:checked {{ background: {color}; color: {contrast_text(color).name()}; border-color: {color}; }}'
    if 'selection' in custom:
        color = custom['selection']
        style += f'\nQLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTreeWidget, QTableWidget, QListWidget, QPlainTextEdit, QTextBrowser, QComboBox QAbstractItemView {{ selection-background-color: {color}; selection-color: {contrast_text(color).name()}; }}\nQTableWidget::item:selected, QMenu::item:selected {{ background: {color}; color: {contrast_text(color).name()}; }}'
    if 'hover' in custom:
        color = custom['hover']
        style += f'\nQPushButton:hover, QToolButton:hover {{ background: {color}; color: {contrast_text(color).name()}; }}'
    factor = max(.75, min(2., scale / 100))
    return re.sub(r"(\d+(?:\.\d+)?)px", lambda match: f"{max(1, round(float(match.group(1)) * factor))}px", style)


def heatmap_color(value, low, high, comparing=False, mode="Absolute", palette=None):
    palette = palette or DEFAULT_PALETTES['Light']
    if value is None:
        return G.QColor(palette.get('heat_invalid', '#e3e7ed'))
    if comparing and mode in ("Difference", "Percentage"):
        extent = max(abs(low), abs(high)) or 1
        ratio = .5 + .5 * value / extent
    else:
        ratio = (value - low) / (high - low) if high != low else .5
    ratio = max(0., min(1., ratio))
    # Normal: cyan -> cream -> coral. Compare: violet -> lavender -> amber.
    prefix = 'compare' if comparing else 'heat'
    stops = [palette.get(prefix + '_' + part, DEFAULT_PALETTES['Light'][prefix + '_' + part]) for part in ('low', 'mid', 'high')]
    first, second = (G.QColor(stops[0]), G.QColor(stops[1])) if ratio <= .5 else (G.QColor(stops[1]), G.QColor(stops[2]))
    blend = ratio * 2 if ratio <= .5 else (ratio - .5) * 2
    return G.QColor(*(round(a + (b - a) * blend) for a, b in zip(first.getRgb()[:3], second.getRgb()[:3])))
