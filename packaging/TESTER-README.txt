GK Tuner - Windows Preview

Install using GK-Tuner-<version>-Setup-x64.exe, then open GK Tuner from the Start menu.
Windows 10/11, 64-bit. Python and a separate GKFlasher/logger installation are not required.
For the portable edition, extract the complete ZIP and open GK Tuner.exe. Keep _internal beside the EXE.

This is an unsigned test build. Windows may show a publisher/reputation prompt.
Your adapter still needs its Windows driver: a compatible serial driver for K-Line,
or the WinUSB driver for a supported gs_usb/candleLight CAN adapter. Drivers are not changed by this installer.

Map Editor: open a BIN and its matching XDF, or choose File > Open demonstration.
Table Save accepts edits into the working BIN. Save BIN writes a new file.
The checksum icon uses GKFlasher and shows existing/proposed checksums before applying.
Choose the connection protocol, interface and ECU before using logging or flashing.

Settings persist per Windows user. Logs and demo files are stored in:
%LOCALAPPDATA%\GK Tuner
CAN captures are in its Captures folder; runtime.log contains startup/error details.
Uninstall from Windows Settings > Apps. Uninstall preserves your settings, captures and BIN/XDF files.

For a test report, include the GK Tuner version, Windows version, adapter/protocol,
what you did, what you expected and what happened. Attach runtime.log if an error occurred.
Physical vehicle/adapter operation has not been validated by the packaged offline checks.

The release includes third-party notices and licenses under _internal\licenses,
and the GK Tuner/GKFlasher/logger build sources in _internal\SOURCES.zip.
