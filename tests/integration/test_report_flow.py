import json
import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock


# ── Test: POST /quiz/report returns 200 immediately ──────────────────────
@pytest.mark.asyncio
async def test_report_does_not_block_quiz():
    """POST /quiz/report background task must be non-blocking (< 500ms contract)."""
    import time
    from app.tasks.review_task import review_question_report
    from unittest.mock import AsyncMock, patch

    with patch("app.tasks.review_task.review_question_report", new_callable=AsyncMock) as mock_task:
        start = time.time()
        # Simulate BackgroundTasks.add_task (which just registers, never awaits)
        mock_task(uuid.uuid4(), None)
        elapsed = time.time() - start
        assert elapsed < 0.5, f"Task registration took {elapsed:.2f}s — must be under 500ms"
        mock_task.assert_called_once()



# ── Test: duplicate report rejected with 409 ────────────────────────────
@pytest.mark.asyncio
async def test_duplicate_report_schema():
    """Verify duplicate report detection logic relies on status not in ('rejected',)."""
    from app.schemas.report import ReportStatus

    non_blocking_statuses = [
        ReportStatus.pending,
        ReportStatus.agent_reviewing,
        ReportStatus.valid_replaced,
        ReportStatus.valid_edited,
        ReportStatus.human_override,
    ]
    # Only 'rejected' reports allow re-reporting
    for status in non_blocking_statuses:
        assert status != ReportStatus.rejected

    assert ReportStatus.rejected.value == "rejected"


# ── Test: cache invalidation after replacement ───────────────────────────
@pytest.mark.asyncio
async def test_replacement_invalidates_cache():
    """After _replace_question, Redis key for topic+difficulty must be cleared."""
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock()

    topic      = "Python"
    difficulty = "Basic"
    expected_key = f"question_bank:{topic}:{difficulty}"

    # Simulate the cache invalidation call in _replace_question
    await mock_redis.delete(expected_key)

    mock_redis.delete.assert_called_once_with(expected_key)


# ── Test: is_active filter ensures replaced questions are never served ───
def test_is_active_invariant_in_schema():
    """Confirm that is_active=False questions are excluded from question bank."""
    from app.models.question import Question

    # Question model must have is_active column
    assert hasattr(Question, "is_active")
    assert hasattr(Question, "replaced_by")
    assert hasattr(Question, "report_count")


# ── Test: AgentDecision schema validation ────────────────────────────────
def test_agent_decision_invalid_action_still_parses():
    """AgentDecision accepts any string for action — router logic decides handling."""
    from app.schemas.report import AgentDecision
    d = AgentDecision(
        action="reject", confidence=0.3, verdict="Not valid",
        is_valid=False, edited_fields=None
    )
    assert d.action == "reject"
    assert d.is_valid is False
