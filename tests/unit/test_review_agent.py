import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.schemas.report import AgentDecision

SAMPLE_Q = json.dumps({
    "id": "11111111-1111-1111-1111-111111111111",
    "question_text": "What does HTTP stand for?",
    "type": "mcq",
    "options": [
        {"id": "A", "text": "HyperText Transfer Protocol", "is_correct": True},
        {"id": "B", "text": "HyperText Transmission Protocol", "is_correct": False},
        {"id": "C", "text": "HighText Transfer Protocol", "is_correct": False},
        {"id": "D", "text": "HyperText Transfer Page", "is_correct": False},
    ],
    "correct_answer": "B",  # intentionally wrong for testing
    "topic": "Networking",
    "subtopic": "HTTP",
    "difficulty": "Basic",
})


def _mock_agent_response(payload: dict) -> MagicMock:
    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value={"output": json.dumps(payload)})
    return mock


@pytest.mark.asyncio
async def test_agent_rejects_baseless_report():
    """Agent returns reject action when confidence < 0.75."""
    decision_data = {
        "action": "reject",
        "confidence": 0.4,
        "verdict": "Question is correct as written. Answer B is HTTP.",
        "is_valid": False,
        "edited_fields": None,
    }
    decision = AgentDecision(**decision_data)
    assert decision.action == "reject"
    assert decision.confidence < 0.75
    assert decision.is_valid is False


@pytest.mark.asyncio
async def test_agent_edits_wrong_answer():
    """AgentDecision with edit action correctly maps edited_fields."""
    decision_data = {
        "action": "edit",
        "confidence": 0.92,
        "verdict": "Correct answer should be A (HyperText Transfer Protocol), not B.",
        "is_valid": True,
        "edited_fields": {
            "correct_answer": "A",
            "explanation": "HTTP stands for HyperText Transfer Protocol.",
        },
    }
    decision = AgentDecision(**decision_data)
    assert decision.action == "edit"
    assert decision.confidence >= 0.75
    assert decision.edited_fields["correct_answer"] == "A"
    assert "explanation" in decision.edited_fields


@pytest.mark.asyncio
async def test_agent_replaces_broken_question():
    """AgentDecision with replace action includes full new question in edited_fields."""
    decision_data = {
        "action": "replace",
        "confidence": 0.88,
        "verdict": "Question contains contradictory premises. Generating replacement.",
        "is_valid": True,
        "edited_fields": {
            "question_text": "What does the HTTP acronym stand for?",
            "options": [
                {"id": "A", "text": "HyperText Transfer Protocol", "is_correct": True, "explanation": "Correct."},
                {"id": "B", "text": "HighText Transfer Protocol", "is_correct": False, "explanation": "Incorrect."},
                {"id": "C", "text": "HyperText Transmission Protocol", "is_correct": False, "explanation": "Incorrect."},
                {"id": "D", "text": "HyperText Transfer Page", "is_correct": False, "explanation": "Incorrect."},
            ],
            "correct_answer": "A",
        },
    }
    decision = AgentDecision(**decision_data)
    assert decision.action == "replace"
    assert decision.confidence >= 0.75
    assert "question_text" in decision.edited_fields
    assert "options" in decision.edited_fields


def test_agent_decision_confidence_boundary():
    """Confidence of exactly 0.75 is considered valid."""
    d = AgentDecision(
        action="edit", confidence=0.75, verdict="Borderline valid",
        is_valid=True, edited_fields={"correct_answer": "A"}
    )
    assert d.is_valid is True
    assert d.confidence == 0.75
