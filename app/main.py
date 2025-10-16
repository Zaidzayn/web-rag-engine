# app/main.py
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from . import schemas, database, services, celery_worker
import uuid

# Create DB tables on startup
database.create_tables()

# Ensure Qdrant collection exists on startup
services.setup_qdrant_collection()

app = FastAPI(title="Web-Aware RAG Engine", version="1.0.0")

@app.post("/ingest-url", status_code=202, response_model=schemas.IngestResponse)
def ingest_url(request: schemas.IngestRequest, req: Request, db: Session = Depends(database.get_db)):
    """Accepts a URL and queues it for background ingestion."""
    # Check for existing URL
    existing_doc = db.query(database.Document).filter(database.Document.source_url == str(request.url)).first()
    if existing_doc:
        raise HTTPException(status_code=409, detail="This URL has already been submitted.")

    new_doc = database.Document(source_url=str(request.url))
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    # Dispatch task to Celery
    celery_worker.process_ingestion_task.delay(str(new_doc.id), str(request.url))
    
    status_url = req.url_for('get_ingestion_status', document_id=new_doc.id)
    
    return {
        "message": "URL accepted for ingestion.",
        "document_id": new_doc.id,
        "status_endpoint": str(status_url)
    }

@app.get("/status/{document_id}", response_model=schemas.DocumentStatus)
def get_ingestion_status(document_id: uuid.UUID, db: Session = Depends(database.get_db)):
    """Retrieves the ingestion status of a specific document."""
    doc = db.query(database.Document).filter(database.Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc

@app.post("/query", response_model=schemas.QueryResponse)
def query_knowledge_base(request: schemas.QueryRequest):
    """Queries the knowledge base to get a grounded answer."""
    if not request.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    
    result = services.perform_query(request.question, request.top_k)
    return result