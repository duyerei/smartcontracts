from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
import os
import re

from app.database import get_db, Payment, Contract, User, SessionLocal
from app.auth import get_current_user
from app.services import file_storage
from app.services.baidu_ocr import BaiduOCR
from app.services.llm_service import LLMService

router = APIRouter(prefix="/payments", tags=["付款管理"])


class PaymentUpdate(BaseModel):
    payment_date: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None


@router.post("/{contract_id}/upload")
async def upload_payment(
    contract_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    payment_date: Optional[str] = Form(None),
    amount: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传付款凭证"""
    # 验证主合同是否存在
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.is_deleted == False
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="主合同不存在")
    
    try:
        # 保存文件到payments目录
        file_path, relative_path = await save_payment_file(file, contract_id)
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        
        # 创建付款记录
        payment = Payment(
            contract_id=contract_id,
            description=description or file.filename,
            payment_date=datetime.strptime(payment_date, "%Y-%m-%d") if payment_date else None,
            amount=float(amount) if amount else None,
            file_path=relative_path,
            file_size=file_size
        )
        
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        # 添加后台任务识别付款时间和金额
        background_tasks.add_task(analyze_and_update_payment, payment.id, file_path)
        
        return {
            "id": payment.id,
            "contract_id": payment.contract_id,
            "description": payment.description,
            "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
            "amount": payment.amount,
            "file_path": payment.file_path,
            "file_size": payment.file_size,
            "created_at": payment.created_at.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def save_payment_file(file: UploadFile, contract_id: int):
    """保存付款文件"""
    import uuid
    
    # 检查文件扩展名
    file_ext = os.path.splitext(file.filename)[1].lower()
    allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
    
    if file_ext not in allowed_extensions:
        raise ValueError("不支持的文件格式，仅支持PDF、图片、DOC、DOCX")
    
    # 读取文件内容
    content = await file.read()
    
    # 检查文件大小（50MB）
    MAX_FILE_SIZE = 50 * 1024 * 1024
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"文件大小超过限制（最大50MB）")
    
    # 生成文件名
    file_id = str(uuid.uuid4())
    file_name = f"{contract_id}_{file_id}{file_ext}"
    
    # 确保payments目录存在
    payments_dir = file_storage.storage_path / "payments"
    payments_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = payments_dir / file_name
    
    # 保存文件
    with open(file_path, "wb") as buffer:
        buffer.write(content)
    
    relative_path = f"payments/{file_name}"
    return str(file_path), relative_path


def analyze_and_update_payment(payment_id: int, file_path: str):
    """后台任务：分析付款凭证并更新付款时间和金额"""
    print(f"开始分析付款凭证 {payment_id}...")
    
    try:
        # 初始化OCR和LLM服务
        ocr = BaiduOCR()
        llm = LLMService()
        
        # OCR识别文件内容
        ocr_text = ""
        try:
            print(f"正在OCR识别文件: {file_path}")
            
            # 判断文件类型
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.pdf':
                ocr_text = ocr.recognize_pdf(file_path, num_pages=2)
            elif file_ext in ['.jpg', '.jpeg', '.png']:
                # 图片文件直接识别
                import base64
                with open(file_path, 'rb') as f:
                    img_base64 = base64.b64encode(f.read()).decode()
                
                import requests
                access_token = ocr.get_access_token()
                url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic?access_token={access_token}"
                headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                data = {'image': img_base64}
                
                response = requests.post(url, headers=headers, data=data, timeout=30)
                result = response.json()
                
                if "words_result" in result:
                    ocr_text = "\n".join([w.get("words", "") for w in result.get("words_result", [])])
            
            if ocr_text:
                print(f"OCR识别成功，文本长度: {len(ocr_text)}")
            else:
                print("OCR未识别到文本")
                return
        except Exception as e:
            print(f"OCR识别失败: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # 使用LLM提取信息
        try:
            print("正在使用LLM提取信息...")
            prompt = f"""请从以下付款凭证文本中提取关键信息：

文本内容：
{ocr_text[:2000]}

请提取：
1. 付款日期/交易时间（格式：YYYY-MM-DD）
2. 付款金额/交易金额（仅数字，不含货币符号）

请以JSON格式返回：
{{
    "payment_date": "YYYY-MM-DD",
    "amount": 数字
}}

如果无法识别某项信息，请返回null。"""

            response = llm._call_qianfan(prompt)
            print(f"LLM响应: {response}")
            
            # 尝试解析JSON响应
            import json
            json_match = re.search(r'\{[^}]+\}', response)
            if json_match:
                info = json.loads(json_match.group())
                print(f"解析结果: {info}")
                
                # 更新数据库
                db = SessionLocal()
                try:
                    payment = db.query(Payment).filter(
                        Payment.id == payment_id
                    ).first()
                    
                    if payment:
                        updated = False
                        
                        if info.get("payment_date") and not payment.payment_date:
                            try:
                                payment.payment_date = datetime.strptime(info["payment_date"], "%Y-%m-%d")
                                updated = True
                                print(f"更新付款时间: {info['payment_date']}")
                            except Exception as e:
                                print(f"付款时间解析失败: {e}")
                        
                        if info.get("amount") and not payment.amount:
                            try:
                                payment.amount = float(info["amount"])
                                updated = True
                                print(f"更新金额: {info['amount']}")
                            except Exception as e:
                                print(f"金额解析失败: {e}")
                        
                        if updated:
                            db.commit()
                            print(f"付款记录 {payment_id} 信息更新成功")
                        else:
                            print(f"付款记录 {payment_id} 无需更新")
                finally:
                    db.close()
            else:
                print("未找到JSON格式的响应")
        except Exception as e:
            print(f"LLM提取信息失败: {e}")
            import traceback
            traceback.print_exc()
    except Exception as e:
        print(f"分析付款凭证失败: {e}")
        import traceback
        traceback.print_exc()


@router.get("/{contract_id}/list")
def list_payments(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同的所有付款记录"""
    # 验证主合同是否存在
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.is_deleted == False
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="主合同不存在")
    
    # 查询付款记录
    payments = db.query(Payment).filter(
        Payment.contract_id == contract_id,
        Payment.is_deleted == False
    ).order_by(Payment.payment_date.desc()).all()
    
    return {
        "payments": [
            {
                "id": p.id,
                "contract_id": p.contract_id,
                "description": p.description,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "amount": p.amount,
                "file_path": p.file_path,
                "file_size": p.file_size,
                "created_at": p.created_at.isoformat()
            }
            for p in payments
        ]
    }


@router.get("/{payment_id}/download")
def download_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """下载或预览付款凭证"""
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.is_deleted == False
    ).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="付款记录不存在")
    
    file_path = file_storage.get_file_path(payment.file_path)
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 根据文件类型设置media_type
    file_ext = os.path.splitext(payment.file_path)[1].lower()
    media_types = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    
    media_type = media_types.get(file_ext, 'application/octet-stream')
    
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=payment.description
    )


@router.patch("/{payment_id}")
def update_payment(
    payment_id: int,
    update_data: PaymentUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新付款记录信息"""
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.is_deleted == False
    ).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="付款记录不存在")
    
    # 更新字段
    if update_data.description is not None:
        payment.description = update_data.description
    
    if update_data.payment_date is not None:
        if update_data.payment_date:
            try:
                payment.payment_date = datetime.strptime(update_data.payment_date, "%Y-%m-%d")
            except:
                raise HTTPException(status_code=400, detail="日期格式错误")
        else:
            payment.payment_date = None
    
    if update_data.amount is not None:
        payment.amount = update_data.amount if update_data.amount else None
    
    db.commit()
    db.refresh(payment)
    
    return {
        "id": payment.id,
        "contract_id": payment.contract_id,
        "description": payment.description,
        "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
        "amount": payment.amount,
        "file_path": payment.file_path,
        "file_size": payment.file_size,
        "created_at": payment.created_at.isoformat()
    }


@router.delete("/{payment_id}")
def delete_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除付款记录"""
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.is_deleted == False
    ).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="付款记录不存在")
    
    # 软删除
    payment.is_deleted = True
    db.commit()
    
    return {"message": "付款记录删除成功"}
