"""Non-interactive live demo: NL -> LLM -> validated command -> fly.

Drives the assistant Agent against a RUNNING flight-safety service (which must be
connected to PX4 SITL). Auto-executes proposals (no y/N prompt) so it can run
unattended; prints the LLM's translation and the service's response for each request.
"""
import asyncio
from assistant.config import AssistantSettings
from assistant.llm import OpenRouterProvider
from assistant.safety_client import SafetyClient
from assistant.agent import Agent
from assistant.command_gen import CommandProposal, QuestionProposal, ErrorProposal

REQUESTS = [
    "take off to 5 meters",
    "orbit right here at 15 meters altitude with a 20 meter radius",
    "fly to latitude 48.5 longitude 8.0 at 30 meters",   # outside geofence -> expect REJECT
    "now return home",
]


async def main() -> None:
    s = AssistantSettings()
    print(f"model = {s.model}")
    client = SafetyClient(s.safety_url)
    await client.connect()
    agent = Agent(OpenRouterProvider.from_settings(s), client)
    try:
        for nl in REQUESTS:
            print(f"\n>>> {nl}", flush=True)
            proposal = await agent.propose(nl)
            if isinstance(proposal, CommandProposal):
                print(f"    LLM -> command: {proposal.command}", flush=True)
                result = await agent.execute(proposal.command)
                print(f"    service        : {result}", flush=True)
            elif isinstance(proposal, QuestionProposal):
                print(f"    assistant asks : {proposal.question}", flush=True)
            else:
                print(f"    error          : {proposal.reason}", flush=True)
            await asyncio.sleep(2)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
