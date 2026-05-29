import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from app.config import config


@dataclass
class DingTalkUserIdentity:
    user_id: Optional[str]
    union_id: Optional[str]
    open_id: Optional[str]
    corp_id: Optional[str]
    nick: Optional[str]
    avatar_url: Optional[str]
    email: Optional[str]
    employee_no: Optional[str] = None
    department_name: Optional[str] = None
    position_name: Optional[str] = None
    visitor: bool = False


class DingTalkOAuthService:
    auth_url = "https://login.dingtalk.com/oauth2/auth"
    token_url = "https://api.dingtalk.com/v1.0/oauth2/userAccessToken"
    me_url = "https://api.dingtalk.com/v1.0/contact/users/me"
    state_max_age_seconds = 600
    _consumed_states: dict[str, int] = {}

    @property
    def is_configured(self) -> bool:
        return bool(
            config.DINGTALK_LOGIN_ENABLED
            and config.DINGTALK_LOGIN_CLIENT_ID
            and config.DINGTALK_LOGIN_CLIENT_SECRET
            and config.DINGTALK_LOGIN_REDIRECT_URI
        )

    def build_login_url(self) -> str:
        if not self.is_configured:
            raise HTTPException(status_code=503, detail="钉钉扫码登录未配置")

        scope = "openid corpid" if config.DINGTALK_LOGIN_CORP_ID else "openid"
        params = {
            "client_id": config.DINGTALK_LOGIN_CLIENT_ID,
            "redirect_uri": config.DINGTALK_LOGIN_REDIRECT_URI,
            "response_type": "code",
            "scope": scope,
            "state": self.create_state(),
            "prompt": "consent",
        }
        return f"{self.auth_url}?{urlencode(params)}"

    def create_state(self) -> str:
        payload = {
            "nonce": secrets.token_urlsafe(16),
            "ts": int(time.time()),
        }
        payload_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        payload_token = self._urlsafe_b64encode(payload_text.encode("utf-8"))
        signature = self._sign(payload_token)
        return f"{payload_token}.{signature}"

    def validate_state(self, state: str):
        if not state or "." not in state:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="钉钉登录状态无效")

        payload_token, signature = state.rsplit(".", 1)
        expected_signature = self._sign(payload_token)
        if not hmac.compare_digest(signature, expected_signature):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="钉钉登录状态无效")

        try:
            payload = json.loads(self._urlsafe_b64decode(payload_token).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="钉钉登录状态无效")

        created_at = int(payload.get("ts") or 0)
        if not created_at or int(time.time()) - created_at > self.state_max_age_seconds:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="钉钉登录已超时，请重新扫码")
        self._remember_state_once(state, created_at)

    def fetch_identity(self, auth_code: str) -> DingTalkUserIdentity:
        if not self.is_configured:
            raise HTTPException(status_code=503, detail="钉钉扫码登录未配置")
        if not auth_code:
            raise HTTPException(status_code=400, detail="钉钉授权码不能为空")

        try:
            with httpx.Client(timeout=10) as client:
                token_resp = client.post(
                    self.token_url,
                    json={
                        "clientId": config.DINGTALK_LOGIN_CLIENT_ID,
                        "clientSecret": config.DINGTALK_LOGIN_CLIENT_SECRET,
                        "code": auth_code,
                        "grantType": "authorization_code",
                    },
                )
                token_resp.raise_for_status()
                token_data = token_resp.json()
                access_token = token_data.get("accessToken")
                corp_id = token_data.get("corpId")
                if not access_token:
                    raise HTTPException(status_code=401, detail="钉钉授权失败，未获取到访问凭证")

                user_resp = client.get(
                    self.me_url,
                    headers={"x-acs-dingtalk-access-token": access_token},
                )
                user_resp.raise_for_status()
                user_data = user_resp.json()
        except HTTPException:
            raise
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="钉钉登录服务暂时不可用")

        identity = DingTalkUserIdentity(
            user_id=self._pick(user_data, "userId", "userid", "user_id"),
            union_id=self._pick(user_data, "unionId", "unionid", "union_id"),
            open_id=self._pick(user_data, "openId", "openid", "open_id"),
            corp_id=corp_id or self._pick(user_data, "corpId", "corpid", "corp_id"),
            nick=self._pick(user_data, "nick", "name", "displayName"),
            avatar_url=self._pick(user_data, "avatarUrl", "avatar"),
            email=self._pick(user_data, "email"),
            employee_no=self._pick(user_data, "jobNumber", "jobnumber", "employeeNo", "employee_no"),
            department_name=self._pick_joined(
                user_data,
                "deptName",
                "dept_name",
                "department",
                "departmentName",
                "department_name",
                "deptNames",
                "departmentNames",
            ),
            position_name=self._pick(user_data, "title", "position", "positionName", "position_name", "jobTitle"),
            visitor=bool(user_data.get("visitor")),
        )

        if config.DINGTALK_LOGIN_CORP_ID and identity.corp_id != config.DINGTALK_LOGIN_CORP_ID:
            raise HTTPException(status_code=403, detail="当前钉钉组织无权登录本系统")
        if not any([identity.user_id, identity.union_id, identity.open_id]):
            raise HTTPException(status_code=401, detail="钉钉授权失败，未获取到用户身份")
        return identity

    def _sign(self, payload_token: str) -> str:
        digest = hmac.new(
            config.JWT_SECRET_KEY.encode("utf-8"),
            payload_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return self._urlsafe_b64encode(digest)

    def _remember_state_once(self, state: str, created_at: int):
        now = int(time.time())
        expired = [
            item
            for item, item_created_at in self._consumed_states.items()
            if now - item_created_at > self.state_max_age_seconds
        ]
        for item in expired:
            self._consumed_states.pop(item, None)
        if state in self._consumed_states:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="钉钉登录状态已使用，请重新扫码")
        self._consumed_states[state] = created_at

    @staticmethod
    def _pick(data: dict, *keys: str) -> Optional[str]:
        for key in keys:
            value = data.get(key)
            if value:
                if isinstance(value, (list, tuple)):
                    return str(value[0]) if value else None
                return str(value)
        return None

    @classmethod
    def _pick_joined(cls, data: dict, *keys: str) -> Optional[str]:
        for key in keys:
            value = data.get(key)
            if not value:
                continue
            if isinstance(value, (list, tuple)):
                parts = [str(item).strip() for item in value if str(item).strip()]
                return " / ".join(parts) if parts else None
            return str(value)
        return None

    @staticmethod
    def _urlsafe_b64encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    @staticmethod
    def _urlsafe_b64decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)


dingtalk_oauth_service = DingTalkOAuthService()
