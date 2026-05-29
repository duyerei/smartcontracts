from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi import HTTPException

from app.auth import hash_password, verify_password
from app.database import User
from app.routers.auth import ChangePasswordRequest, change_password


class DummyDbSession:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True


def test_change_password_updates_current_user_password():
    db = DummyDbSession()
    user = User(
        username="tester",
        real_name="测试用户",
        hashed_password=hash_password("OldPass123!"),
        is_active=True,
    )
    principal = SimpleNamespace(user=user)

    result = change_password(
        ChangePasswordRequest(old_password="OldPass123!", new_password="NewPass123!"),
        principal=principal,
        db=db,
    )

    assert result == {"message": "密码修改成功"}
    assert db.committed is True
    assert verify_password("NewPass123!", user.hashed_password)


def test_change_password_rejects_incorrect_old_password():
    db = DummyDbSession()
    user = User(
        username="tester",
        real_name="测试用户",
        hashed_password=hash_password("OldPass123!"),
        is_active=True,
    )
    principal = SimpleNamespace(user=user)

    with pytest.raises(HTTPException) as exc_info:
        change_password(
            ChangePasswordRequest(old_password="WrongPass123!", new_password="NewPass123!"),
            principal=principal,
            db=db,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "旧密码不正确"
    assert db.committed is False
