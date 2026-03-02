import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile
from app.config import config

# 文件大小限制（50MB）
MAX_FILE_SIZE = 50 * 1024 * 1024

class FileStorage:
    def __init__(self):
        config.init_storage()
        self.storage_path = config.STORAGE_PATH
        self.contracts_dir = self.storage_path / "contracts"
        self.supplements_dir = self.storage_path / "supplements"
        self.temp_dir = self.storage_path / "temp"
        
        # 确保supplements目录存在
        self.supplements_dir.mkdir(parents=True, exist_ok=True)
    
    async def save_contract(self, file: UploadFile) -> tuple[str, str]:
        """保存合同文件，包含安全验证"""
        # 1. 检查文件扩展名
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ['.pdf', '.doc', '.docx']:
            raise ValueError("不支持的文件格式，仅支持PDF、DOC、DOCX")
        
        # 2. 读取文件内容
        content = await file.read()
        
        # 3. 检查文件大小
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"文件大小超过限制（最大{MAX_FILE_SIZE // 1024 // 1024}MB）")
        
        # 4. 验证文件头（魔数检查）
        if not self._validate_file_type(content, file_ext):
            raise ValueError(f"文件内容与扩展名不匹配")
        
        # 5. 生成安全的文件名
        file_id = str(uuid.uuid4())
        file_name = f"{file_id}{file_ext}"
        file_path = self.contracts_dir / file_name
        
        # 6. 保存文件
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        relative_path = f"contracts/{file_name}"
        return str(file_path), relative_path
    
    def _validate_file_type(self, content: bytes, ext: str) -> bool:
        """验证文件类型（通过文件头魔数）"""
        if len(content) < 4:
            return False
        
        # PDF文件头: %PDF
        if ext == '.pdf':
            return content[:4] == b'%PDF'
        
        # DOC文件头: D0 CF 11 E0 (OLE2)
        elif ext == '.doc':
            return content[:4] == b'\xD0\xCF\x11\xE0'
        
        # DOCX文件头: PK (ZIP格式)
        elif ext == '.docx':
            return content[:2] == b'PK'
        
        return False
    
    def get_file_path(self, relative_path: str) -> Path:
        """获取文件路径，防止路径遍历攻击"""
        # 规范化路径
        requested_path = (self.storage_path / relative_path).resolve()
        
        # 确保路径在storage_path内
        try:
            requested_path.relative_to(self.storage_path.resolve())
        except ValueError:
            raise ValueError("非法的文件路径")
        
        return requested_path
    
    def delete_file(self, relative_path: str) -> bool:
        try:
            file_path = self.get_file_path(relative_path)
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception:
            return False
    
    def file_exists(self, relative_path: str) -> bool:
        return self.get_file_path(relative_path).exists()
    
    async def save_supplement(self, file: UploadFile, contract_id: int) -> tuple[str, str]:
        """保存补充协议文件"""
        # 1. 检查文件扩展名
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ['.pdf', '.doc', '.docx']:
            raise ValueError("不支持的文件格式，仅支持PDF、DOC、DOCX")
        
        # 2. 读取文件内容
        content = await file.read()
        
        # 3. 检查文件大小
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"文件大小超过限制（最大{MAX_FILE_SIZE // 1024 // 1024}MB）")
        
        # 4. 验证文件头（魔数检查）
        if not self._validate_file_type(content, file_ext):
            raise ValueError(f"文件内容与扩展名不匹配")
        
        # 5. 生成安全的文件名（包含合同ID）
        file_id = str(uuid.uuid4())
        file_name = f"{contract_id}_{file_id}{file_ext}"
        file_path = self.supplements_dir / file_name
        
        # 6. 保存文件
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        relative_path = f"supplements/{file_name}"
        return str(file_path), relative_path
    
    async def save_temp_file(self, file: UploadFile) -> tuple[str, str]:
        """保存临时文件用于分析"""
        # 1. 检查文件扩展名
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ['.pdf', '.doc', '.docx']:
            raise ValueError("不支持的文件格式，仅支持PDF、DOC、DOCX")
        
        # 2. 读取文件内容
        content = await file.read()
        
        # 3. 检查文件大小
        if len(content) > MAX_FILE_SIZE:
            raise ValueError(f"文件大小超过限制（最大{MAX_FILE_SIZE // 1024 // 1024}MB）")
        
        # 4. 验证文件头（魔数检查）
        if not self._validate_file_type(content, file_ext):
            raise ValueError(f"文件内容与扩展名不匹配")
        
        # 5. 生成临时文件名
        file_id = str(uuid.uuid4())
        file_name = f"temp_{file_id}{file_ext}"
        file_path = self.temp_dir / file_name
        
        # 6. 保存文件
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        # 重置文件指针，以便后续可以再次读取
        await file.seek(0)
        
        relative_path = f"temp/{file_name}"
        return str(file_path), relative_path

file_storage = FileStorage()
