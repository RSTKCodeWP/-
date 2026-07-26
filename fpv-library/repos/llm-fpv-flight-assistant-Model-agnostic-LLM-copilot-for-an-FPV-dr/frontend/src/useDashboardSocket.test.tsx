import { reduceMessage, type ChatState, emptyChat } from "./useDashboardSocket";

test("assembles a streaming assistant turn", () => {
  let s: ChatState = emptyChat;
  s = reduceMessage(s, { type: "chat_start" });
  s = reduceMessage(s, { type: "chat_delta", kind: "thinking", text: "hmm" });
  s = reduceMessage(s, { type: "chat_delta", kind: "reply", text: "Holding" });
  s = reduceMessage(s, { type: "chat_end" });
  const last = s.messages[s.messages.length - 1];
  expect(last.role).toBe("assistant");
  expect(last.reply).toBe("Holding");
  expect(last.thinking).toBe("hmm");
  expect(s.streaming).toBe(false);
});

test("user echo + control state", () => {
  let s = reduceMessage(emptyChat, { type: "__user", text: "go" });
  expect(s.messages[0]).toEqual(expect.objectContaining({ role: "user", reply: "go" }));
});
