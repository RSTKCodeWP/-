/**
 * FILE_TRANSFER_PROTOCOL (ID 110) message decoder and opcode constants.
 *
 * MAVLink FTP is a session-based file access protocol. The GCS opens a file
 * for reading, streams its contents in bursts, optionally verifies a CRC-32,
 * and terminates the session. Every response is an ACK or NAK whose req_opcode
 * echoes the request being answered.
 *
 * @module protocol/messages/ftp
 */

/**
 * FTP opcodes per the MAVLink file-transfer specification.
 *
 * The numeric values follow the specification exactly. The read path uses
 * Terminate=1, ListDirectory=3, OpenFileRO=4, ReadFile=5, CalcFileCRC32=14,
 * BurstReadFile=15. The write path (used only for deliberate operator-initiated
 * uploads/deletes, e.g. Lua script management) uses CreateFile=6, WriteFile=7,
 * RemoveFile=8, and CreateDirectory=9. CalcFileCRC32 is 14, not 8; opcode 8 is
 * RemoveFile.
 */
export const FtpOpcode = {
  None: 0,
  TerminateSession: 1,
  ResetSessions: 2,
  ListDirectory: 3,
  OpenFileRO: 4,
  ReadFile: 5,
  CreateFile: 6,
  WriteFile: 7,
  RemoveFile: 8,
  CreateDirectory: 9,
  RemoveDirectory: 10,
  OpenFileWO: 11,
  TruncateFile: 12,
  Rename: 13,
  CalcFileCRC32: 14,
  BurstReadFile: 15,
  Ack: 128,
  Nak: 129,
} as const;

/**
 * FTP NAK error codes carried in data[0] of a NAK response.
 * EOF is the expected terminator of a successful read.
 */
export const FtpError = {
  None: 0,
  Fail: 1,
  FailErrno: 2,
  InvalidDataSize: 3,
  InvalidSession: 4,
  NoSessionsAvailable: 5,
  EndOfFile: 6,
  UnknownCommand: 7,
  FileExists: 8,
  FileProtected: 9,
  FileNotFound: 10,
} as const;

/** Human-readable label for a NAK error code. */
export function ftpErrorName(code: number): string {
  switch (code) {
    case FtpError.None: return "None";
    case FtpError.Fail: return "Fail";
    case FtpError.FailErrno: return "FailErrno";
    case FtpError.InvalidDataSize: return "InvalidDataSize";
    case FtpError.InvalidSession: return "InvalidSession";
    case FtpError.NoSessionsAvailable: return "NoSessionsAvailable";
    case FtpError.EndOfFile: return "EndOfFile";
    case FtpError.UnknownCommand: return "UnknownCommand";
    case FtpError.FileExists: return "FileExists";
    case FtpError.FileProtected: return "FileProtected";
    case FtpError.FileNotFound: return "FileNotFound";
    default: return `Unknown(${code})`;
  }
}

export interface FileTransferProtocolMsg {
  targetNetwork: number;
  targetSystem: number;
  targetComponent: number;
  seq: number;
  session: number;
  opcode: number;
  size: number;
  reqOpcode: number;
  burstComplete: number;
  offset: number;
  /** Full 239-byte data field. Valid bytes = the first `size` on ACK/NAK. */
  data: Uint8Array;
}

/** Offset of the FTP inner payload inside the outer message payload. */
const FTP_INNER_OFFSET = 3;
/** FTP inner-payload header size (bytes). */
const FTP_HEADER_SIZE = 12;
/** Maximum data bytes carried in one FTP payload. */
const FTP_MAX_DATA = 239;

/**
 * Decode FILE_TRANSFER_PROTOCOL (msg ID 110).
 *
 * Outer fields (target_network/system/component) occupy bytes 0-2; the inner
 * FTP payload starts at byte 3. The 239-byte data field is copied out so the
 * caller can retain it past the parser's rolling buffer.
 */
export function decodeFileTransferProtocol(dv: DataView): FileTransferProtocolMsg {
  const base = FTP_INNER_OFFSET;
  const data = new Uint8Array(FTP_MAX_DATA);
  const dataStart = base + FTP_HEADER_SIZE;
  for (let i = 0; i < FTP_MAX_DATA; i++) {
    data[i] = dv.getUint8(dataStart + i);
  }
  return {
    targetNetwork: dv.getUint8(0),
    targetSystem: dv.getUint8(1),
    targetComponent: dv.getUint8(2),
    seq: dv.getUint16(base + 0, true),
    session: dv.getUint8(base + 2),
    opcode: dv.getUint8(base + 3),
    size: dv.getUint8(base + 4),
    reqOpcode: dv.getUint8(base + 5),
    burstComplete: dv.getUint8(base + 6),
    offset: dv.getUint32(base + 8, true),
    data,
  };
}
