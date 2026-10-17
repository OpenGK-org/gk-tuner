"""Build the self-contained Windows desktop app, installer, ZIP and hashes.

Only explicit backend sources/resources are staged. Never collect ECU images,
personal definitions, captures, settings, caches or the backend working folders.
"""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'build' / 'release-stage'
RUNTIME_PACKAGES = ('PyQt5', 'PyQtWebEngine', 'gkbus', 'python-can', 'gs-usb', 'pyusb',
                    'libusb-package', 'PyYAML', 'crcmod', 'alive-progress', 'plyer')
FLASHER_FILES = ('gui.py', 'gkflasher.py', 'bsl.py', 'ecu_definitions.py', '_version.py',
                 'gkflasher.yml', 'LICENSE', 'README.md', 'requirements.txt')
BOOT_FILES = ('simk43_rsw_fl2.bin', 'simk4x_bootstrap.bin', 'simk4x_kernel.bin',
              'simk4x_driver_i4_a29fx00bx.bin', 'simk4x_driver_v6_a29fx00bx.bin')
LOGGER_FILES = ('ccp_studio.py', 'ca663056_ccp_logger_v6.py', 'boost_can.py', 'requirements.txt', 'README.md')


def copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def stage_backends(flasher, logger):
    for name in FLASHER_FILES:
        copy_file(flasher / name, STAGE / 'backends' / 'GKFlasher' / name)
    for name in BOOT_FILES:
        copy_file(flasher / 'assets' / name, STAGE / 'backends' / 'GKFlasher' / 'assets' / name)
    for source in (flasher / 'flasher').rglob('*'):
        if source.is_file() and source.suffix in ('.py', '.ui', '.qss') and '__pycache__' not in source.parts:
            copy_file(source, STAGE / 'backends' / 'GKFlasher' / source.relative_to(flasher))
    for name in LOGGER_FILES:
        copy_file(logger / name, STAGE / 'backends' / 'CANLogger' / name)
    copy_file(logger / 'Sample' / 'idle_v3.csv', STAGE / 'backends' / 'CANLogger' / 'Sample' / 'idle_v3.csv')


def stage_licenses_and_sources():
    from packaging.requirements import Requirement
    pending, distributions = list(RUNTIME_PACKAGES), {}
    while pending:
        dist = metadata.distribution(pending.pop())
        name = dist.metadata['Name']
        if name in distributions:
            continue
        distributions[name] = dist
        for value in dist.requires or ():
            req = Requirement(value)
            if req.marker is None or req.marker.evaluate({'extra': ''}):
                pending.append(req.name)
    lines = [f'{name}=={dist.version}' for name, dist in sorted(distributions.items())]
    (STAGE / 'runtime-requirements.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    notices = [
        'GK Tuner test distribution - third-party notices',
        'GKFlasher and GKBus include GNU GPL v3 licensed code; their original license is included.',
        'PyQt5 and PyQtWebEngine are GPL v3 builds. Qt and Chromium include additional licenses.',
        'Bundled components remain subject to their respective copyright and license terms.',
        'GK Tuner, backend and build sources are in SOURCES.zip. Runtime versions are in runtime-requirements.txt.',
        'Upstream source archives for the bundled Qt/PyQt components:',
        'https://www.riverbankcomputing.com/software/pyqt/download',
        'https://download.qt.io/archive/qt/5.15/5.15.2/submodules/',
        'Other component versions and upstream URLs are recorded in their METADATA files below.',
        '',
    ]
    license_root = STAGE / 'licenses'
    license_root.mkdir(parents=True, exist_ok=True)
    copy_file(STAGE / 'backends' / 'GKFlasher' / 'LICENSE', license_root / 'GKFlasher-GPL-3.0.txt')
    for name, dist in distributions.items():
        folder = license_root / name
        folder.mkdir(exist_ok=True)
        (folder / 'METADATA.txt').write_text(dist.read_text('METADATA') or str(dist.metadata), encoding='utf-8')
        for file in dist.files or ():
            if any(token in file.name.lower() for token in ('license', 'copying', 'copyright', 'notice')):
                source = Path(dist.locate_file(file))
                if source.is_file() and source.suffix.lower() not in ('.pyc', '.pyd', '.dll', '.exe'):
                    copy_file(source, folder / str(file).replace('../', '').replace('..\\', ''))
    (license_root / 'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(notices), encoding='utf-8')
    with zipfile.ZipFile(STAGE / 'SOURCES.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
        for folder in ('gktuner', 'tools', 'tests', 'packaging'):
            for source in (ROOT / folder).rglob('*'):
                if source.is_file() and '__pycache__' not in source.parts and source.suffix != '.pyc':
                    bundle.write(source, source.relative_to(ROOT).as_posix())
        for name in ('pyproject.toml', 'requirements.txt', 'requirements-build.txt', 'README.md', 'COMPATIBILITY.md', 'VALIDATION.md'):
            bundle.write(ROOT / name, name)
        for source in (STAGE / 'backends').rglob('*'):
            if source.is_file():
                bundle.write(source, source.relative_to(STAGE).as_posix())
        # Include the installed Python dependency sources, including local GKBus changes.
        for name, dist in distributions.items():
            for file in dist.files or ():
                source = Path(dist.locate_file(file))
                if source.is_file() and source.suffix in ('.py', '.sip', '.h', '.c') and '..' not in file.parts:
                    bundle.write(source, 'dependencies/' + name + '/' + file.as_posix())
        bundle.writestr('BUILDING.txt', 'Install runtime-requirements.txt and requirements-build.txt using Python 3.11 x64.\nRun python -m tools.build_release with --flasher and --logger pointing at the included backends.\nInno Setup 6 is needed for --iscc. See packaging/README.md.\n')
        bundle.write(STAGE / 'runtime-requirements.txt', 'runtime-requirements.txt')


def make_icon():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W
    app = W.QApplication.instance() or W.QApplication(['icon-build'])
    icon = G.QIcon(str(ROOT / 'gktuner' / 'assets' / 'opengk.svg'))
    payloads = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        buffer = C.QBuffer()
        buffer.open(C.QIODevice.WriteOnly)
        assert icon.pixmap(size, size).save(buffer, 'PNG')
        payloads.append((size, bytes(buffer.data())))
    offset = 6 + 16 * len(payloads)
    entries = []
    for size, data in payloads:
        entries.append(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    (ROOT / 'gktuner' / 'assets' / 'opengk.ico').write_bytes(struct.pack('<HHH', 0, 1, len(payloads)) + b''.join(entries) + b''.join(data for _, data in payloads))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flasher', type=Path, default=ROOT.parent / 'GKFlasher-1.99 STOCK')
    parser.add_argument('--logger', type=Path, default=ROOT.parent / 'ECU Reverse Engineering/ca663056 CCP/Logger')
    parser.add_argument('--iscc', type=Path, default=ROOT / '.build-tools/Inno Setup 6/ISCC.exe')
    parser.add_argument('--stage-only', action='store_true')
    parser.add_argument('--app-only', action='store_true', help='Build the app for smoke checks before packaging')
    args = parser.parse_args()
    from gktuner import __version__
    if STAGE.exists():
        # Only this fixed build directory is recreated, never a source/input path.
        assert STAGE.resolve().is_relative_to(ROOT / 'build')
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    make_icon()
    stage_backends(args.flasher.resolve(), args.logger.resolve())
    stage_licenses_and_sources()
    version = tuple(int(part) for part in __version__.split('.')) + (0,)
    (STAGE / 'version-info.txt').write_text(f'''VSVersionInfo(ffi=FixedFileInfo(filevers={version}, prodvers={version}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)), kids=[StringFileInfo([StringTable('040904B0', [StringStruct('CompanyName', 'OpenGK'), StringStruct('FileDescription', 'GK Tuner'), StringStruct('FileVersion', '{__version__}'), StringStruct('InternalName', 'GKTuner'), StringStruct('OriginalFilename', 'GK Tuner.exe'), StringStruct('ProductName', 'GK Tuner'), StringStruct('ProductVersion', '{__version__}')])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])''', encoding='utf-8')
    manifest = {p.relative_to(STAGE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (STAGE / 'backends').rglob('*') if p.is_file()}
    (STAGE / 'backend-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    if args.stage_only:
        print('Staged explicit backend sources, assets, licenses, source archive and icon.')
        return
    build_root = ROOT / 'build' / 'desktop'
    release = ROOT / 'release' / __version__
    release.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    tool_path = ROOT / '.build-tools' / 'python'
    if tool_path.is_dir():
        env['PYTHONPATH'] = str(tool_path)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(build_root), '--workpath', str(ROOT / 'build' / 'pyinstaller'), str(ROOT / 'packaging' / 'GKTuner.spec')], cwd=ROOT, env=env, check=True)
    if args.app_only:
        print('Desktop app ready for smoke checks:', build_root)
        return
    subprocess.run([str(args.iscc), '/Qp', '/DAppVersion=' + __version__, '/DBuildRoot=' + str(build_root), '/DReleaseDir=' + str(release), str(ROOT / 'packaging' / 'installer.iss')], check=True)
    shutil.make_archive(str(release / f'GK-Tuner-{__version__}-Portable-x64'), 'zip', build_root, 'GK Tuner')
    copy_file(ROOT / 'packaging' / 'TESTER-README.txt', release / 'READ-ME-FIRST.txt')
    copy_file(STAGE / 'SOURCES.zip', release / f'GK-Tuner-{__version__}-Sources.zip')
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name for p in sorted(release.iterdir()) if p.is_file() and p.name != 'SHA256SUMS.txt']
    (release / 'SHA256SUMS.txt').write_text('\n'.join(hashes) + '\n', encoding='utf-8')
    print('Release ready:', release)


if __name__ == '__main__':
    main()
