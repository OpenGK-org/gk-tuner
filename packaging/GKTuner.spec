# Build via: python -m tools.build_release
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs, copy_metadata

root = Path(SPECPATH).parent
stage = root / 'build' / 'release-stage'
hidden = []
datas = [(str(root / 'gktuner' / 'assets'), 'gktuner/assets'),
         (str(root / 'gktuner' / 'logger_web'), 'gktuner/logger_web'),
         (str(stage / 'backends'), 'backends'), (str(stage / 'licenses'), 'licenses'),
         (str(root / 'COMPATIBILITY.md'), '.'), (str(root / 'README.md'), '.'),
         (str(root / 'packaging' / 'TESTER-README.txt'), '.'),
         (str(stage / 'SOURCES.zip'), '.'), (str(stage / 'runtime-requirements.txt'), '.')]
binaries = []
for package in ('gkbus', 'can', 'serial', 'usb', 'gs_usb', 'crcmod', 'alive_progress', 'plyer', 'libusb_package'):
    hidden += [name for name in collect_submodules(package) if all(part.isidentifier() for part in name.split('.'))]
    datas += collect_data_files(package)
    binaries += collect_dynamic_libs(package)
hidden += ['yaml', 'scapy.contrib.cansocket', 'scapy.contrib.isotp', 'scapy.contrib.isotp.isotp_soft_socket',
           'scapy.contrib.isotp.isotp_packet', 'scapy.contrib.cansocket_python_can', 'PyQt5.QtSvg',
           'PyQt5.QtWebEngineWidgets', 'PyQt5.QtWebChannel', 'plyer.platforms.win.notification',
           'gktuner.release_check']
hidden += collect_submodules('PyQt5.uic')
for package in ('gkbus', 'python-can', 'gs-usb', 'pyusb', 'libusb-package', 'alive-progress', 'grapheme'):
    datas += copy_metadata(package)

a = Analysis([str(root / 'packaging' / 'desktop_entry.py')], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hidden,
             excludes=['tkinter', 'matplotlib', 'IPython', 'jupyter', 'pytest', 'PySide2', 'PySide6', 'PyQt6',
                       'flasher', 'gkflasher', 'ecu_definitions', 'bsl', '_version',
                       'ca663056_ccp_logger_v6', 'boost_can'],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='GK Tuner', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon=str(root / 'gktuner' / 'assets' / 'opengk.ico'),
          version=str(stage / 'version-info.txt'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='GK Tuner')
