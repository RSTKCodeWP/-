import json
from dataclasses import dataclass
from pydantic import ValidationError
from flight_safety.models import parse_command

_VERB_HELP = """\
Allowed commands (emit ONE, with exact fields):
- arm_takeoff: {"verb":"arm_takeoff","alt":<m, 0-120>}
- goto: {"verb":"goto","lat":<deg>,"lon":<deg>,"alt":<m,0-120>}
- orbit: {"verb":"orbit","radius":<m,0-200>,"alt":<m,0-120>,"center":[<lat>,<lon>] or omit}
- loiter: {"verb":"loiter"}
- return_to_launch: {"verb":"return_to_launch"}
- land: {"verb":"land"}"""

_SYSTEM = f"""You are a UAV flight-command translator. First write ONE short sentence to the \
operator describing what you will do (or what you need). Then, on a NEW LINE, output ONLY a JSON \
object and nothing after it.
The JSON is either {{"action":"command","command":{{...}}}} using exactly one allowed command,
or {{"action":"ask","question":"..."}} if the request is ambiguous or missing required values.
{_VERB_HELP}
Never invent coordinates. If the user references a place you don't have coordinates for, ask."""


@dataclass
class CommandProposal:
    command: dict
    say: str = ""

@dataclass
class QuestionProposal:
    question: str
    say: str = ""

@dataclass
class ErrorProposal:
    reason: str
    say: str = ""


def _extract_json(text: str) -> tuple[str, dict]:
    """Return (prose_before_json, parsed_json). Finds the first balanced {...}."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no json object found")
    prose = text[:start].strip().strip("`").strip()
    return prose, json.loads(text[start:end + 1])


async def propose(provider, nl: str, telemetry: dict, max_retries: int = 1):
    """Ask the LLM for a structured command/question; validate; retry once on invalid."""
    user = f"Operator request: {nl}\nCurrent telemetry: {json.dumps(telemetry)}"
    last_err = "no response"
    for attempt in range(max_retries + 1):
        raw = await provider.complete(_SYSTEM, user)
        try:
            prose, obj = _extract_json(raw)
        except (ValueError, IndexError):
            last_err = "output was not valid JSON"
            user = f"Your previous reply was not valid JSON. {last_err}. Re-send ONLY the JSON object."
            continue
        if obj.get("action") == "ask":
            return QuestionProposal(question=str(obj.get("question", "Could you clarify?")))
        if obj.get("action") == "command":
            cmd = obj.get("command", {})
            try:
                parse_command(cmd)
            except ValidationError as e:
                last_err = f"command failed validation: {e.errors()[0]['msg']}"
                user = f"Your command was invalid ({last_err}). Re-send a corrected JSON object only."
                continue
            return CommandProposal(command=cmd)
        last_err = "missing or unknown 'action'"
        user = f"Your reply was malformed ({last_err}). Re-send ONLY {{'action':...}} JSON."
    return ErrorProposal(reason=f"Could not produce a valid command after retries: {last_err}")


async def propose_stream(provider, nl: str, telemetry: dict, on_delta):
    """Stream prose to on_delta('reply'/'thinking'); parse the trailing JSON command."""
    user = f"Operator request: {nl}\nCurrent telemetry: {json.dumps(telemetry)}"
    acc = ""
    seen_brace = False
    async for d in provider.stream(_SYSTEM, user):
        if "thinking" in d:
            await on_delta("thinking", d["thinking"])
        if "reply" in d:
            chunk = d["reply"]
            acc += chunk
            if not seen_brace:
                bi = chunk.find("{")
                if bi < 0:
                    await on_delta("reply", chunk)
                else:
                    if bi > 0:
                        await on_delta("reply", chunk[:bi])
                    seen_brace = True
    try:
        prose, obj = _extract_json(acc)
    except (ValueError, IndexError):
        # one non-streamed retry
        raw = await provider.complete(
            _SYSTEM, "Your previous reply had no valid JSON. Re-send prose + JSON.")
        try:
            prose, obj = _extract_json(raw)
        except (ValueError, IndexError):
            return ErrorProposal(reason="no valid JSON after retry")
    if obj.get("action") == "ask":
        return QuestionProposal(question=str(obj.get("question", "Could you clarify?")), say=prose)
    if obj.get("action") == "command":
        cmd = obj.get("command", {})
        try:
            parse_command(cmd)
        except ValidationError as e:
            return ErrorProposal(reason=f"invalid command: {e.errors()[0]['msg']}", say=prose)
        return CommandProposal(command=cmd, say=prose)
    return ErrorProposal(reason="missing or unknown 'action'", say=prose)
