from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class ContractBase(BaseModel):
    title: str
    contract_type: str
    department: str
    parties: List[str]
    amount: Optional[float] = None
    currency: str = "CNY"
    start_date: datetime
    end_date: datetime

class ContractCreate(ContractBase):
    pass

class ContractUpdate(BaseModel):
    title: Optional[str] = None
    contract_type: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None
    parties: Optional[List[str]] = None
    amount: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    summary: Optional[str] = None

class ContractResponse(BaseModel):
    id: int
    contract_number: str
    title: str
    contract_type: str
    department: str
    status: str
    parties: str
    amount: Optional[float] = None
    currency: str = "CNY"
    signed_date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    file_path: str
    summary: Optional[str] = None
    risk_level: Optional[str] = None
    risk_analysis: Optional[str] = None
    raw_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    source: Optional[str] = None

    class Config:
        from_attributes = True

class ContractListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    contracts: List[ContractResponse]

class ExtractData(BaseModel):
    contract_number: Optional[str] = None
    title: Optional[str] = None
    parties: Optional[List[str]] = None
    amount: Optional[float] = None
    contract_type: Optional[str] = None
    department: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class UploadResponse(BaseModel):
    contract_id: int
    contract_number: str
    file_path: str
    message: str
    note: Optional[str] = None
    extracted_data: Optional[ExtractData] = None
