from pydantic import BaseModel
from typing import Optional, List, Literal, Dict, Any


class AgentOperation(BaseModel):
    action: Literal["list_contracts", "get_contract", "delete_contract", "reparse_contract", "consult"]
    contract_id: Optional[int] = None
    filters: Optional[Dict[str, Any]] = None


class AgentChatRequest(BaseModel):
    message: str
    confirm: bool = False
    operation: Optional[AgentOperation] = None
    conversation_id: Optional[str] = None


class AgentChatResponse(BaseModel):
    reply: str
    requires_confirmation: bool = False
    operation: Optional[AgentOperation] = None
    data: Optional[List[Dict[str, Any]]] = None
    conversation_id: Optional[str] = None
    provider: Optional[Literal["ark", "appbuilder", "qianfan", "rule"]] = None
    error_detail: Optional[str] = None
