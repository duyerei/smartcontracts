"""
钉钉机器人回调路由
处理两种消息：
1. 文件消息 → 自动上传到合同系统并触发 OCR 解析
2. 文本消息 → 自然语言查询合同信息
"""
import logging
import threading
import json
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal, Contract
from app.services.dingtalk_service import dingtalk_service
from app.services import file_storage
from app.services.agent_service import agent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dingtalk", tags=["钉钉机器人"])


@router.get("/health")
def dingtalk_health():
    return {
        "status": "ok",
        "configured": dingtalk_service.is_configured,
        "robot_code": dingtalk_service.robot_code or None,
    }


@router.post("/callback")
async def dingtalk_callback(request: Request):
    """
    钉钉 Outgoing 机器人回调入口
    接收群消息/单聊消息，根据消息类型分发处理
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的请求体")

    logger.info(f"收到钉钉回调: msgtype={body.get('msgtype')}, "
                f"senderNick={body.get('senderNick')}")

    # 签名验证（可选，配置了 outgoing_token 时启用）
    timestamp = request.headers.get("timestamp", "")
    sign = request.headers.get("sign", "")
    if dingtalk_service.outgoing_token and timestamp and sign:
        if not dingtalk_service.verify_signature(timestamp, sign):
            logger.warning("钉钉签名验证失败")
            raise HTTPException(status_code=403, detail="签名验证失败")

    msgtype = body.get("msgtype", "")
    session_webhook = body.get("sessionWebhook", "")
    sender_nick = body.get("senderNick", "用户")
    sender_id = body.get("senderStaffId") or body.get("senderId", "")

    if not session_webhook:
        logger.warning("回调中缺少 sessionWebhook，无法回复")
        return {"status": "ok"}

    if msgtype == "file":
        # 文件消息 → 上传合同
        threading.Thread(
            target=_handle_file_message,
            args=(body, session_webhook, sender_nick, sender_id),
            daemon=True,
        ).start()
        return {"status": "ok"}

    elif msgtype == "text":
        # 文本消息 → 查询合同
        text_content = body.get("text", {}).get("content", "").strip()
        if not text_content:
            return {"status": "ok"}
        threading.Thread(
            target=_handle_text_message,
            args=(text_content, session_webhook, sender_nick, sender_id),
            daemon=True,
        ).start()
        return {"status": "ok"}

    elif msgtype == "richText":
        # 富文本消息，可能包含图片+文字，暂时提取文字部分
        rich_text = body.get("content", {}).get("richText", [])
        text_parts = [item.get("text", "") for item in rich_text if item.get("text")]
        text_content = " ".join(text_parts).strip()
        if text_content:
            threading.Thread(
                target=_handle_text_message,
                args=(text_content, session_webhook, sender_nick, sender_id),
                daemon=True,
            ).start()
        return {"status": "ok"}

    else:
        logger.info(f"不支持的消息类型: {msgtype}")
        dingtalk_service.reply_to_user(
            session_webhook,
            f"暂不支持该消息类型（{msgtype}），请发送文本查询合同或发送PDF/Word文件上传合同。"
        )
        return {"status": "ok"}


def _handle_file_message(body: dict, session_webhook: str, sender_nick: str, sender_id: str):
    """
    处理文件消息：下载文件 → 保存 → 创建合同记录 → 后台解析
    """
    try:
        file_info = body.get("content", {})
        # Outgoing 机器人的文件消息格式
        download_code = file_info.get("downloadCode", "")
        file_name = file_info.get("fileName", "unknown.pdf")

        if not download_code:
            dingtalk_service.reply_to_user(session_webhook, "未能获取文件下载信息，请重试。")
            return

        # 通知用户开始处理
        dingtalk_service.reply_to_user(
            session_webhook,
            f"📄 收到文件「{file_name}」，正在下载并上传到合同系统..."
        )

        # 下载文件
        try:
            file_content, actual_filename = dingtalk_service.download_file(download_code)
        except Exception as e:
            logger.error(f"下载钉钉文件失败: {e}")
            dingtalk_service.reply_to_user(session_webhook, f"❌ 文件下载失败: {e}")
            return

        # 使用原始文件名（如果钉钉返回的更准确）
        if actual_filename and actual_filename != "unknown.pdf":
            file_name = actual_filename

        # 保存文件
        try:
            abs_path, relative_path = dingtalk_service.save_downloaded_file(file_content, file_name)
        except ValueError as e:
            dingtalk_service.reply_to_user(session_webhook, f"❌ {e}")
            return

        # 创建合同记录
        db = SessionLocal()
        try:
            contract_number = f"DD-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"
            contract = Contract(
                contract_number=contract_number,
                title="解析中...",
                contract_type="其他",
                department="其他",
                status="待审核",
                parties="[]",
                amount=None,
                currency="CNY",
                file_path=relative_path,
                original_filename=file_name,
                summary=f"通过钉钉上传（{sender_nick}），正在解析中...",
                raw_text="",
                extracted_data=json.dumps({"parsing": True, "source": "dingtalk", "sender": sender_nick}, ensure_ascii=False),
            )
            db.add(contract)
            db.commit()
            db.refresh(contract)
            contract_id = contract.id
        finally:
            db.close()

        # 通知用户上传成功
        dingtalk_service.reply_to_user(
            session_webhook,
            f"✅ 合同上传成功！\n"
            f"- 合同ID: {contract_id}\n"
            f"- 编号: {contract_number}\n"
            f"- 文件: {file_name}\n"
            f"正在后台进行OCR识别与智能解析，完成后会通知您。"
        )

        # 后台异步解析（复用现有的解析流程）
        from app.routers.contracts import _async_full_parse
        parse_thread = threading.Thread(
            target=_dingtalk_parse_and_notify,
            args=(contract_id, abs_path, session_webhook, sender_id),
            daemon=True,
        )
        parse_thread.start()

    except Exception as e:
        logger.error(f"处理钉钉文件消息异常: {e}", exc_info=True)
        try:
            dingtalk_service.reply_to_user(session_webhook, f"❌ 处理文件时出错: {e}")
        except Exception:
            pass


def _dingtalk_parse_and_notify(contract_id: int, file_path: str, session_webhook: str, sender_id: str):
    """
    后台解析合同，完成后通过钉钉通知用户
    """
    try:
        from app.routers.contracts import _async_full_parse
        _async_full_parse(contract_id, file_path, "")

        # 解析完成，读取结果
        db = SessionLocal()
        try:
            contract = db.query(Contract).filter(Contract.id == contract_id).first()
            if not contract:
                return

            # 构建解析结果摘要
            lines = [f"🎉 合同解析完成！（ID: {contract_id}）"]
            if contract.title and contract.title != "解析中...":
                lines.append(f"📋 名称: {contract.title}")
            if contract.contract_number:
                lines.append(f"🔢 编号: {contract.contract_number}")
            if contract.amount:
                lines.append(f"💰 金额: {contract.amount:,.2f} 元")
            if contract.parties and contract.parties != "[]":
                try:
                    parties = json.loads(contract.parties)
                    if parties:
                        parties_str = "、".join([p.get("name", "") for p in parties if p.get("name")])
                        if parties_str:
                            lines.append(f"👥 当事方: {parties_str}")
                except (json.JSONDecodeError, TypeError):
                    pass
            if contract.start_date:
                lines.append(f"📅 开始日期: {str(contract.start_date)[:10]}")
            if contract.end_date:
                lines.append(f"📅 结束日期: {str(contract.end_date)[:10]}")
            if contract.contract_type and contract.contract_type != "其他":
                lines.append(f"📁 类型: {contract.contract_type}")

            result_text = "\n".join(lines)
        finally:
            db.close()

        # 通过 sessionWebhook 回复（如果还有效）
        try:
            dingtalk_service.reply_to_user(session_webhook, result_text)
        except Exception:
            pass

        # 也通过 OpenAPI 主动发消息（sessionWebhook 可能已过期）
        if sender_id:
            try:
                dingtalk_service.send_message_by_open_api(sender_id, result_text)
            except Exception as e:
                logger.warning(f"主动发送解析结果失败: {e}")

    except Exception as e:
        logger.error(f"钉钉合同解析异常: {e}", exc_info=True)
        try:
            dingtalk_service.reply_to_user(session_webhook, f"❌ 合同解析失败: {e}")
        except Exception:
            pass


def _handle_text_message(text: str, session_webhook: str, sender_nick: str, sender_id: str):
    """
    处理文本消息：自然语言查询合同
    复用现有的 AgentService 意图识别 + 合同查询能力
    """
    try:
        # 去掉 @机器人 的前缀（钉钉群消息中 @机器人 后面才是真正内容）
        # 有时内容前面会有空格或特殊字符
        text = text.strip()

        # 帮助信息
        if text in ("帮助", "help", "?", "？", "功能"):
            help_text = (
                "🤖 合同管理助手\n\n"
                "📄 上传合同：直接发送 PDF/Word 文件\n"
                "🔍 查询合同：\n"
                "  - 「查一下XX公司的合同」\n"
                "  - 「金额大于100万的合同」\n"
                "  - 「快到期的合同」\n"
                "  - 「最近的合同」\n"
                "  - 「合同16」（查看指定合同）\n"
                "  - 直接输入公司名或关键词搜索\n"
            )
            dingtalk_service.reply_to_user(session_webhook, help_text)
            return

        # 使用 AgentService 的意图识别
        op = agent_service.detect_operation(text)
        if not op:
            dingtalk_service.reply_to_user(
                session_webhook,
                "🤔 没有理解您的意思，请试试：\n- 发送文件上传合同\n- 输入「查一下XX合同」查询\n- 输入「帮助」查看功能"
            )
            return

        db = SessionLocal()
        try:
            if op.action == "list_contracts":
                filters = op.filters or {}
                items = agent_service.list_contracts(db, limit=10, filters=filters)

                if not items:
                    dingtalk_service.reply_to_user(session_webhook, "📭 未找到匹配的合同。")
                    return

                # 构建结果文本
                lines = [f"🔍 为您找到 {len(items)} 份合同：\n"]
                for i, item in enumerate(items, 1):
                    title = item.get("title", "未命名")
                    cid = item.get("id", "")
                    amount = item.get("amount")
                    status = item.get("status", "")
                    amount_str = f"  💰{amount:,.2f}元" if amount else ""
                    status_str = f"  [{status}]" if status else ""
                    lines.append(f"{i}. 【{cid}】{title}{amount_str}{status_str}")

                dingtalk_service.reply_to_user(session_webhook, "\n".join(lines))

            elif op.action == "get_contract":
                if not op.contract_id:
                    dingtalk_service.reply_to_user(session_webhook, "请提供合同ID，例如：合同16")
                    return

                item = agent_service.get_contract(db, op.contract_id)
                if not item:
                    dingtalk_service.reply_to_user(session_webhook, f"未找到合同 {op.contract_id}")
                    return

                # 构建详情文本
                lines = [f"📋 合同详情（ID: {op.contract_id}）\n"]
                field_map = [
                    ("名称", "title"), ("编号", "contract_number"),
                    ("金额", "amount"), ("类型", "contract_type"),
                    ("状态", "status"), ("部门", "department"),
                    ("开始日期", "start_date"), ("结束日期", "end_date"),
                ]
                for label, key in field_map:
                    val = item.get(key)
                    if val is not None and val != "" and val != "[]":
                        if key == "amount":
                            val = f"{val:,.2f} 元"
                        lines.append(f"  {label}: {val}")

                # 当事方
                parties = item.get("parties")
                if parties:
                    if isinstance(parties, str):
                        try:
                            parties = json.loads(parties)
                        except (json.JSONDecodeError, TypeError):
                            parties = []
                    if isinstance(parties, list) and parties:
                        names = [p.get("name", "") for p in parties if isinstance(p, dict) and p.get("name")]
                        if names:
                            lines.append(f"  当事方: {'、'.join(names)}")

                summary = item.get("summary")
                if summary and len(summary) > 10:
                    # 截取摘要前200字
                    lines.append(f"\n📝 摘要: {summary[:200]}{'...' if len(summary) > 200 else ''}")

                dingtalk_service.reply_to_user(session_webhook, "\n".join(lines))

            elif op.action == "consult":
                # 咨询类问题 → 调用 LLM
                result = agent_service.consult(message=text)
                reply = result.get("reply", "")
                if reply:
                    dingtalk_service.reply_to_user(session_webhook, reply)
                else:
                    dingtalk_service.reply_to_user(session_webhook, "🤔 暂时无法回答这个问题，请换个方式提问。")

            else:
                # 其他操作（删除、重解析等）在钉钉中不支持
                dingtalk_service.reply_to_user(
                    session_webhook,
                    "⚠️ 该操作暂不支持通过钉钉执行，请登录合同管理系统操作。"
                )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"处理钉钉文本消息异常: {e}", exc_info=True)
        try:
            dingtalk_service.reply_to_user(session_webhook, f"❌ 查询出错: {e}")
        except Exception:
            pass
