from backend.analysis.llm import LLMDecisionEngine

import pytest


# --------------
# Helpers
# --------------

def make_engine(monkeypatch, model_name="test-model"):
    """
    Creates an LLMDecisionEngine without starting Ollama.

    The real constructor calls _ensure_ready(), which can start the Ollama app
    and check installed models. For unit tests, we patch that away.
    """
    monkeypatch.setattr(LLMDecisionEngine, "_ensure_ready", lambda self: None)

    return LLMDecisionEngine(
        model_name=model_name,
        ollama_app_path="fake_ollama_path.exe",
    )


def make_decide_kwargs(**overrides):
    kwargs = {
        "title": "Microsoft announces major AI infrastructure deal",
        "summary": "Microsoft signed a large multi-year AI cloud agreement.",
        "ticker": "MSFT",
        "company_dossier": "Microsoft is a cloud and AI infrastructure company.",
        "memory_context": "Past Memories: Similar AI cloud deals led to strong momentum.",
        "risk_profile": {"REGIME": "MARKUP"},
    }

    kwargs.update(overrides)
    return kwargs


class FakeOllamaResponse:
    def __init__(self, response_text):
        self.response_text = response_text

    def raise_for_status(self):
        return None

    def json(self):
        return {"response": self.response_text}


# ----------------------
# Test decide happy path
# ----------------------

def test_decide_returns_structured_decision_from_ollama_response(monkeypatch):
    engine = make_engine(monkeypatch)
    captured_payload = {}

    def fake_post(url, json, timeout):
        captured_payload["url"] = url
        captured_payload["json"] = json
        captured_payload["timeout"] = timeout

        return FakeOllamaResponse(
            '{"signal": "BUY", "confidence": 0.87, "reasoning": "Strong institutional catalyst."}'
        )

    monkeypatch.setattr("backend.analysis.llm.requests.post", fake_post)

    decision = engine.decide(**make_decide_kwargs())

    assert decision == {
        "signal": "BUY",
        "confidence": pytest.approx(0.87),
        "reasoning": "Strong institutional catalyst.",
    }

    assert captured_payload["url"] == "http://localhost:11434/api/generate"
    assert captured_payload["timeout"] == 120

    payload = captured_payload["json"]

    assert payload["model"] == "test-model"
    assert payload["stream"] is False
    assert payload["format"] == "json"

    assert "Microsoft announces major AI infrastructure deal" in payload["prompt"]
    assert "MSFT" in payload["prompt"]
    assert "MARKUP" in payload["prompt"]
    assert "Microsoft is a cloud and AI infrastructure company." in payload["prompt"]
    assert "Past Memories" in payload["prompt"]


# ---------------------------------------
# Test decide defaults incomplete response
# ---------------------------------------

def test_decide_defaults_missing_json_fields_to_safe_values(monkeypatch):
    engine = make_engine(monkeypatch)

    def fake_post(url, json, timeout):
        return FakeOllamaResponse("{}")

    monkeypatch.setattr("backend.analysis.llm.requests.post", fake_post)

    decision = engine.decide(**make_decide_kwargs())

    assert decision == {
        "signal": "WAIT",
        "confidence": pytest.approx(0.0),
        "reasoning": "",
    }


# -------------------------------
# Test decide handles bad response
# -------------------------------

def test_decide_returns_none_when_ollama_call_fails(monkeypatch):
    engine = make_engine(monkeypatch)

    def fake_post(url, json, timeout):
        raise RuntimeError("Ollama is unavailable")

    monkeypatch.setattr("backend.analysis.llm.requests.post", fake_post)

    decision = engine.decide(**make_decide_kwargs())

    assert decision is None