# app/schemas.py
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import uuid

class IngestRequest(BaseModel):
    url: HttpUrl

class IngestResponse(BaseModel):
    message: str
    document_id: uuid.UUID
    status_endpoint: str
    
class DocumentStatus(BaseModel):
    document_id: uuid.UUID
    status: str
    source_url: str
    error_message: Optional[str] = None
    
class QueryRequest(BaseModel):
    question: str
    top_k: int = 3

class ContextChunk(BaseModel):
    text: str
    url: str
    score: float

class QueryResponse(BaseModel):
    answer: str
    context: List[ContextChunk]