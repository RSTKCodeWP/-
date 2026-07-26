import asyncio
from assistant.config import AssistantSettings
from assistant.llm import OpenRouterProvider
from assistant.safety_client import SafetyClient
from assistant.agent import Agent
from assistant.command_gen import CommandProposal, QuestionProposal, ErrorProposal


async def run() -> None:
    settings = AssistantSettings()
    if not settings.openrouter_api_key:
        raise SystemExit("Set AS_OPENROUTER_API_KEY in .env")
    client = SafetyClient(settings.safety_url)
    await client.connect()
    agent = Agent(OpenRouterProvider.from_settings(settings), client)
    print(f"Assistant ready (model={settings.model}). Type a request, 'abort', or 'quit'.")
    try:
        while True:
            nl = (await asyncio.to_thread(input, "> ")).strip()
            if not nl:
                continue
            if nl in ("quit", "exit"):
                break
            if nl == "abort":
                print(await agent.abort())
                continue
            proposal = await agent.propose(nl)
            if isinstance(proposal, QuestionProposal):
                print(f"[assistant asks] {proposal.question}")
            elif isinstance(proposal, ErrorProposal):
                print(f"[error] {proposal.reason}")
            elif isinstance(proposal, CommandProposal):
                print(f"[proposed command] {proposal.command}")
                ok = (await asyncio.to_thread(input, "execute? [y/N] ")).strip().lower()
                if ok == "y":
                    print(await agent.execute(proposal.command))
                else:
                    print("cancelled")
    finally:
        await client.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
