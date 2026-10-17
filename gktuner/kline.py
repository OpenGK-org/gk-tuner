"""Bounded ADX serial acquisition with explicit, reviewable compatibility checks.

Only the fixed-frame send/listen/silence/macro subset is executable. There is no
vehicle-specific command synthesis, flashing service, or implicit initialization.
"""
from __future__ import annotations

import csv
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from .core import Equation, integer, xml_file


class Cancelled(Exception):
    pass


@dataclass
class Channel:
    id: str
    title: str
    offset: int
    bits: int
    flags: int
    equation: Equation | None
    parent: str
    unit: str
    reason: str = ""

    def decode(self, packet):
        if self.reason:
            raise ValueError(self.reason)
        size = self.bits // 8
        if self.offset < 0 or self.offset + size > len(packet):
            raise ValueError(f"{self.title}: field is outside the received payload.")
        raw = int.from_bytes(packet[self.offset:self.offset + size], "little" if self.flags & 2 else "big", signed=bool(self.flags & 1))
        return self.equation(raw)


class Profile:
    TAGS = {"ADXMACRO", "ADXCSENDCOMMAND", "ADXCLISTENPACKET", "ADXCLISTENSILENCE"}

    def __init__(self, path):
        self.path = Path(path).resolve()
        self.root = xml_file(path, "ADXFORMAT")
        header = self.root.find("ADXHEADER")
        if header is None:
            raise ValueError("ADX header is missing.")
        self.baud = integer(header.findtext("baud"), 10400)
        if not 50 <= self.baud <= 1000000:
            raise ValueError("Initial ADX baud rate is outside the supported range.")
        defaults = header.find("DEFAULTS")
        default_flags = 0
        if defaults is not None:
            default_flags = (1 if integer(defaults.get("signed")) else 0) | (2 if integer(defaults.get("lsbfirst")) else 0) | (4 if integer(defaults.get("float")) else 0)
        self.entry = {phase: header.findtext(phase + "cmd", "") for phase in ("connect", "monitor", "disconnect")}
        self.commands = {n.get("id"): n for n in self.root if n.tag in self.TAGS}
        self.channels = []
        for node in self.root.findall("ADXVALUE"):
            channel = Channel(node.get("id", ""), node.get("title", node.get("id", "")), 0, 8, 0, None,
                              node.findtext("parentcmdidhash", "").lower(), node.findtext("units", ""))
            try:
                channel.offset = integer(node.findtext("packetoffset"))
                channel.bits = integer(node.findtext("sizeinbits"), integer(defaults.get("datasizeinbits"), 8) if defaults is not None else 8)
                channel.flags = integer(node.findtext("flags"), default_flags)
                if channel.bits not in (8, 16, 32, 64) or channel.flags & ~3:
                    raise ValueError("Unsupported ADX channel storage flags or size.")
                maths = node.findall("MATH")
                if len(maths) > 1:
                    raise ValueError("Multiple channel equations are not supported.")
                expression = maths[0] if maths else None
                if expression is not None:
                    for var in expression.findall("VAR"):
                        if var.get("varID", "X").upper() != "X" or var.get("type", "native") != "native":
                            raise ValueError("Linked ADX equation variables are not implemented yet.")
                channel.equation = Equation(expression.get("equation", "X") if expression is not None else "X")
            except (ValueError, SyntaxError, ZeroDivisionError) as exc:
                channel.reason = str(exc)
            self.channels.append(channel)
        self.transport_error = ""
        try:
            plan = self.plan()
            for channel in self.channels:
                if not channel.reason:
                    try:
                        self.validate_channels([channel], plan)
                    except ValueError as exc:
                        channel.reason = str(exc)
        except ValueError as exc:
            self.transport_error = str(exc)

    def flatten(self, command_id, stack=()):
        if not command_id:
            return []
        if command_id in stack or len(stack) > 12:
            raise ValueError("ADX macros contain a cycle or exceed the nesting limit.")
        node = self.commands.get(command_id)
        if node is None:
            raise ValueError(f"Missing or unsupported ADX command: {command_id}.")
        if node.tag != "ADXMACRO":
            return [node]
        repeat = integer(node.get("repeatcount"), 1)
        if not 1 <= repeat <= 100:
            raise ValueError("ADX repeat count must be between 1 and 100.")
        result = []
        for child in node.findall("NODE"):
            count = integer(child.get("repeatcount"), 1)
            if not 1 <= count <= 100:
                raise ValueError("ADX node repeat count must be between 1 and 100.")
            steps = self.flatten(child.get("commandID", ""), stack + (command_id,))
            if len(result) + len(steps) * count > 1000:
                raise ValueError("ADX macro expands beyond 1000 steps.")
            result.extend(steps * count)
        if len(result) * repeat > 1000:
            raise ValueError("ADX macro expands beyond 1000 steps.")
        return result * repeat

    def plan(self):
        if not self.entry["monitor"]:
            raise ValueError("ADX has no monitor command.")
        plan = {phase: self.flatten(command) for phase, command in self.entry.items()}
        if not any(n.tag == "ADXCLISTENPACKET" and integer(n.findtext("packetsize")) > 0 for n in plan["monitor"]):
            raise ValueError("Monitor macro has no fixed-length data payload.")
        for steps in plan.values():
            for node in steps:
                self.validate_command(node)
            duration = sum(integer(n.findtext("listentimeout"), 500) if n.tag == "ADXCLISTENPACKET" else integer(n.findtext("totaltimeout")) if n.tag == "ADXCLISTENSILENCE" else 2000 for n in steps)
            if duration > 30000:
                raise ValueError("ADX phase exceeds the 30-second bounded execution limit.")
        return plan

    def validate_channels(self, selected, plan):
        packets = [node for node in plan["monitor"] if node.tag == "ADXCLISTENPACKET" and integer(node.findtext("packetsize"))]
        ids = [channel.id for channel in selected]
        if len(set(ids)) != len(ids):
            raise ValueError("ADX channel IDs must be unique.")
        for channel in selected:
            matching = [node for node in packets if not channel.parent or node.get("idhash", "").lower() == channel.parent]
            if not matching:
                raise ValueError(f"{channel.title}: parent packet is not acquired by the monitor macro.")
            if channel.offset < 0 or any(channel.offset + channel.bits // 8 > integer(node.findtext("packetsize")) for node in matching):
                raise ValueError(f"{channel.title}: field exceeds the monitor packet payload.")

    @staticmethod
    def validate_command(node):
        allowed = {
            "ADXCSENDCOMMAND": {"desc", "baud", "bytestring", "SNDCMDCHECKSUM"},
            "ADXCLISTENPACKET": {"desc", "baud", "listentimeout", "packetbodylength", "packetoffsetinbody", "packetsize", "headerstring"},
            "ADXCLISTENSILENCE": {"desc", "silencelen", "totaltimeout"},
        }
        if node.tag not in allowed or any(child.tag not in allowed[node.tag] for child in node):
            raise ValueError(f"{node.get('id')}: unsupported command options.")
        baud = integer(node.findtext("baud"))
        if baud and not 50 <= baud <= 1000000:
            raise ValueError("Unsupported serial baud rate.")
        if node.tag == "ADXCSENDCOMMAND":
            payload = bytes.fromhex(node.findtext("bytestring", ""))
            if not 1 <= len(payload) <= 4096:
                raise ValueError("Send commands need 1–4096 bytes.")
            declared = node.find("bytestring").get("size")
            if declared is not None and integer(declared) != len(payload):
                raise ValueError("Send command byte count does not match its declared size.")
            checksum = node.find("SNDCMDCHECKSUM")
            if checksum is not None and (checksum.get("type") != "1" or set(checksum.attrib) != {"type"}):
                raise ValueError("Only whole-command additive 8-bit send checksums are supported.")
            if integer(node.get("flags")):
                raise ValueError("Send command flags are not supported.")
        elif node.tag == "ADXCLISTENPACKET":
            flags = integer(node.get("flags"))
            if flags & ~5:
                raise ValueError("Unsupported receive flags.")
            body = integer(node.findtext("packetbodylength"))
            offset = integer(node.findtext("packetoffsetinbody"))
            size = integer(node.findtext("packetsize"))
            header = bytes.fromhex(node.findtext("headerstring", ""))
            if not header or len(header) > 256 or not 0 <= offset <= body <= 65536 or not 0 <= size <= body - offset:
                raise ValueError("Invalid fixed-frame receive lengths or missing synchronization header.")
            timeout = integer(node.findtext("listentimeout"), 500)
            if not 1 <= timeout <= 10000:
                raise ValueError("Receive timeout must be 1–10000 ms.")
        else:
            if integer(node.findtext("silencelen")) != 0:
                raise ValueError("Adaptive silence waits are not implemented; use fixed delays.")
            if not 0 <= integer(node.findtext("totaltimeout")) <= 10000:
                raise ValueError("Pause exceeds 10 seconds.")


class Runner:
    def __init__(self, profile, serial_port, stop_event, callback, selected, verify_sum=False):
        self.profile, self.serial, self.stop_event = profile, serial_port, stop_event
        self.callback, self.selected = callback, selected
        self.verify_sum = verify_sum
        self.steps = profile.plan()
        self.buffer = bytearray()

    def check_stop(self):
        if self.stop_event.is_set():
            raise Cancelled()

    def read_exact(self, count, deadline):
        while len(self.buffer) < count:
            self.check_stop()
            if time.monotonic() >= deadline:
                raise TimeoutError("K-line receive timed out.")
            data = self.serial.read(max(1, count - len(self.buffer)))
            self.buffer.extend(data)
        result = bytes(self.buffer[:count])
        del self.buffer[:count]
        return result

    def receive(self, node, capture=True):
        header = bytes.fromhex(node.findtext("headerstring"))
        deadline = time.monotonic() + integer(node.findtext("listentimeout"), 500) / 1000
        # Header matching also skips local adapter echo without assuming it exists.
        window = bytearray()
        scanned = 0
        while bytes(window) != header:
            window.extend(self.read_exact(1, deadline))
            if len(window) > len(header):
                del window[0]
            scanned += 1
            if scanned > 131072:
                raise ValueError("K-line could not synchronize to the ADX header.")
        body = self.read_exact(integer(node.findtext("packetbodylength")), deadline)
        if self.verify_sum and body:
            frame = header + body
            if sum(frame[:-1]) & 255 != frame[-1]:
                raise ValueError("K-line frame checksum mismatch.")
        offset, size = integer(node.findtext("packetoffsetinbody")), integer(node.findtext("packetsize"))
        payload = body[offset:offset + size]
        if size and capture:
            parent = node.get("idhash", "").lower()
            row = {}
            for channel in self.selected:
                if channel.parent and channel.parent != parent:
                    continue
                row[channel.id] = channel.decode(payload)
            if row:
                self.callback(row)

    def execute(self, steps, capture=True):
        for node in steps:
            self.check_stop()
            baud = integer(node.findtext("baud"))
            if baud:
                self.serial.baudrate = baud
            if node.tag == "ADXCSENDCOMMAND":
                payload = bytes.fromhex(node.findtext("bytestring"))
                if node.find("SNDCMDCHECKSUM") is not None:
                    payload += bytes([sum(payload) & 255])
                written = self.serial.write(payload)
                if written != len(payload):
                    raise IOError("K-line adapter accepted only part of a command.")
                self.serial.flush()
            elif node.tag == "ADXCLISTENSILENCE":
                if self.stop_event.wait(integer(node.findtext("totaltimeout")) / 1000):
                    raise Cancelled()
            else:
                self.receive(node, capture)


class KLineSession:
    """Same snapshot/samples lifecycle as the existing CAN logger adapter."""
    def __init__(self, profile):
        self.profile = profile
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.state = "idle"
        self.error = self.output = ""
        self.rows = deque(maxlen=10000)
        self.count = 0

    def snapshot(self):
        with self.lock:
            return {"state": self.state, "error": self.error, "output": self.output,
                    "count": self.count, "incomplete": 0}

    def samples(self, since):
        with self.lock:
            base = self.count - len(self.rows)
            start = max(0, since - base)
            return {"rows": list(self.rows)[start:], "next": self.count}

    def start(self, selected_ids, port, output, verify_sum=False):
        plan = self.profile.plan()  # Reject unsupported commands before opening any device.
        selected = [c for c in self.profile.channels if c.id in selected_ids]
        if not selected or any(c.reason for c in selected):
            raise ValueError("Choose at least one supported ADX channel.")
        self.profile.validate_channels(selected, plan)
        if not port.strip():
            raise ValueError("Enter the K-line adapter's serial port, for example COM3.")
        target = Path(output).resolve()
        if target.exists():
            raise ValueError("Choose a new log filename.")
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError("The previous K-line session is still releasing the adapter.")
            self.stop_event.clear()
            self.state, self.error, self.count = "connecting", "", 0
            self.rows.clear()
            self.output = str(target)
            self.thread = threading.Thread(target=self._run, args=(selected, port, target, verify_sum), daemon=True)
            self.thread.start()

    def stop(self):
        with self.lock:
            if self.state in ("connecting", "recording"):
                self.state = "stopping"
                self.stop_event.set()

    def _run(self, selected, port, output, verify_sum):
        serial_port = None
        runner = None
        failure = ""
        try:
            import serial
            with output.open("x", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["t_s"] + [c.id for c in selected])
                writer.writeheader()
                started = time.monotonic()

                def sample(values):
                    row = {"t_s": time.monotonic() - started, **values}
                    writer.writerow(row)
                    stream.flush()
                    with self.lock:
                        self.rows.append(row)
                        self.count += 1

                serial_port = serial.Serial(port, baudrate=self.profile.baud, timeout=.025, write_timeout=2)
                runner = Runner(self.profile, serial_port, self.stop_event, sample, selected, verify_sum)
                runner.execute(runner.steps["connect"], capture=False)
                with self.lock:
                    self.state = "recording"
                while not self.stop_event.is_set():
                    runner.execute(runner.steps["monitor"])
                    self.stop_event.wait(.001)
        except Cancelled:
            pass
        except Exception as exc:
            failure = str(exc)
        finally:
            if runner and serial_port and serial_port.is_open:
                # Disconnect is bounded and uses an independent cancellation token.
                try:
                    runner.stop_event = threading.Event()
                    runner.execute(runner.steps["disconnect"], capture=False)
                except Exception as exc:
                    failure = failure or f"Disconnect failed: {exc}"
            if serial_port:
                serial_port.close()
            with self.lock:
                self.error = failure
                self.state = "error" if failure else "stopped"
