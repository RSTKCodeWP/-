from assistant.config import AssistantSettings


def test_defaults():
    s = AssistantSettings(openrouter_api_key="sk-test")
    assert s.model
    assert s.base_url.startswith("https://")
    assert s.safety_url.startswith("ws://")
    assert s.openrouter_api_key == "sk-test"
