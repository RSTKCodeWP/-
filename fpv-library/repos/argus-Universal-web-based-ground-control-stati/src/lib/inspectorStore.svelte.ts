export interface MavMsg {
  id: number;
  name: string;
  hz: number;
  count: number;
  size: number;
  last_fields: Record<string, unknown>;
}

class InspectorState {
  messages: MavMsg[] = $state([]);
  paused: boolean = $state(false);
  enabled: boolean = $state(false);
  consoleLines: string[] = $state([]);
  consoleInput: string = $state('');
}

export const inspectorState = new InspectorState();

export function updateInspector(msgs: MavMsg[]) {
  if (!inspectorState.paused) {
    inspectorState.messages = msgs;
  }
}

export function appendConsole(text: string) {
  const lines = text.split('\n');
  for (const line of lines) {
    if (line) inspectorState.consoleLines.push(line);
  }
  if (inspectorState.consoleLines.length > 1000) {
    inspectorState.consoleLines.splice(0, inspectorState.consoleLines.length - 500);
  }
}
