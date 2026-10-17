# Windows release build

Use Python 3.11 x64 on Windows. Install `requirements.txt`, the GKFlasher requirements,
and the CAN logger requirements. `tools.build_release` records the installed runtime
versions in `runtime-requirements.txt` and includes the exact backend sources used.

Install `requirements-build.txt` into `.build-tools/python`, and install Inno Setup 6.
Run `python -m tools.build_release`. Use `--iscc`, `--flasher`, and `--logger` for
alternate locations; backend source folders in a release source ZIP can be supplied.
Use `--stage-only` to inspect the staged resources before freezing.

Outputs in `release/<version>`:

- `GK-Tuner-<version>-Setup-x64.exe`: per-user installer, Start menu, optional desktop shortcut, uninstaller.
- `GK-Tuner-<version>-Portable-x64.zip`: extract the entire directory before running.
- `GK-Tuner-<version>-Sources.zip`: app/build/backend sources and installed Python dependency sources.
- `READ-ME-FIRST.txt` and `SHA256SUMS.txt`.

PyInstaller includes Python, Qt/WebEngine, hardware libraries and libusb. Raw backend
modules stay beside their original assets, so GKFlasher's code is reused unchanged.
Only five named bootstrap/driver binaries are included; ECU dumps, personal XDFs,
capture logs and settings are excluded. The bundled logger's intentional sample CSV
is included. Third-party notices, metadata and available license files are bundled.

Run the EXE with `--smoke-test <absolute-report.json>` to test the frozen application
without hardware. Set `GKTUNER_DATA_DIR` to a disposable folder and use a clean
`PYTHONPATH`/`PYTHONHOME` when checking. This tests native startup, map editing/Undo,
backend imports and resource paths, original checksum calculation, WebEngine,
logger sample graphs, libusb and the palette bridge. Installer testing must also
cover install, launch, uninstall and retention of user data. Physical adapter tests
and code signing require a separate release pass.
