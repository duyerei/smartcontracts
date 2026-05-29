from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.database import Base, DingTalkLoginCandidate
from app.routers.auth import _record_dingtalk_candidate
from app.services.dingtalk_oauth_service import DingTalkUserIdentity


def test_record_dingtalk_candidate_persists_profile_fields():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        identity = DingTalkUserIdentity(
            user_id="ding-user-1",
            union_id="union-1",
            open_id="open-1",
            corp_id="corp-1",
            nick="张三",
            avatar_url="https://example.com/avatar.png",
            email="zhangsan@example.com",
            employee_no="EMP001",
            department_name="法务合规中心",
            position_name="法务经理",
            visitor=False,
        )

        _record_dingtalk_candidate(db, identity)

        candidate = db.query(DingTalkLoginCandidate).filter(DingTalkLoginCandidate.dingtalk_user_id == "ding-user-1").one()
        assert candidate.nick == "张三"
        assert candidate.employee_no == "EMP001"
        assert candidate.department_name == "法务合规中心"
        assert candidate.position_name == "法务经理"
        assert candidate.status == "pending"
        assert candidate.seen_count == 1
    finally:
        db.close()
