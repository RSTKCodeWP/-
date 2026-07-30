"""Ctrl/OSD UDP command-line client for the Ascent VRX and MSP protocols."""

from __future__ import annotations

import argparse
import select
import socket
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from msp_osd import (
    MspDisplayPortCommand,
    MspDisplayPortSubcommand,
    MspFrameReassembler,
    MspOsdParser,
)

HEADER = bytes.fromhex("FE EF")
TAIL = bytes.fromhex("0D 0A")
MAX_PAYLOAD_LENGTH = 0xFFFF
DEFAULT_CTRL_PORT = 9001
DEFAULT_OSD_PORT = 9200
PASSTHROUGH_COMMAND = 0x23
SET_MODE_SUBCOMMAND = 0x02
OSD_PROBE_BYTES = bytes.fromhex("31 32 33 34")
MODE_SWITCH_DELAY_SECONDS = 0.5
OSD_NO_DATA_TIMEOUT_SECONDS = 1.0


class PassthroughMode(IntEnum):
    """VRX passthrough modes accepted by the set-mode command."""

    NONE = 0
    MAVLINK = 1
    CRSF = 2
    SBUS = 3
    USER = 4
    OSD = 5


@dataclass(frozen=True)
class DeviceConnectionProfile:
    """Resolved device address and the independent Ctrl/OSD UDP ports."""

    name: str
    host: str
    ctrl_port: int = DEFAULT_CTRL_PORT
    osd_port: int = DEFAULT_OSD_PORT


DEVICE_CONNECTION_PROFILES = {
    "rj45": DeviceConnectionProfile("rj45", "192.168.1.100"),
    "usb-c": DeviceConnectionProfile("usb-c", "192.168.3.102"),
}


class ProtocolError(ValueError):
    """Raised when a received packet violates the configured protocol."""


def calculate_checksum(payload: bytes) -> bytes:
    """Calculate the checksum for a protocol payload.

    Args:
        payload: Raw payload bytes. Frame metadata is not included.

    Returns:
        The payload-byte sum modulo 65536, encoded as two big-endian bytes.
    """
    return (sum(payload) & 0xFFFF).to_bytes(2, byteorder="big")


def assemble_packet(command: int, payload: bytes) -> bytes:
    """Assemble a complete VRX protocol packet.

    Args:
        command: One-byte protocol command value.
        payload: Command-specific payload bytes.

    Returns:
        A packet containing the header, command, payload length, payload,
        checksum, and frame tail.

    Raises:
        ValueError: If the command or payload length is outside the protocol
            range.
    """
    if not 0 <= command <= 0xFF:
        raise ValueError("command must be an unsigned byte")
    if len(payload) > MAX_PAYLOAD_LENGTH:
        raise ValueError("payload exceeds 65535 bytes")

    return (
        HEADER
        + bytes([command])
        + len(payload).to_bytes(2, byteorder="big")
        + payload
        + calculate_checksum(payload)
        + TAIL
    )


def build_set_mode_packet(mode: PassthroughMode | int) -> bytes:
    """Build a VRX passthrough-mode switch frame for Ctrl UDP port 9001."""
    try:
        resolved_mode = PassthroughMode(mode)
    except ValueError as error:
        raise ValueError("unsupported passthrough mode") from error

    payload = bytes(
        [SET_MODE_SUBCOMMAND, int(resolved_mode), 0x00, 0x00, 0x00]
    )
    return assemble_packet(PASSTHROUGH_COMMAND, payload)


def parse_packet(data: bytes) -> tuple[int, bytes]:
    """Validate and decode one complete VRX protocol packet.

    Args:
        data: A complete UDP datagram containing one protocol frame.

    Returns:
        A tuple containing the command byte and raw payload bytes.

    Raises:
        ProtocolError: If the header, length, checksum, tail, or minimum frame
            size is invalid.
    """
    minimum_size = 2 + 1 + 2 + 2 + 2
    if len(data) < minimum_size:
        raise ProtocolError("packet is shorter than the minimum frame length")
    if data[:2] != HEADER:
        raise ProtocolError("invalid header")

    payload_length = int.from_bytes(data[3:5], byteorder="big")
    expected_size = 2 + 1 + 2 + payload_length + 2 + 2
    if len(data) != expected_size:
        raise ProtocolError(
            f"length mismatch: declared {payload_length} payload bytes, "
            f"received {len(data)} total bytes"
        )

    payload_end = 5 + payload_length
    payload = data[5:payload_end]
    received_checksum = data[payload_end:payload_end + 2]
    if received_checksum != calculate_checksum(payload):
        raise ProtocolError("checksum mismatch")
    if data[payload_end + 2:payload_end + 4] != TAIL:
        raise ProtocolError("invalid tail")

    return data[2], payload


WRITE_COMMAND = 0x22
READ_COMMAND = 0xA2
KEYS = {
    "up": (0, 0),
    "down": (1, 0),
    "left": (2, 0),
    "right": (3, 0),
    "confirm": (4, 0),
    "pairing": (5, 0),
    "upgrade": (5, 1),
    "recording": (6, 0),
    "back": (7, 0),
    "force-720p60": (7, 1),
    "debug3": (9, 0),
}
BANDS = {"A": 0, "B": 1, "C": 2}

NORMAL_KEYBOARD_ACTIONS = {
    "w": "up",
    "s": "down",
    "a": "left",
    "d": "right",
    "e": "confirm",
    "\r": "confirm",
    "\x08": "back",
    "p": "pairing",
    "u": "upgrade",
    "r": "recording",
    "q": "quit",
}
EXTENDED_KEYBOARD_ACTIONS = {
    "H": "up",
    "P": "down",
    "K": "left",
    "M": "right",
}


def keyboard_input_to_action(character: str, *, extended: bool = False) -> str | None:
    """Translate a Windows console character into a keyboard action.

    Args:
        character: Character returned by ``msvcrt.getwch()``.
        extended: Whether the character belongs to an extended-key sequence,
            such as an arrow key.

    Returns:
        A VRX key name, ``"quit"``, or ``None`` for an unmapped key.
    """
    if extended:
        return EXTENDED_KEYBOARD_ACTIONS.get(character)
    lookup = character.lower() if character.isalpha() else character
    return NORMAL_KEYBOARD_ACTIONS.get(lookup)


def channel_number(value: str) -> int:
    """Convert a command-line value into a valid channel index.

    Args:
        value: Text supplied for the ``--channel`` argument.

    Returns:
        An integer channel index from 0 through 16.

    Raises:
        argparse.ArgumentTypeError: If the value is not an integer in range.
    """
    try:
        channel = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "channel must be an integer from 0 to 16"
        ) from error
    if not 0 <= channel <= 16:
        raise argparse.ArgumentTypeError("channel must be from 0 to 16")
    return channel


def power_index(value: str) -> int:
    """Convert a command-line value into a valid power index.

    Args:
        value: Text supplied for the power-index argument.

    Returns:
        An integer power index from 0 through 19.

    Raises:
        argparse.ArgumentTypeError: If the value is not an integer in range.
    """
    try:
        index = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "power index must be an integer from 0 to 19"
        ) from error
    if not 0 <= index <= 19:
        raise argparse.ArgumentTypeError("power index must be from 0 to 19")
    return index


def udp_port(value: str) -> int:
    """Convert a command-line value into a valid non-zero UDP port."""
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be from 1 to 65535")
    return port


def create_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for Ctrl-only and dual-channel operations."""
    parser = argparse.ArgumentParser(description="Ascent VRX UDP protocol client")
    parser.add_argument(
        "--profile",
        choices=sorted(DEVICE_CONNECTION_PROFILES),
        default="rj45",
        help="device connection profile",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="device address; overrides the selected profile",
    )
    parser.add_argument(
        "--port",
        "--ctrl-port",
        dest="ctrl_port",
        default=None,
        type=udp_port,
        help="Ctrl UDP port; --port is retained for compatibility",
    )
    parser.add_argument(
        "--osd-port",
        default=None,
        type=udp_port,
        help="OSD UDP port",
    )
    subcommands = parser.add_subparsers(dest="operation", required=True)

    key_parser = subcommands.add_parser("key", help="simulate a VRX key press")
    key_parser.add_argument("key_name", choices=sorted(KEYS))

    frequency_parser = subcommands.add_parser(
        "set-frequency", help="set band/channel/hopping"
    )
    frequency_parser.add_argument("--band", choices=sorted(BANDS), required=True)
    frequency_parser.add_argument("--channel", type=channel_number, required=True)
    frequency_parser.add_argument(
        "--hop", action="store_true", help="enable frequency hopping"
    )

    subcommands.add_parser("get-frequency", help="request current frequency")
    subcommands.add_parser("status", help="request wireless status")
    subcommands.add_parser("get-power", help="request power index and supported values")
    subcommands.add_parser(
        "keyboard", help="interactively send VRX key presses from the keyboard"
    )

    power_parser = subcommands.add_parser("set-power", help="set power index")
    power_parser.add_argument("index", type=power_index)

    mode_parser = subcommands.add_parser(
        "set-mode", help="switch the VRX passthrough mode on Ctrl UDP"
    )
    mode_parser.add_argument("mode", choices=("crsf", "osd"))

    osd_parser = subcommands.add_parser(
        "osd", help="start Ctrl/OSD UDP channels and print parsed MSP frames"
    )
    osd_parser.add_argument(
        "--no-mode-switch",
        action="store_true",
        help="send the OSD probe without first switching the VRX to OSD mode",
    )
    return parser


def resolve_connection_profile(
    args: argparse.Namespace,
) -> DeviceConnectionProfile:
    """Resolve profile defaults and explicit CLI endpoint overrides."""
    base = DEVICE_CONNECTION_PROFILES[args.profile]
    return DeviceConnectionProfile(
        name=base.name,
        host=args.host or base.host,
        ctrl_port=args.ctrl_port or base.ctrl_port,
        osd_port=args.osd_port or base.osd_port,
    )


def build_command_payload(args: argparse.Namespace) -> tuple[int, bytes]:
    """Build protocol command fields from parsed command-line arguments.

    Args:
        args: Namespace returned by :func:`create_argument_parser`.

    Returns:
        A tuple containing the outer command byte and command payload.

    Raises:
        ValueError: If the requested operation has no packet implementation.
    """
    if args.operation == "key":
        key_number, press_type = KEYS[args.key_name]
        return WRITE_COMMAND, bytes([0x40, key_number, press_type, 0x00])
    if args.operation == "set-frequency":
        return WRITE_COMMAND, bytes(
            [0x50, BANDS[args.band], args.channel, int(args.hop), 0, 0, 0, 0]
        )
    if args.operation == "get-frequency":
        return READ_COMMAND, bytes([0x51, 0, 0, 0, 0, 0, 0, 0])
    if args.operation == "status":
        return READ_COMMAND, bytes([0x52, 0, 0, 0, 0, 0, 0, 0])
    if args.operation == "get-power":
        return READ_COMMAND, bytes([0x53, 0, 0, 0, 0, 0, 0, 0])
    if args.operation == "set-power":
        return WRITE_COMMAND, bytes([0x54, args.index, 0, 0, 0, 0, 0, 0])
    if args.operation == "set-mode":
        mode = PassthroughMode.CRSF if args.mode == "crsf" else PassthroughMode.OSD
        return (
            PASSTHROUGH_COMMAND,
            bytes([SET_MODE_SUBCOMMAND, int(mode), 0, 0, 0]),
        )
    raise ValueError(f"unsupported operation: {args.operation}")


def decode_payload(payload: bytes) -> dict[str, object]:
    """Decode a known wireless-response payload into named values.

    Args:
        payload: Raw response payload extracted from a validated packet.

    Returns:
        A dictionary describing an empty, frequency, wireless-status, or power
        response payload.
    """
    if not payload:
        return {"type": "empty"}

    command_type = payload[0]
    values = payload[1:]
    if command_type == 0x51 and len(values) >= 3:
        band_names = {0: "A", 1: "B", 2: "C"}
        return {
            "type": "frequency",
            "band": band_names.get(values[0], f"unknown({values[0]})"),
            "channel": values[1],
            "hopping": values[2] == 1,
        }
    if command_type == 0x52 and len(values) >= 6:
        return {
            "type": "wireless_status",
            "rssi1": values[0],
            "rssi2": values[1],
            "data_rate_mbps": values[3],
            "delay_ms": values[4],
            "connected": values[5] == 1,
        }
    if command_type == 0x53 and len(values) >= 5:
        settable_indices = []
        for byte_index, bitmap_byte in enumerate(values[1:5]):
            for bit_index in range(8):
                if bitmap_byte & (1 << bit_index):
                    settable_indices.append(byte_index * 8 + bit_index)
        return {
            "type": "power",
            "power_index": values[0],
            "settable_indices": settable_indices,
        }
    return {
        "type": "unknown",
        "command_type": command_type,
        "data": bytes(values),
    }


class UdpChannel:
    """Connected UDP channel with an explicit start/close lifecycle."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        label: str,
        sock: socket.socket | None = None,
    ):
        if not 1 <= port <= 65535:
            raise ValueError("port must be from 1 to 65535")
        self.address = (host, port)
        self.label = label
        self.socket = sock
        self._provided_socket = sock is not None
        self.is_running = False

    def start(self) -> None:
        """Bind an ephemeral local port and connect to the remote endpoint."""
        if self.is_running:
            return
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(("", 0))
            self.socket.connect(self.address)
            self.is_running = True
        except Exception:
            self.socket.close()
            if not self._provided_socket:
                self.socket = None
            raise

    def send(self, data: bytes) -> None:
        """Send one datagram through the connected channel."""
        if not self.is_running or self.socket is None:
            raise OSError(f"{self.label} UDP channel is not running")
        self.socket.send(data)

    def receive(self) -> tuple[bytes, tuple[str, int]]:
        """Receive one datagram and its source endpoint."""
        if not self.is_running or self.socket is None:
            raise OSError(f"{self.label} UDP channel is not running")
        return self.socket.recvfrom(MAX_PAYLOAD_LENGTH)

    def close(self) -> None:
        """Close the socket; repeated calls are safe."""
        current_socket = self.socket
        self.is_running = False
        if current_socket is not None:
            current_socket.close()
        if not self._provided_socket:
            self.socket = None


class DualUdpVrxSession:
    """Coordinate Ctrl UDP 9001 and OSD UDP 9200 for MSP diagnostics."""

    def __init__(
        self,
        host: str,
        ctrl_port: int = DEFAULT_CTRL_PORT,
        osd_port: int = DEFAULT_OSD_PORT,
        *,
        control_channel: UdpChannel | None = None,
        osd_channel: UdpChannel | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
        select_fn: Callable[..., tuple[list[object], list[object], list[object]]] = (
            select.select
        ),
        output: Callable[[str], None] = print,
    ):
        self.host = host
        self.ctrl_port = ctrl_port
        self.osd_port = osd_port
        self.control_channel = control_channel or UdpChannel(
            host, ctrl_port, label="Ctrl"
        )
        self.osd_channel = osd_channel or UdpChannel(
            host, osd_port, label="OSD"
        )
        self.sleep_fn = sleep_fn
        self.monotonic_fn = monotonic_fn
        self.select_fn = select_fn
        self.output = output
        self.osd_reassembler = MspFrameReassembler()
        self._last_osd_data_time: float | None = None
        self._osd_status: str | None = None

    def start(self, *, send_mode_switch: bool = True) -> None:
        """Start both channels, switch mode, wait 500 ms, then probe OSD."""
        try:
            self.control_channel.start()
            self.output(f"Ctrl UDP started: {self.host}:{self.ctrl_port}")
            self.osd_channel.start()
            self.output(f"OSD UDP started: {self.host}:{self.osd_port}")
            self._set_osd_status("OSD=connect")

            if send_mode_switch:
                packet = build_set_mode_packet(PassthroughMode.OSD)
                self.control_channel.send(packet)
                self.output(
                    "Ctrl TX OSD mode: " + packet.hex(" ").upper()
                )
                self.sleep_fn(MODE_SWITCH_DELAY_SECONDS)

            self.osd_channel.send(OSD_PROBE_BYTES)
            self.output(
                "OSD TX probe: " + OSD_PROBE_BYTES.hex(" ").upper()
            )
            self._last_osd_data_time = self.monotonic_fn()
        except Exception:
            self.close()
            raise

    def handle_control_datagram(
        self,
        data: bytes,
        source: tuple[str, int],
    ) -> None:
        """Print a Ctrl datagram and attempt VRX-frame decoding."""
        self.output(
            f"CTRL RX <- {source[0]}:{source[1]}  "
            f"{data.hex(' ').upper()}"
        )
        try:
            command, payload = parse_packet(data)
            decoded = decode_payload(payload)
            self.output(f"  command: 0x{command:02X}")
            for key, value in decoded.items():
                self.output(f"  {key}: {value}")
        except ProtocolError as error:
            self.output(f"  invalid VRX packet: {error}")

    def handle_osd_datagram(
        self,
        data: bytes,
        source: tuple[str, int],
    ) -> None:
        """Reassemble, parse, and print MSP frames received on OSD UDP."""
        self._last_osd_data_time = self.monotonic_fn()
        self._set_osd_status(f"OSD={source[1]}")
        self.output(
            f"OSD RX <- {source[0]}:{source[1]} len={len(data)}  "
            f"{data.hex(' ').upper()}"
        )

        complete_frames = self.osd_reassembler.append(data)
        if not complete_frames:
            self.output(
                "  MSP buffered: "
                f"{self.osd_reassembler.buffered_byte_count} byte(s)"
            )
            return

        parsed, result = MspOsdParser.try_parse(complete_frames)
        for frame in result.frames:
            self.output(
                f"  MSP {frame.version.value} direction={frame.direction} "
                f"command=0x{frame.command:04X} "
                f"payload_len={len(frame.payload)} "
                f"checksum=0x{frame.checksum:02X} "
                f"calculated=0x{frame.calculated_checksum:02X} "
                f"ok={frame.checksum_ok}"
            )

        for command in result.display_port_commands:
            self.output(self._format_display_port_command(command))

        for issue in result.issues:
            self.output(
                f"  MSP {issue.severity.value}: {issue.category} "
                f"offset={issue.offset} message={issue.message}"
            )

        if not parsed and not result.issues:
            self.output("  no MSP frame parsed")

    @staticmethod
    def _format_display_port_command(
        command: MspDisplayPortCommand,
    ) -> str:
        name = command.subcommand.name
        if command.subcommand is MspDisplayPortSubcommand.WRITE_STRING:
            characters = (command.characters or b"").hex(" ").upper()
            return (
                f"  DISPLAYPORT {name} row={command.row} "
                f"column={command.column} attribute=0x{command.attribute:02X} "
                f"characters={characters}"
            )
        if command.subcommand is MspDisplayPortSubcommand.OPTIONS:
            return (
                f"  DISPLAYPORT {name} font={command.font} mode={command.mode}"
            )
        return f"  DISPLAYPORT {name}"

    def listen_forever(self) -> None:
        """Monitor both sockets until interrupted with Ctrl+C."""
        control_socket = self.control_channel.socket
        osd_socket = self.osd_channel.socket
        if control_socket is None or osd_socket is None:
            raise OSError("both UDP channels must be started before listening")

        self.output("Listening on Ctrl and OSD UDP. Press Ctrl+C to stop.")
        while True:
            readable, _, _ = self.select_fn(
                [control_socket, osd_socket], [], [], 0.5
            )
            for ready_socket in readable:
                if ready_socket is control_socket:
                    data, source = self.control_channel.receive()
                    self.handle_control_datagram(data, source)
                elif ready_socket is osd_socket:
                    data, source = self.osd_channel.receive()
                    self.handle_osd_datagram(data, source)

            if (
                self._last_osd_data_time is not None
                and self.monotonic_fn() - self._last_osd_data_time
                > OSD_NO_DATA_TIMEOUT_SECONDS
            ):
                self._set_osd_status("OSD=No rec")

    def run(self, *, send_mode_switch: bool = True) -> None:
        """Start, listen, and always close both UDP channels."""
        try:
            self.start(send_mode_switch=send_mode_switch)
            self.listen_forever()
        except KeyboardInterrupt:
            self.output("Stopped dual UDP listener.")
        finally:
            self.close()

    def _set_osd_status(self, status: str) -> None:
        if status != self._osd_status:
            self._osd_status = status
            self.output(status)

    def close(self) -> None:
        """Close both sockets and discard an incomplete MSP tail."""
        self.control_channel.close()
        self.osd_channel.close()
        self.osd_reassembler.reset()
        self._last_osd_data_time = None
        self._set_osd_status("OSD=disconnect")


class UdpVrxClient:
    """Send VRX UDP datagrams and continuously decode received datagrams."""

    def __init__(self, host: str, port: int, sock: socket.socket | None = None):
        """Initialize a UDP client for one VRX endpoint.

        Args:
            host: Destination IPv4 address or resolvable host name.
            port: Destination UDP port from 0 through 65535.
            sock: Optional socket-compatible object, primarily for testing.

        Raises:
            ValueError: If ``port`` is outside the valid UDP port range.
        """
        if not 0 <= port <= 65535:
            raise ValueError("port must be from 0 to 65535")
        self.address = (host, port)
        self.socket = (
            sock
            if sock is not None
            else socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        )

    def send(self, packet: bytes) -> None:
        """Send a complete protocol packet to the configured endpoint.

        Args:
            packet: Fully assembled protocol frame to transmit.

        Raises:
            OSError: If the operating system cannot send the UDP datagram.
        """
        print(f"TX -> {self.address[0]}:{self.address[1]}  {packet.hex(' ').upper()}")
        self.socket.sendto(packet, self.address)

    @staticmethod
    def print_received_datagram(data: bytes, source: tuple[str, int]) -> None:
        """Print and decode one received UDP datagram.

        Args:
            data: Raw datagram bytes received from the socket.
            source: Source host and port reported by ``recvfrom``.

        Invalid protocol packets are reported without terminating the listener.
        """
        print(f"RX <- {source[0]}:{source[1]}  {data.hex(' ').upper()}")
        try:
            command, payload = parse_packet(data)
            decoded = decode_payload(payload)
            print(f"  command: 0x{command:02X}")
            for key, value in decoded.items():
                print(f"  {key}: {value}")
        except ProtocolError as error:
            print(f"  invalid packet: {error}")

    def listen_forever(self) -> None:
        """Continuously receive and display UDP responses.

        The loop ends cleanly when the user presses ``Ctrl+C``. Malformed
        datagrams are reported by :meth:`print_received_datagram` and do not
        stop subsequent reception.
        """
        print("Listening for UDP responses. Press Ctrl+C to stop.")
        try:
            while True:
                data, source = self.socket.recvfrom(MAX_PAYLOAD_LENGTH + 9)
                self.print_received_datagram(data, source)
        except KeyboardInterrupt:
            print("Stopped listening.")

    def control_from_keyboard(self) -> None:
        """Run interactive keyboard control while receiving UDP responses.

        The method polls Windows console input and the UDP socket in the same
        loop. Mapped keys are converted into simulated VRX key packets. The
        loop ends when the user presses ``Q`` or ``Ctrl+C``.

        Raises:
            OSError: If Windows console input is unavailable or socket polling
                fails.
        """
        try:
            import msvcrt
        except ImportError as error:
            raise OSError("keyboard mode currently requires Windows") from error

        print("Keyboard control started:")
        print("  Arrows/WASD=move, Enter/E=confirm, Backspace=back")
        print("  P=pairing, U=upgrade, R=recording, Q=quit")

        try:
            while True:
                if msvcrt.kbhit():
                    character = msvcrt.getwch()
                    extended = character in ("\x00", "\xe0")
                    if extended:
                        character = msvcrt.getwch()

                    action = keyboard_input_to_action(character, extended=extended)
                    if action == "quit":
                        print("Stopped keyboard control.")
                        return
                    if action is not None:
                        key_number, press_type = KEYS[action]
                        payload = bytes([0x40, key_number, press_type, 0x00])
                        print(f"Key: {action}")
                        self.send(assemble_packet(WRITE_COMMAND, payload))

                readable, _, _ = select.select([self.socket], [], [], 0.05)
                if readable:
                    data, source = self.socket.recvfrom(MAX_PAYLOAD_LENGTH + 9)
                    self.print_received_datagram(data, source)
        except KeyboardInterrupt:
            print("Stopped keyboard control.")

    def close(self) -> None:
        """Close the UDP socket and release its operating-system resources."""
        self.socket.close()


def main(argv: list[str] | None = None) -> int:
    """Run the VRX UDP command-line client.

    Args:
        argv: Optional argument list used instead of ``sys.argv[1:]``. This is
            useful for tests and embedded callers.

    Returns:
        ``0`` after normal completion or ``1`` after a UDP/console error.

    When launched without arguments, the function prints command help and
    exits successfully. Packet operations use Ctrl UDP, while the ``osd``
    operation starts and monitors independent Ctrl and OSD channels.
    """
    parser = create_argument_parser()
    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        parser.print_help()
        return 0

    args = parser.parse_args(arguments)
    profile = resolve_connection_profile(args)

    if args.operation == "osd":
        session = DualUdpVrxSession(
            profile.host,
            profile.ctrl_port,
            profile.osd_port,
        )
        try:
            session.run(send_mode_switch=not args.no_mode_switch)
        except OSError as error:
            print(f"UDP error: {error}", file=sys.stderr)
            return 1
        return 0

    client = UdpVrxClient(profile.host, profile.ctrl_port)
    try:
        if args.operation == "keyboard":
            client.control_from_keyboard()
        else:
            command, payload = build_command_payload(args)
            packet = assemble_packet(command, payload)
            client.send(packet)
            client.listen_forever()
    except OSError as error:
        print(f"UDP error: {error}", file=sys.stderr)
        return 1
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
