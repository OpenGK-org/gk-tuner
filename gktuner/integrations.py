"""Adapters to the user's existing backends; opening the app never opens a bus."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from .runtime import resource_root, default_backend, data_root, frozen

ROOT = resource_root()
DEFAULT_FLASHER = default_backend('GKFlasher')
DEFAULT_LOGGER = default_backend('CANLogger')


def load_can_backend(folder):
    folder = Path(folder).resolve()
    entry = folder / "ccp_studio.py"
    if not entry.is_file():
        raise ValueError("Choose the CAN Logger folder containing ccp_studio.py.")
    # Keep the existing logger's imports and decoder logic intact.
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location("gktuner_ccp_backend", entry)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if frozen():
        module.CAPTURES = data_root() / 'Captures'
    return module


def flasher_command(folder, protocol, interface, operation, binary=None, output=None):
    folder = Path(folder).resolve()
    script = folder / "gkflasher.py"
    if not script.is_file():
        raise ValueError("Choose the GKFlasher source folder containing gkflasher.py.")
    if protocol not in ("canbus", "kline") or not interface.strip():
        raise ValueError("Choose a protocol and enter an adapter interface.")
    flags = {"Identify ECU": "--id", "Read full binary": "--read",
             "Read calibration": "--read-calibration", "Flash calibration": "--flash-calibration",
             "Flash program": "--flash-program", "Flash full binary": "--flash"}
    if operation not in flags:
        raise ValueError("Unsupported flasher operation.")
    args = ["-u", str(script), "--protocol", protocol, "--interface", interface.strip(), flags[operation]]
    if operation.startswith("Flash"):
        if not binary or not Path(binary).is_file():
            raise ValueError("Select an existing saved binary to flash.")
        args.append(str(Path(binary).resolve()))
    if operation.startswith("Read"):
        if not output:
            raise ValueError("Choose an output binary filename.")
        if Path(output).exists():
            raise ValueError("Choose a new output filename to preserve existing files.")
        args += ["--output", str(Path(output).resolve())]
    return args
