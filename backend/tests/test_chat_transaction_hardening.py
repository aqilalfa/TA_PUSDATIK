import asyncio
from unittest.mock import MagicMock

import pytest

from app.api.routes.chat import _persist_exchange, _request_disconnected


def test_persist_exchange_commits_user_and_assistant_together():
    db = MagicMock()
    session = MagicMock()
    _persist_exchange(db, session, "s1", "question", "answer", [], 12)
    assert db.add.call_count == 2
    assert [call.args[0].role for call in db.add.call_args_list] == ["user", "assistant"]
    db.commit.assert_called_once()


def test_persist_exchange_rolls_back_failed_commit():
    db = MagicMock()
    db.commit.side_effect = RuntimeError("write failed")
    with pytest.raises(RuntimeError):
        _persist_exchange(db, MagicMock(), "s1", "q", "a", [], 0)
    db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_request_disconnected_and_cancelled_error_are_distinct():
    request = MagicMock()
    request.is_disconnected.return_value = asyncio.sleep(0, result=True)
    assert await _request_disconnected(request) is True
