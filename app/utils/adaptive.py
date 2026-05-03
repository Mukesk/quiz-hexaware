import uuid
from sqlalchemy.ext.asyncio import AsyncSession

async def apply_adaptive_rules(accuracy: float, current_diff: str, session_id: uuid.UUID, db: AsyncSession, sess_repo):
    order = ['Basic', 'Easy', 'Intermediate', 'Advanced', 'VeryDifficult']
    try:
        idx = order.index(current_diff)
    except ValueError:
        idx = 0

    if accuracy >= 80 and idx < len(order) - 1:
        new = order[idx + 1]
    elif accuracy < 50 and idx > 0:
        new = order[idx - 1]
    else:
        return current_diff, False

    await sess_repo.update_difficulty(session_id, new, db)
    return new, True
