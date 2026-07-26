import { useEffect, useRef, useState } from "react";
import type { ChatState } from "../useDashboardSocket";
import type { ProposalView } from "../types";
import { theme } from "../theme";
import { Button } from "./ui/Button";
import { Panel } from "./ui/Panel";

export function ChatDrawer({ chat, proposal, onChat, onConfirm, onCancel }: {
  chat: ChatState;
  proposal: ProposalView | null;
  onChat: (text: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => { endRef.current?.scrollIntoView?.({ block: "end" }); }, [chat.messages, chat.streaming, proposal]);

  const submit = () => {
    const t = text.trim();
    if (!t) return;
    onChat(t);
    setText("");
  };

  return (
    <Panel style={{ display: "flex", flexDirection: "column", maxHeight: "70vh", overflow: "hidden" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: 10, display: "flex", flexDirection: "column", gap: 8 }}>
        {chat.messages.map((m, i) => {
          const mine = m.role === "user";
          return (
            <div key={i} style={{ alignSelf: mine ? "flex-end" : "flex-start", maxWidth: "85%" }}>
              {!mine && m.thinking ? (
                <details style={{ marginBottom: 4, color: theme.color.dim, fontSize: 11 }}>
                  <summary style={{ cursor: "pointer" }}>reasoning</summary>
                  <div style={{ whiteSpace: "pre-wrap", fontFamily: theme.font.mono, opacity: 0.8 }}>{m.thinking}</div>
                </details>
              ) : null}
              <div style={{
                background: mine ? "#1c2a3c" : "#13202e",
                border: `1px solid ${theme.color.border}`, borderRadius: theme.radius.md,
                padding: "7px 10px", fontSize: 13, whiteSpace: "pre-wrap",
                color: theme.color.text }}>
                {m.reply}
              </div>
            </div>
          );
        })}
        {chat.streaming ? (
          <div style={{ alignSelf: "flex-start", color: theme.color.accent, fontSize: 12, opacity: 0.8 }}>
            thinking…
          </div>
        ) : null}
        <div ref={endRef} />
      </div>

      {proposal ? (
        <div style={{ borderTop: `1px solid ${theme.color.border}`, padding: 10, background: "#0d1622" }}>
          {proposal.say ? <div style={{ fontSize: 12, marginBottom: 6, color: theme.color.dim }}>{proposal.say}</div> : null}
          <pre style={{ margin: 0, fontSize: 11, fontFamily: theme.font.mono, color: theme.color.text,
            background: "#0a131d", border: `1px solid ${theme.color.border}`, borderRadius: theme.radius.sm,
            padding: 8, overflowX: "auto" }}>{JSON.stringify(proposal.command, null, 2)}</pre>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <Button variant="accent" onClick={onConfirm}>Confirm</Button>
            <Button onClick={onCancel}>Cancel</Button>
          </div>
        </div>
      ) : null}

      <div style={{ display: "flex", gap: 8, padding: 10, borderTop: `1px solid ${theme.color.border}` }}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
          placeholder="Type a command…"
          style={{ flex: 1, padding: "8px 10px", background: "#0a131d", color: theme.color.text,
            border: `1px solid ${theme.color.border}`, borderRadius: theme.radius.sm, fontSize: 13 }}
        />
        <Button variant="accent" onClick={submit}>Send</Button>
      </div>
    </Panel>
  );
}
