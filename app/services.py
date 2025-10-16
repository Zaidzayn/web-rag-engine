## app/services.py
import logging
from newspaper import Article
from qdrant_client import QdrantClient, models
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer
from groq import Groq
import uuid

from .config import settings
from .database import SessionLocal, Document, IngestionStatus

# --- Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Initialize the local sentence-transformer model
# This model will be downloaded automatically the first time it's used.
logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL_NAME}")
embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
EMBEDDING_DIMENSION = embedding_model.get_sentence_embedding_dimension()
logger.info(f"Embedding model loaded. Vector dimension: {EMBEDDING_DIMENSION}")

# 2. Initialize the Groq client
try:
    groq_client = Groq(api_key=settings.GROQ_API_KEY)
    logger.info("Groq client configured successfully.")
except Exception as e:
    logger.error(f"Failed to configure Groq client: {e}")

# 3. Initialize the Qdrant client
qdrant_client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
QDRANT_COLLECTION_NAME = "web_content"

# --- Helper Functions ---
def setup_qdrant_collection():
    """Ensures the Qdrant collection exists with the correct vector size."""
    try:
        qdrant_client.get_collection(collection_name=QDRANT_COLLECTION_NAME)
        logger.info(f"Qdrant collection '{QDRANT_COLLECTION_NAME}' already exists.")
    except Exception:
        logger.info(f"Qdrant collection '{QDRANT_COLLECTION_NAME}' not found. Creating...")
        qdrant_client.recreate_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=EMBEDDING_DIMENSION,  # Use the dimension from our local model
                distance=models.Distance.COSINE
            ),
        )
        logger.info("Collection created successfully.")

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> list[str]:
    # (No changes to this function)
    if not text: return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return chunks

# --- Core Service Logic ---
def process_url_content(document_id: str, url: str):
    """The main ingestion pipeline function called by the Celery worker."""
    db: Session = SessionLocal()
    try:
        # 1. Update status to PROCESSING
        doc = db.query(Document).filter(Document.id == document_id).one()
        doc.status = IngestionStatus.PROCESSING
        db.commit()

        # 2. Scrape and clean content
        logger.info(f"[{document_id}] Scraping URL: {url}")
        article = Article(url)
        article.download()
        article.parse()
        content = article.text
        if not content: raise ValueError("Failed to extract content from URL.")

        # 3. Chunk the text
        text_chunks = chunk_text(content)
        logger.info(f"[{document_id}] Text split into {len(text_chunks)} chunks.")

        # 4. Embed chunks using the LOCAL model
        embeddings = embedding_model.encode(text_chunks, show_progress_bar=True).tolist()
        logger.info(f"[{document_id}] Generated {len(embeddings)} embeddings locally.")

        # 5. Store in Qdrant
        qdrant_client.upsert(
            collection_name=QDRANT_COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={"text": chunk, "document_id": document_id, "url": url}
                )
                for i, (chunk, embedding) in enumerate(zip(text_chunks, embeddings))
            ]
        )
        logger.info(f"[{document_id}] Upserted {len(embeddings)} points to Qdrant.")

        # 6. Update status to COMPLETED
        doc.status = IngestionStatus.COMPLETED
        db.commit()
        logger.info(f"[{document_id}] Ingestion COMPLETED.")

    except Exception as e:
        logger.error(f"[{document_id}] Ingestion FAILED. Error: {e}", exc_info=True)
        if 'doc' in locals():
            doc.status = IngestionStatus.FAILED
            doc.error_message = str(e)
            db.commit()
    finally:
        db.close()

def perform_query(question: str, top_k: int):
    """Performs semantic search and generates a grounded answer using Groq."""
    # 1. Embed the query using the LOCAL model
    query_vector = embedding_model.encode(question).tolist()

    # 2. Search Qdrant for relevant chunks
    search_results = qdrant_client.search(
        collection_name=QDRANT_COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
        with_payload=True
    )
    
    context_chunks = [
        {"text": point.payload['text'], "url": point.payload['url'], "score": point.score}
        for point in search_results
    ]

    if not context_chunks:
        return {"answer": "I could not find any relevant information in the knowledge base.", "context": []}

    # 3. Generate a grounded answer with Groq
    context_str = "\n---\n".join([chunk['text'] for chunk in context_chunks])
    
    chat_completion = groq_client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a helpful AI assistant. Answer the user's question based ONLY on the context provided. If the context does not contain the answer, state that you cannot answer the question with the given information."
            },
            {
                "role": "user",
                "content": f"CONTEXT:\n{context_str}\n\nQUESTION:\n{question}"
            }
        ],
        model=settings.GENERATIVE_MODEL_NAME,
    )
    
    answer = chat_completion.choices[0].message.content
    
    return {"answer": answer, "context": context_chunks}