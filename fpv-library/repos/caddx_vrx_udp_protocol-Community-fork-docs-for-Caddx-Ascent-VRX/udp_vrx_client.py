"""Command-line UDP client for the Ascent VRX packet protocol."""

from __future__ import annotations

import argparse
import select
import socket
import sys

HEADER = bytes.fromhex("FE EF")
TAIL = bytes.fromhex("0D 0A")
MAX_PAYLOAD_LENGTH = 0xFFFF


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


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the command-line argument parser.

    Returns:
        A parser containing the destination options and every supported VRX
        operation, including interactive keyboard control.
    """
    parser = argparse.ArgumentParser(description="Ascent VRX UDP protocol client")
    parser.add_argument("--host", default="192.168.1.100", help="UDP server address")
    parser.add_argument("--port", default=9001, type=int, help="UDP server port")
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
    return parser


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
    exits successfully. Packet operations send one request and then listen for
    responses; the keyboard operation enters interactive control mode.
    """
    parser = create_argument_parser()
    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        parser.print_help()
        return 0

    args = parser.parse_args(arguments)
    client = UdpVrxClient(args.host, args.port)
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
