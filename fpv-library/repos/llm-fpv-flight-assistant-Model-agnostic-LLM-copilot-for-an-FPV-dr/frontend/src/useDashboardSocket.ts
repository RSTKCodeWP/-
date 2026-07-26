import { useEffect, useRef, useState, useCallback } from "react";
import type { Telemetry, VideoStatus, ControlWho, ChatMessage, ProposalView, EventEntry } from "./types";

export interface ChatState { messages: ChatMessage[]; streaming: boolean; }
export const emptyChat: ChatState = { messages: [], streaming: false };

export function reduceMessage(s: ChatState, m: any): ChatState {
  switch (m.type) {
    case "__user":
      return { ...s, messages: [...s.messages, { role: "user", reply: m.text }] };
    case "chat_start":
      return { ...s, streaming: true, messages: [...s.messages, { role: "assistant", reply: "", thinking: "" }] };
    case "chat_delta": {
      const msgs = s.messages.slice(); const last = { ...msgs[msgs.length - 1] };
      if (m.kind === "reply") last.reply += m.text; else last.thinking = (last.thinking || "") + m.text;
      msgs[msgs.length - 1] = last; return { ...s, messages: msgs };
    }
    case "chat_end":
      return { ...s, streaming: false };
    default:
      return s;
  }
}

export function useDashboardSocket(url: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [chat, setChat] = useState<ChatState>(emptyChat);
  const [proposal, setProposal] = useState<ProposalView | null>(null);
  const [control, setControl] = useState<ControlWho>("assistant");
  const [videoStatus, setVideoStatus] = useState<VideoStatus | null>(null);
  const [events, setEvents] = useState<EventEntry[]>([]);
  const logEvent = (kind: string, text: string) =>
    setEvents((e) => [...e.slice(-199), { ts: Date.now(), kind, text }]);

  useEffect(() => {
    const ws = new WebSocket(url); wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      switch (m.type) {
        case "telemetry": setTelemetry(m.data); break;
        case "video_status": setVideoStatus({ ok: m.ok, url: m.url }); break;
        case "control_state": setControl(m.who); logEvent("control", `control: ${m.who}`); break;
        case "proposal": setProposal({ command: m.command, say: m.say }); logEvent("proposal", m.say || JSON.stringify(m.command)); break;
        case "result": setProposal(null); logEvent("result", `${m.status} ${m.verb || ""}`.trim()); break;
        case "narration": logEvent("narration", m.text); setChat((s) => reduceMessage(reduceMessage(s, { type: "chat_start" }), { type: "chat_delta", kind: "reply", text: m.text })); setChat((s) => reduceMessage(s, { type: "chat_end" })); break;
        case "chat_start": case "chat_delta": case "chat_end": setChat((s) => reduceMessage(s, m)); break;
      }
    };
    return () => ws.close();
  }, [url]);

  const send = useCallback((o: unknown) => wsRef.current?.send(JSON.stringify(o)), []);
  const sendChat = useCallback((text: string) => { setChat((s) => reduceMessage(s, { type: "__user", text })); send({ type: "chat", text }); }, [send]);
  const confirm = useCallback(() => { setProposal(null); send({ type: "confirm" }); }, [send]);
  const cancel = useCallback(() => { setProposal(null); send({ type: "cancel" }); }, [send]);
  const abort = useCallback(() => send({ type: "abort" }), [send]);
  const takeControl = useCallback(() => send({ type: "take_control" }), [send]);
  const release = useCallback(() => send({ type: "release_control" }), [send]);
  const quick = useCallback((verb: string, args?: object) => send({ type: "quick", verb, args: args || {} }), [send]);
  const sendManual = useCallback((forward: number, right: number, down: number, yaw_rate: number) =>
    send({ type: "manual", forward, right, down, yaw_rate }), [send]);

  return { connected, telemetry, chat, proposal, control, videoStatus, events,
           sendChat, confirm, cancel, abort, takeControl, release, quick, sendManual };
}
