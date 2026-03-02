from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
import os
import re

from app.database import get_db, Supplement, Contract, User, SessionLocal
from app.auth import get_current_user
from app.services import file_storage
from app.services.baidu_ocr import BaiduOCR
from app.services.llm_service import LLMService

router = APIRouter(prefix="/supplements", tags=["补充协议"])


class SupplementUpdate(BaseModel):
    title: Optional[str] = None
    signed_date: Optional[str] = None
    amount: Optional[float] = None


@router.post("/{contract_id}/analyze")
async def analyze_supplement(
    contract_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """分析补充协议文件，提取标题和签订时间"""
    # 验证主合同是否存在
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.is_deleted == False
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="主合同不存在")
    
    try:
        # 保存临时文件
        temp_path, _ = await file_storage.save_temp_file(file)
        
        # 初始化OCR和LLM服务
        ocr = BaiduOCR()
        llm = LLMService()
        
        # OCR识别文件内容（只识别前2页）
        ocr_text = ""
        try:
            ocr_text = ocr.recognize_pdf(str(temp_path), num_pages=2)
        except Exception as e:
            print(f"OCR识别失败: {e}")
        
        # 使用LLM提取信息
        extracted_info = {
            "title": file.filename.replace(".pdf", "").replace(".doc", "").replace(".docx", ""),
            "signed_date": None,
            "amount": None
        }
        
        if ocr_text:
            try:
                prompt = f"""请从以下补充协议文本中提取关键信息：

文本内容：
{ocr_text[:2000]}

请提取：
1. 协议标题或名称（如"补充协议"、"补充协议一"等）
2. 签订日期（格式：YYYY-MM-DD）
3. 补充协议涉及的金额（仅数字，不含货币符号）

请以JSON格式返回：
{{
    "title": "协议标题",
    "signed_date": "YYYY-MM-DD",
    "amount": 数字
}}

如果无法识别某项信息，请返回null。"""

                response = llm._call_qianfan(prompt)
                
                # 尝试解析JSON响应
                import json
                # 提取JSON部分
                json_match = re.search(r'\{[^}]+\}', response)
                if json_match:
                    info = json.loads(json_match.group())
                    if info.get("title"):
                        extracted_info["title"] = info["title"]
                    if info.get("signed_date"):
                        extracted_info["signed_date"] = info["signed_date"]
                    if info.get("amount"):
                        try:
                            extracted_info["amount"] = float(info["amount"])
                        except:
                            pass
            except Exception as e:
                print(f"LLM提取信息失败: {e}")
        
        # 清理临时文件
        try:
            os.remove(temp_path)
        except:
            pass
        
        return extracted_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件分析失败: {str(e)}")


@router.post("/{contract_id}/upload")
async def upload_supplement(
    contract_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    signed_date: Optional[str] = Form(None),
    amount: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传补充协议"""
    # 验证主合同是否存在
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.is_deleted == False
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="主合同不存在")
    
    try:
        # 保存文件
        file_path, relative_path = await file_storage.save_supplement(file, contract_id)
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        
        # 创建补充协议记录
        supplement = Supplement(
            contract_id=contract_id,
            title=title or file.filename,
            signed_date=datetime.strptime(signed_date, "%Y-%m-%d") if signed_date else None,
            amount=float(amount) if amount else None,
            file_path=relative_path,
            file_size=file_size
        )
        
        db.add(supplement)
        db.commit()
        db.refresh(supplement)
        
        # 添加后台任务识别签订时间和金额
        background_tasks.add_task(analyze_and_update_supplement, supplement.id, file_path)
        
        return {
            "id": supplement.id,
            "contract_id": supplement.contract_id,
            "title": supplement.title,
            "signed_date": supplement.signed_date.isoformat() if supplement.signed_date else None,
            "amount": supplement.amount,
            "file_path": supplement.file_path,
            "file_size": supplement.file_size,
            "created_at": supplement.created_at.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def analyze_and_update_supplement(supplement_id: int, file_path: str):
    """后台任务：分析补充协议并更新签订时间和金额"""
    print(f"开始分析补充协议 {supplement_id}...")
    
    try:
        # 初始化OCR和LLM服务
        ocr = BaiduOCR()
        llm = LLMService()
        
        # OCR识别文件内容（只识别前2页）
        ocr_text = ""
        try:
            print(f"正在OCR识别文件: {file_path}")
            ocr_text = ocr.recognize_pdf(file_path, num_pages=2)
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
            prompt = f"""请从以下补充协议文本中提取关键信息：

文本内容：
{ocr_text[:2000]}

请提取：
1. 签订日期（格式：YYYY-MM-DD）
2. 补充协议涉及的金额（仅数字，不含货币符号）

请以JSON格式返回：
{{
    "signed_date": "YYYY-MM-DD",
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
                    supplement = db.query(Supplement).filter(
                        Supplement.id == supplement_id
                    ).first()
                    
                    if supplement:
                        updated = False
                        
                        if info.get("signed_date") and not supplement.signed_date:
                            try:
                                supplement.signed_date = datetime.strptime(info["signed_date"], "%Y-%m-%d")
                                updated = True
                                print(f"更新签订时间: {info['signed_date']}")
                            except Exception as e:
                                print(f"签订时间解析失败: {e}")
                        
                        if info.get("amount") and not supplement.amount:
                            try:
                                supplement.amount = float(info["amount"])
                                updated = True
                                print(f"更新金额: {info['amount']}")
                            except Exception as e:
                                print(f"金额解析失败: {e}")
                        
                        if updated:
                            db.commit()
                            print(f"补充协议 {supplement_id} 信息更新成功")
                        else:
                            print(f"补充协议 {supplement_id} 无需更新")
                finally:
                    db.close()
            else:
                print("未找到JSON格式的响应")
        except Exception as e:
            print(f"LLM提取信息失败: {e}")
            import traceback
            traceback.print_exc()
    except Exception as e:
        print(f"分析补充协议失败: {e}")
        import traceback
        traceback.print_exc()


@router.get("/{contract_id}/list")
def list_supplements(
    contract_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取合同的所有补充协议"""
    # 验证主合同是否存在
    contract = db.query(Contract).filter(
        Contract.id == contract_id,
        Contract.is_deleted == False
    ).first()
    
    if not contract:
        raise HTTPException(status_code=404, detail="主合同不存在")
    
    # 查询补充协议
    supplements = db.query(Supplement).filter(
        Supplement.contract_id == contract_id,
        Supplement.is_deleted == False
    ).order_by(Supplement.created_at.desc()).all()
    
    return {
        "supplements": [
            {
                "id": s.id,
                "contract_id": s.contract_id,
                "title": s.title,
                "signed_date": s.signed_date.isoformat() if s.signed_date else None,
                "amount": s.amount,
                "file_path": s.file_path,
                "file_size": s.file_size,
                "created_at": s.created_at.isoformat()
            }
            for s in supplements
        ]
    }


@router.get("/{supplement_id}/download")
def download_supplement(
    supplement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """下载或预览补充协议"""
    supplement = db.query(Supplement).filter(
        Supplement.id == supplement_id,
        Supplement.is_deleted == False
    ).first()
    
    if not supplement:
        raise HTTPException(status_code=404, detail="补充协议不存在")
    
    file_path = file_storage.get_file_path(supplement.file_path)
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 根据文件类型设置media_type
    file_ext = os.path.splitext(supplement.file_path)[1].lower()
    media_types = {
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    
    media_type = media_types.get(file_ext, 'application/octet-stream')
    
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=supplement.title + file_ext
    )


@router.delete("/{supplement_id}")
def delete_supplement(
    supplement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除补充协议"""
    supplement = db.query(Supplement).filter(
        Supplement.id == supplement_id,
        Supplement.is_deleted == False
    ).first()
    
    if not supplement:
        raise HTTPException(status_code=404, detail="补充协议不存在")
    
    # 软删除
    supplement.is_deleted = True
    db.commit()
    
    return {"message": "补充协议删除成功"}


@router.patch("/{supplement_id}")
def update_supplement(
    supplement_id: int,
    update_data: SupplementUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新补充协议信息"""
    supplement = db.query(Supplement).filter(
        Supplement.id == supplement_id,
        Supplement.is_deleted == False
    ).first()
    
    if not supplement:
        raise HTTPException(status_code=404, detail="补充协议不存在")
    
    # 更新字段
    if update_data.title is not None:
        supplement.title = update_data.title
    
    if update_data.signed_date is not None:
        if update_data.signed_date:
            try:
                supplement.signed_date = datetime.strptime(update_data.signed_date, "%Y-%m-%d")
            except:
                raise HTTPException(status_code=400, detail="日期格式错误")
        else:
            supplement.signed_date = None
    
    if update_data.amount is not None:
        supplement.amount = update_data.amount if update_data.amount else None
    
    db.commit()
    db.refresh(supplement)
    
    return {
        "id": supplement.id,
        "contract_id": supplement.contract_id,
        "title": supplement.title,
        "signed_date": supplement.signed_date.isoformat() if supplement.signed_date else None,
        "amount": supplement.amount,
        "file_path": supplement.file_path,
        "file_size": supplement.file_size,
        "created_at": supplement.created_at.isoformat()
    }
