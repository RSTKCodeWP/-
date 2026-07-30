"""MSP frame reassembly and MSP_DISPLAYPORT parsing.

This module is a Python port of the parsing-only portion of the
GroundConfiguration MSP OSD pipeline. It has no network, UI, font, or rendering
dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum


class MspOsdFrameVersion(Enum):
    """Supported MSP wire-format versions."""

    V1 = "v1"
    V2 = "v2"


class MspOsdIssueSeverity(Enum):
    """Severity assigned to a recoverable parse issue."""

    WARNING = "warning"
    ERROR = "error"


class MspDisplayPortSubcommand(IntEnum):
    """Standard MSP_DISPLAYPORT subcommands."""

    HEARTBEAT = 0
    RELEASE = 1
    CLEAR_SCREEN = 2
    WRITE_STRING = 3
    DRAW_SCREEN = 4
    OPTIONS = 5
    SYS = 6


@dataclass(frozen=True)
class MspOsdParseIssue:
    """A warning or error tied to an offset in the original byte stream."""

    offset: int
    severity: MspOsdIssueSeverity
    category: str
    message: str


@dataclass(frozen=True)
class MspOsdFrame:
    """A complete parsed MSP frame, including received and calculated checksums."""

    version: MspOsdFrameVersion
    direction: str
    offset: int
    total_length: int
    flags: int = 0
    command: int = 0
    payload: bytes = b""
    checksum: int = 0
    calculated_checksum: int = 0

    @property
    def checksum_ok(self) -> bool:
        """Whether the received checksum matches the calculated checksum."""

        return self.checksum == self.calculated_checksum


@dataclass(frozen=True)
class MspDisplayPortCommand:
    """A validated, decoded MSP_DISPLAYPORT subcommand."""

    subcommand: MspDisplayPortSubcommand
    row: int = 0
    column: int = 0
    attribute: int = 0
    characters: bytes | None = None
    font: int = 0
    mode: int = 0


@dataclass
class MspOsdParseResult:
    """Frames, DisplayPort commands, and issues produced by one parse call."""

    frames: list[MspOsdFrame] = field(default_factory=list)
    display_port_commands: list[MspDisplayPortCommand] = field(
        default_factory=list
    )
    issues: list[MspOsdParseIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Whether any parse issue has error severity."""

        return any(
            issue.severity is MspOsdIssueSeverity.ERROR
            for issue in self.issues
        )


class MspParseError(ValueError):
    """Raised by strict parsing when any warning or error is encountered."""


class MspFrameReassembler:
    """Reassemble complete MSP v1/v2 frames across arbitrary byte chunks.

    The reassembler recognizes only frame boundaries. It does not validate
    checksums or interpret payloads. Instances are stateful and not thread-safe.
    """

    DEFAULT_MAX_BUFFER_BYTES = 8 * 1024

    _FRAME_HEADER = 0x24
    _MARKER_V1 = 0x4D
    _MARKER_V2 = 0x58
    _V1_OVERHEAD = 6
    _V2_OVERHEAD = 9

    def __init__(self, max_buffer_bytes: int = DEFAULT_MAX_BUFFER_BYTES):
        if max_buffer_bytes <= 0:
            raise ValueError("max_buffer_bytes must be greater than zero")

        self._max_buffer_bytes = max_buffer_bytes
        self._buffer = bytearray()

    @property
    def max_buffer_bytes(self) -> int:
        """Maximum number of incomplete bytes retained between calls."""

        return self._max_buffer_bytes

    @property
    def buffered_byte_count(self) -> int:
        """Number of incomplete bytes currently retained."""

        return len(self._buffer)

    def append(self, data: bytes | bytearray | memoryview | None) -> bytes:
        """Append bytes and return the complete-frame span in original order.

        For parity with the C# implementation, garbage between the first and
        last complete frames remains in the returned span. Leading garbage and
        incomplete trailing bytes are not emitted.
        """

        if data:
            self._buffer.extend(data)

        length = len(self._buffer)
        scan = 0
        emit_start = -1
        emit_end = 0
        tail_start = 0

        while scan < length:
            if self._buffer[scan] != self._FRAME_HEADER:
                scan += 1
                tail_start = scan
                continue

            if length - scan < 3:
                break

            marker = self._buffer[scan + 1]
            if marker == self._MARKER_V1:
                if length - scan < 4:
                    break
                total_length = self._V1_OVERHEAD + self._buffer[scan + 3]
            elif marker == self._MARKER_V2:
                if length - scan < 8:
                    break
                payload_length = (
                    self._buffer[scan + 6]
                    | (self._buffer[scan + 7] << 8)
                )
                total_length = self._V2_OVERHEAD + payload_length
            else:
                scan += 1
                tail_start = scan
                continue

            if length - scan < total_length:
                break

            if emit_start < 0:
                emit_start = scan
            scan += total_length
            emit_end = scan
            tail_start = scan

        if emit_start >= 0 and emit_end > emit_start:
            complete = bytes(self._buffer[emit_start:emit_end])
        else:
            complete = b""

        if tail_start > 0:
            del self._buffer[:tail_start]

        if len(self._buffer) > self._max_buffer_bytes:
            self._buffer.clear()

        return complete

    def reset(self) -> None:
        """Discard all retained incomplete bytes."""

        self._buffer.clear()


class MspOsdParser:
    """Parse complete MSP v1/v2 frames and validated DisplayPort payloads."""

    MSP_DISPLAYPORT_COMMAND = 0xB6
    _FULL_FRAME_SUBCOMMAND = 0x35

    @classmethod
    def try_parse(
        cls,
        data: bytes | bytearray | memoryview,
    ) -> tuple[bool, MspOsdParseResult]:
        """Parse a byte stream without raising for malformed MSP data.

        The boolean is true when at least one complete MSP frame was read.
        Warnings and errors are retained in the returned result.
        """

        raw = cls._coerce_data(data)
        result = MspOsdParseResult()
        offset = 0

        while offset < len(raw):
            if raw[offset] != 0x24:
                cls._add_issue(
                    result,
                    offset,
                    MspOsdIssueSeverity.WARNING,
                    "UnexpectedByte",
                    "Expected '$'.",
                )
                offset += 1
                continue

            if offset + 2 >= len(raw):
                cls._add_issue(
                    result,
                    offset,
                    MspOsdIssueSeverity.ERROR,
                    "IncompleteHeader",
                    "Incomplete MSP header.",
                )
                break

            marker = raw[offset + 1]
            if marker == 0x4D:
                frame = cls._try_read_v1_frame(raw, offset, result)
            elif marker == 0x58:
                frame = cls._try_read_v2_frame(raw, offset, result)
            else:
                cls._add_issue(
                    result,
                    offset,
                    MspOsdIssueSeverity.WARNING,
                    "UnsupportedMarker",
                    "Unsupported MSP marker.",
                )
                offset += 1
                continue

            if frame is None:
                break

            result.frames.append(frame)
            if not frame.checksum_ok:
                cls._add_issue(
                    result,
                    frame.offset,
                    MspOsdIssueSeverity.ERROR,
                    "InvalidChecksum",
                    "Invalid MSP checksum.",
                )
            elif frame.command == cls.MSP_DISPLAYPORT_COMMAND:
                cls._parse_display_port(frame, result)

            offset += frame.total_length

        return bool(result.frames), result

    @classmethod
    def parse(
        cls,
        data: bytes | bytearray | memoryview,
    ) -> MspOsdParseResult:
        """Parse a byte stream and raise if any warning or error is found."""

        _, result = cls.try_parse(data)
        if result.issues:
            issue = result.issues[0]
            raise MspParseError(
                f"MSP parse error at offset {issue.offset}: {issue.message}"
            )
        return result

    @staticmethod
    def _coerce_data(data: bytes | bytearray | memoryview) -> bytes:
        if data is None:
            raise TypeError("data must not be None")
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("data must be bytes-like")
        return bytes(data)

    @classmethod
    def _try_read_v1_frame(
        cls,
        data: bytes,
        offset: int,
        result: MspOsdParseResult,
    ) -> MspOsdFrame | None:
        if offset + 6 > len(data):
            cls._add_issue(
                result,
                offset,
                MspOsdIssueSeverity.ERROR,
                "IncompleteHeader",
                "Incomplete MSP v1 header.",
            )
            return None

        payload_length = data[offset + 3]
        total_length = 6 + payload_length
        if offset + total_length > len(data):
            cls._add_issue(
                result,
                offset,
                MspOsdIssueSeverity.ERROR,
                "TruncatedFrame",
                "Truncated MSP v1 frame.",
            )
            return None

        return MspOsdFrame(
            version=MspOsdFrameVersion.V1,
            direction=chr(data[offset + 2]),
            offset=offset,
            total_length=total_length,
            command=data[offset + 4],
            payload=bytes(data[offset + 5 : offset + 5 + payload_length]),
            checksum=data[offset + total_length - 1],
            calculated_checksum=cls._xor(
                data,
                offset + 3,
                payload_length + 2,
            ),
        )

    @classmethod
    def _try_read_v2_frame(
        cls,
        data: bytes,
        offset: int,
        result: MspOsdParseResult,
    ) -> MspOsdFrame | None:
        if offset + 9 > len(data):
            cls._add_issue(
                result,
                offset,
                MspOsdIssueSeverity.ERROR,
                "IncompleteHeader",
                "Incomplete MSP v2 header.",
            )
            return None

        payload_length = data[offset + 6] | (data[offset + 7] << 8)
        total_length = 9 + payload_length
        if offset + total_length > len(data):
            cls._add_issue(
                result,
                offset,
                MspOsdIssueSeverity.ERROR,
                "TruncatedFrame",
                "Truncated MSP v2 frame.",
            )
            return None

        return MspOsdFrame(
            version=MspOsdFrameVersion.V2,
            direction=chr(data[offset + 2]),
            offset=offset,
            total_length=total_length,
            flags=data[offset + 3],
            command=data[offset + 4] | (data[offset + 5] << 8),
            payload=bytes(data[offset + 8 : offset + 8 + payload_length]),
            checksum=data[offset + total_length - 1],
            calculated_checksum=cls._crc8_dvb_s2(
                data,
                offset + 3,
                payload_length + 5,
            ),
        )

    @classmethod
    def _parse_display_port(
        cls,
        frame: MspOsdFrame,
        result: MspOsdParseResult,
    ) -> None:
        payload = frame.payload
        if not payload:
            cls._add_issue(
                result,
                cls._payload_offset(frame),
                MspOsdIssueSeverity.ERROR,
                "DisplayPortTooShort",
                "MSP_DISPLAYPORT payload does not contain a subcommand.",
            )
            return

        if payload[0] == cls._FULL_FRAME_SUBCOMMAND:
            cls._parse_full_frame_display_port(frame, result)
            return

        try:
            subcommand = MspDisplayPortSubcommand(payload[0])
        except ValueError:
            cls._add_issue(
                result,
                cls._payload_offset(frame),
                MspOsdIssueSeverity.WARNING,
                "UnsupportedDisplayPortSubcommand",
                "Unsupported MSP_DISPLAYPORT subcommand.",
            )
            return

        if subcommand in (
            MspDisplayPortSubcommand.HEARTBEAT,
            MspDisplayPortSubcommand.RELEASE,
            MspDisplayPortSubcommand.CLEAR_SCREEN,
            MspDisplayPortSubcommand.DRAW_SCREEN,
            MspDisplayPortSubcommand.SYS,
        ):
            result.display_port_commands.append(
                MspDisplayPortCommand(subcommand=subcommand)
            )
            return

        if subcommand is MspDisplayPortSubcommand.WRITE_STRING:
            if len(payload) < 4:
                cls._add_issue(
                    result,
                    cls._payload_offset(frame),
                    MspOsdIssueSeverity.ERROR,
                    "DisplayPortTooShort",
                    "MSP_DISPLAYPORT WRITE_STRING requires row, column "
                    "and attribute.",
                )
                return

            result.display_port_commands.append(
                MspDisplayPortCommand(
                    subcommand=subcommand,
                    row=payload[1],
                    column=payload[2],
                    attribute=payload[3],
                    characters=bytes(payload[4:]),
                )
            )
            return

        if subcommand is MspDisplayPortSubcommand.OPTIONS:
            if len(payload) < 3:
                cls._add_issue(
                    result,
                    cls._payload_offset(frame),
                    MspOsdIssueSeverity.ERROR,
                    "DisplayPortTooShort",
                    "MSP_DISPLAYPORT OPTIONS requires font and mode.",
                )
                return

            result.display_port_commands.append(
                MspDisplayPortCommand(
                    subcommand=subcommand,
                    font=payload[1],
                    mode=payload[2],
                )
            )

    @classmethod
    def _parse_full_frame_display_port(
        cls,
        frame: MspOsdFrame,
        result: MspOsdParseResult,
    ) -> None:
        payload = frame.payload
        if len(payload) < 3:
            cls._add_issue(
                result,
                cls._payload_offset(frame),
                MspOsdIssueSeverity.ERROR,
                "DisplayPortTooShort",
                "MSP_DISPLAYPORT full frame is shorter than its prefix.",
            )
            return

        index = 3
        while index < len(payload):
            segment_length = payload[index]
            issue_offset = cls._payload_offset(frame) + index
            if segment_length < 4:
                cls._add_issue(
                    result,
                    issue_offset,
                    MspOsdIssueSeverity.ERROR,
                    "InvalidDisplayPortSegmentLength",
                    "MSP_DISPLAYPORT full-frame segment length is less "
                    "than 4.",
                )
                return

            if index + segment_length > len(payload):
                cls._add_issue(
                    result,
                    issue_offset,
                    MspOsdIssueSeverity.ERROR,
                    "TruncatedDisplayPortSegment",
                    "MSP_DISPLAYPORT full-frame segment extends past "
                    "the payload.",
                )
                return

            result.display_port_commands.append(
                MspDisplayPortCommand(
                    subcommand=MspDisplayPortSubcommand.WRITE_STRING,
                    row=payload[index + 1],
                    column=payload[index + 2],
                    attribute=payload[index + 3],
                    characters=bytes(
                        payload[index + 4 : index + segment_length]
                    ),
                )
            )
            index += segment_length

        result.display_port_commands.append(
            MspDisplayPortCommand(
                subcommand=MspDisplayPortSubcommand.DRAW_SCREEN
            )
        )

    @staticmethod
    def _payload_offset(frame: MspOsdFrame) -> int:
        overhead = 5 if frame.version is MspOsdFrameVersion.V1 else 8
        return frame.offset + overhead

    @staticmethod
    def _add_issue(
        result: MspOsdParseResult,
        offset: int,
        severity: MspOsdIssueSeverity,
        category: str,
        message: str,
    ) -> None:
        result.issues.append(
            MspOsdParseIssue(
                offset=offset,
                severity=severity,
                category=category,
                message=f"{message} Offset {offset}.",
            )
        )

    @staticmethod
    def _xor(data: bytes, offset: int, count: int) -> int:
        value = 0
        for byte in data[offset : offset + count]:
            value ^= byte
        return value

    @staticmethod
    def _crc8_dvb_s2(data: bytes, offset: int, count: int) -> int:
        crc = 0
        for byte in data[offset : offset + count]:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ 0xD5) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
        return crc
