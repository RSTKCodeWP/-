/**
 * @module protocol/msp/bf-cli.test
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { BfCliSession, type BfCliIo } from "../bf-cli";
import { BfCliSettings, parseDumpSettings, parseGetValue } from "../bf-cli-settings";

/** A scripted FC that answers each CLI command with prompt-terminated text. */
class FakeIo implements BfCliIo {
  sent: string[] = [];
  active: boolean[] = [];
  session!: BfCliSession;
  constructor(private readonly responder: (cmd: string) => string) {}
  send(bytes: Uint8Array): void {
    const cmd = new TextDecoder().decode(bytes).trim();
    this.sent.push(cmd);
    // Deliver synchronously so the prompt fast-path resolves without timers.
    this.session.feed(new TextEncoder().encode(this.responder(cmd)));
  }
  setActive(active: boolean): void {
    this.active.push(active);
  }
}

function makeSession(responder: (cmd: string) => string): { session: BfCliSession; io: FakeIo } {
  const io = new FakeIo(responder);
  const session = new BfCliSession(io);
  io.session = session;
  return { session, io };
}

describe("parseDumpSettings", () => {
  it("parses `set name = value` lines and ignores comments/dedupes", () => {
    const dump = [
      "# version",
      "# Betaflight / STM32F405",
      "set gyro_hardware_lpf = NORMAL",
      "set gyro_lpf1_static_hz = 250",
      "set motor_pwm_protocol = DSHOT600",
      "set gyro_hardware_lpf = NORMAL", // duplicate — kept once
      "feature -RX_PARALLEL_PWM",
      "# ",
    ].join("\n");
    const out = parseDumpSettings(dump);
    expect(out).toEqual([
      { name: "gyro_hardware_lpf", value: "NORMAL" },
      { name: "gyro_lpf1_static_hz", value: "250" },
      { name: "motor_pwm_protocol", value: "DSHOT600" },
    ]);
  });
});

describe("parseGetValue", () => {
  it("extracts the value line for a named setting", () => {
    const text = "gyro_hardware_lpf = NORMAL\nAllowed values: NORMAL, OPTION_1\n# ";
    expect(parseGetValue(text, "gyro_hardware_lpf")).toBe("NORMAL");
    expect(parseGetValue(text, "nonexistent")).toBeUndefined();
  });
});

describe("BfCliSession", () => {
  it("enters, runs a command, and exits without reboot", async () => {
    const { session, io } = makeSession((cmd) => {
      if (cmd === "#") return "Entering CLI Mode\r\n# ";
      if (cmd === "dump") return "set a = 1\r\nset b = 2\r\n# ";
      return "\r\n# ";
    });
    await session.enter();
    expect(session.isActive).toBe(true);
    const out = await session.run("dump");
    expect(out).toContain("set a = 1");
    await session.exit(false);
    expect(session.isActive).toBe(false);
    expect(io.sent).toEqual(["#", "dump", "exit noreboot"]);
    expect(io.active).toEqual([true, false]); // pauses then resumes MSP
  });

  it("persists with `save noreboot` when exiting with persist", async () => {
    const { session, io } = makeSession(() => "\r\n# ");
    await session.enter();
    await session.exit(true);
    expect(io.sent).toContain("save noreboot");
    expect(io.sent).not.toContain("save"); // exact command, not a bare save+reboot
  });

  it("streams inbound text in interactive mode and appends the command newline", () => {
    const streamed: string[] = [];
    const { session, io } = makeSession((cmd) => (cmd === "#" ? "Entering CLI\r\n# " : "output\r\n# "));
    session.attachInteractive((t) => streamed.push(t));
    expect(io.active).toEqual([true]); // pauses MSP polling on entry
    expect(io.sent).toEqual(["#"]);
    expect(streamed.join("")).toContain("Entering CLI"); // banner streamed to the terminal
    session.sendInteractive("version");
    expect(io.sent).toContain("version"); // command sent (newline appended by sendInteractive)
    expect(streamed.join("")).toContain("output");
    session.detachInteractive();
    expect(io.sent).toContain("exit noreboot");
    expect(io.active).toEqual([true, false]); // resumes MSP polling on exit
    expect(session.isActive).toBe(false);
  });
});

describe("BfCliSettings (cliSettings capability)", () => {
  it("enumerate() dumps and parses every setting", async () => {
    const { session } = makeSession((cmd) => {
      if (cmd === "#") return "# ";
      if (cmd === "dump") return "set gyro_hardware_lpf = NORMAL\r\nset acc_hardware = AUTO\r\n# ";
      return "\r\n# ";
    });
    const settings = await new BfCliSettings(session).enumerate();
    expect(settings).toEqual([
      { name: "gyro_hardware_lpf", value: "NORMAL" },
      { name: "acc_hardware", value: "AUTO" },
    ]);
  });

  it("applySettings() sets each change, persists, and reports success", async () => {
    const { session, io } = makeSession(() => "\r\n# ");
    const r = await new BfCliSettings(session).applySettings(
      [{ name: "gyro_hardware_lpf", value: "OPTION_1" }, { name: "motor_pwm_protocol", value: "DSHOT300" }],
      { persist: true },
    );
    expect(r.success).toBe(true);
    expect(io.sent).toEqual([
      "#",
      "set gyro_hardware_lpf = OPTION_1",
      "set motor_pwm_protocol = DSHOT300",
      "save noreboot",
      "exit noreboot",
    ]);
  });

  it("applySettings() flags a rejected setting", async () => {
    const { session } = makeSession((cmd) =>
      cmd.startsWith("set bad") ? "Invalid name\r\n# " : "\r\n# ",
    );
    const r = await new BfCliSettings(session).applySettings([{ name: "bad_name", value: "9" }]);
    expect(r.success).toBe(false);
    expect(r.message).toContain("bad_name");
  });

  it("applySettings() with no changes is a no-op success", async () => {
    const { session, io } = makeSession(() => "\r\n# ");
    const r = await new BfCliSettings(session).applySettings([]);
    expect(r.success).toBe(true);
    expect(io.sent).toEqual([]); // never enters the CLI
  });

  it("does not cut a dump short when a chunk ends at a mid-dump `#` comment", async () => {
    // A response streamed in pieces, one boundary landing right after a bare `#`
    // (a `# comment` split from its text) — the prompt grace must not resolve early.
    const io = new FakeIo(() => ""); // manual streaming below
    const session = new BfCliSession(io);
    io.session = session;
    const feed = (s: string) => session.feed(new TextEncoder().encode(s));
    // override send so `dump` streams asynchronously in chunks
    io.send = (bytes: Uint8Array) => {
      const cmd = new TextDecoder().decode(bytes).trim();
      io.sent.push(cmd);
      if (cmd === "#") { feed("# "); return; }
      if (cmd === "dump") {
        feed("set a = 1\r\n#"); // chunk ends at a bare `#` of a comment
        setTimeout(() => feed(" resource block\r\nset b = 2\r\nset c = 3\r\n# "), 20);
        return;
      }
      feed("\r\n# ");
    };
    const settings = await new BfCliSettings(session).enumerate();
    expect(settings.map((s) => s.name)).toEqual(["a", "b", "c"]); // all three, not just `a`
  });
});
