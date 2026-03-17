"""
钉钉机器人服务 - 处理消息接收、文件下载、消息回复
支持两种模式：
1. HTTP 回调模式（Outgoing 机器人）
2. Stream 模式（dingtalk-stream SDK，后续可扩展）
"""
import os
import uuid
import json
import time
import hmac
import hashlib
import base64
import logging
import requests
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from app.config import config

logger = logging.getLogger(__name__)


class DingTalkService:
    """钉钉机器人服务"""

    def __init__(self):
        self.app_key = os.getenv("DINGTALK_APP_KEY", "")
        self.app_secret = os.getenv("DINGTALK_APP_SECRET", "")
        self.robot_code = os.getenv("DINGTALK_ROBOT_CODE", "")
        self.outgoing_token = os.getenv("DINGTALK_OUTGOING_TOKEN", "")
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.app_key and self.app_secret)

    def get_access_token(self) -> str:
        """获取钉钉 access_token（带缓存）"""
        now = time.time()
        if self._access_token and now < self._token_expires_at - 60:
            return self._access_token

        url = "https://oapi.dingtalk.com/gettoken"
        resp = requests.get(url, params={
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }, timeout=10)
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"获取钉钉token失败: {data.get('errmsg')}")

        self._access_token = data["access_token"]
        self._token_expires_at = now + data.get("expires_in", 7200)
        return self._access_token

    def verify_signature(self, timestamp: str, sign: str) -> bool:
        """验证钉钉回调签名"""
        if not self.outgoing_token:
            return True  # 未配置 token 时跳过验证（开发模式）
        string_to_sign = f"{timestamp}\n{self.outgoing_token}"
        hmac_code = hmac.new(
            self.outgoing_token.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        expected_sign = base64.b64encode(hmac_code).decode("utf-8")
        return sign == expected_sign

    def download_file(self, download_code: str) -> Tuple[bytes, str]:
        """
        通过钉钉 downloadCode 下载文件
        返回 (文件内容bytes, 文件名)
        """
        token = self.get_access_token()
        # 获取下载链接
        url = f"https://oapi.dingtalk.com/robot/messageFiles/download"
        resp = requests.post(url, params={"access_token": token}, json={
            "downloadCode": download_code,
            "robotCode": self.robot_code,
        }, timeout=30)
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"获取文件下载链接失败: {data.get('errmsg', data)}")

        download_url = data.get("downloadUrl") or data.get("result", {}).get("downloadUrl")
        if not download_url:
            raise RuntimeError(f"未获取到下载链接: {data}")

        # 下载文件
        file_resp = requests.get(download_url, timeout=120)
        file_resp.raise_for_status()

        # 尝试从 Content-Disposition 获取文件名
        cd = file_resp.headers.get("Content-Disposition", "")
        filename = "unknown.pdf"
        if "filename=" in cd:
            filename = cd.split("filename=")[-1].strip('"').strip("'")
        elif "filename*=" in cd:
            filename = cd.split("filename*=")[-1].split("''")[-1]

        return file_resp.content, filename

    def save_downloaded_file(self, content: bytes, filename: str) -> Tuple[str, str]:
        """
        将下载的文件保存到合同存储目录
        返回 (绝对路径, 相对路径)
        """
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in [".pdf", ".doc", ".docx"]:
            raise ValueError(f"不支持的文件格式: {file_ext}，仅支持 PDF/DOC/DOCX")

        file_id = str(uuid.uuid4())
        safe_name = f"{file_id}{file_ext}"
        contracts_dir = config.STORAGE_PATH / "contracts"
        contracts_dir.mkdir(parents=True, exist_ok=True)
        file_path = contracts_dir / safe_name
        file_path.write_bytes(content)

        relative_path = f"contracts/{safe_name}"
        return str(file_path), relative_path

    def send_text_message(self, webhook_url: str, content: str):
        """通过 webhook 回复文本消息"""
        payload = {
            "msgtype": "text",
            "text": {"content": content},
        }
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            logger.info(f"钉钉消息发送结果: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.error(f"发送钉钉消息失败: {e}")

    def send_markdown_message(self, webhook_url: str, title: str, text: str):
        """通过 webhook 回复 Markdown 消息"""
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": text},
        }
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            logger.info(f"钉钉Markdown消息发送结果: {resp.status_code}")
        except Exception as e:
            logger.error(f"发送钉钉Markdown消息失败: {e}")

    def reply_to_user(self, session_webhook: str, content: str, msg_type: str = "text"):
        """
        回复用户消息（使用 Outgoing 机器人的 sessionWebhook）
        """
        if msg_type == "markdown":
            # 取前20字作为标题
            title = content[:20].replace("\n", " ") + "..."
            self.send_markdown_message(session_webhook, title, content)
        else:
            self.send_text_message(session_webhook, content)

    def send_message_by_open_api(self, user_id: str, content: str, msg_type: str = "sampleText"):
        """
        通过钉钉 OpenAPI 主动发送消息给用户（单聊）
        适用于异步处理完成后的通知
        """
        if not self.robot_code:
            logger.warning("未配置 DINGTALK_ROBOT_CODE，无法主动发消息")
            return

        token = self.get_access_token()
        url = "https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend"
        headers = {
            "x-acs-dingtalk-access-token": token,
            "Content-Type": "application/json",
        }
        payload = {
            "robotCode": self.robot_code,
            "userIds": [user_id],
            "msgKey": msg_type,
            "msgParam": json.dumps({"content": content}),
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            logger.info(f"钉钉主动消息发送: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.error(f"钉钉主动消息发送失败: {e}")


dingtalk_service = DingTalkService()
