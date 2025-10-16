# Scalable, Web-Aware RAG Engine

This project is a complete, production-ready system designed to asynchronously ingest web content and create a searchable knowledge base. It provides a simple API for users to ask grounded, fact-based questions against the ingested information.

The architecture is built around a hybrid AI model: it leverages a **local, private embedding model** for robust and cost-effective data processing, combined with a **high-speed cloud LLM (Groq)** for real-time, low-latency answer generation.

---

## 🏛️ System Architecture

The system is designed with a decoupled, message-driven architecture to ensure scalability, resilience, and responsiveness. The user-facing API is separated from the heavy-lifting of data processing, which happens asynchronously in background workers.


graph TD
    subgraph "User Interaction"
        User -- "1. POST /ingest-url" --> API[API Server (FastAPI)]
        API -- "2. Returns 202 Accepted" --> User
        User -- "A. POST /query" --> API
        API -- "F. Returns Answer" --> User
    end

    subgraph "Backend Processing (Asynchronous)"
        API -- "3. Creates PENDING record" --> MetaDB[(Metadata DB - PostgreSQL)]
        API -- "4. Enqueues Job" --> Queue[(Task Queue - Redis)]
        Worker[Celery Worker(s)] -- "5. Polls for jobs" --> Queue
        Worker -- "6. Scrapes, Chunks, Embeds (Locally)" --> LocalModel["Local Embedding Model (SentenceTransformer)"]
        LocalModel -- "Vectors" --> Worker
        Worker -- "7. Stores Vectors" --> VecDB[(Vector DB - Qdrant)]
        Worker -- "8. Updates status to COMPLETED" --> MetaDB
    end

    subgraph "Query Path (Synchronous)"
        API -- "B. Embeds Question" --> LocalModel
        API -- "C. Searches for Context" --> VecDB
        API -- "D. Sends Context + Question" --> Groq["Groq Cloud API (Llama 3)"]
        Groq -- "E. Generates Answer" --> API
    end

    style User fill:#cde,stroke:#333
    style Groq fill:#cde,stroke:#333

---

## ⚙️ Technology Stack & Justification

| Component           | Technology                               | Justification                                                                                                                                                                                                                                                         |
| ------------------- | ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Web Framework** | `FastAPI`                                | **High-performance and asynchronous** by nature, making it ideal for I/O-bound operations. Built-in data validation with Pydantic ensures robust and clean API contracts.                                                                                              |
| **Task Queue** | `Celery` + `Redis`                       | **Industry-standard** for background task processing in Python. This decouples the API from heavy workloads, enabling asynchronous ingestion, retries, and independent scaling of processing power. Redis serves as a simple and fast message broker.                 |
| **Vector Database** | `Qdrant`                                 | **Production-grade and performant.** As a standalone service, it's optimized for high-speed vector similarity search and supports metadata filtering, which is critical for scalable RAG systems.                                                                      |
| **Metadata DB** | `PostgreSQL`                             | **Reliable and robust.** It provides strong transactional integrity for tracking the state of ingestion jobs. Its maturity and powerful querying capabilities make it the definitive source of truth for our system's metadata.                                        |
| **Embedding Model** | `SentenceTransformers` (Local)           | **Private, cost-effective, and rate-limit-proof.** By running a state-of-the-art embedding model locally, we gain full control over the most frequent ML task, avoiding external API costs and limitations, which proved to be a bottleneck with cloud embedding APIs. |
| **Generative LLM** | `Groq` (Llama 3)                         | **Extreme low latency.** Groq's LPU inference engine is purpose-built for speed, making the user-facing query API feel instantaneous. This provides an excellent user experience for real-time Q&A.                                                                    |
| **Containerization**| `Docker` & `Docker Compose`            | **Reproducibility and isolation.** Docker encapsulates each service into a portable container, simplifying setup, development, and deployment across any environment. Docker Compose orchestrates the entire multi-container application with a single command.        |

---

## 🗃️ Database Schema

### Metadata Store (PostgreSQL)

A single table, `documents`, acts as the source of truth for the status and metadata of each ingestion job.

**Table: `documents`**
```sql
CREATE TYPE ingestion_status AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_url VARCHAR(2048) NOT NULL UNIQUE,
    status ingestion_status NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
);
```
- `id`: The primary key, used to link vectors in Qdrant back to their source.
- `source_url`: The unique URL to be processed, preventing duplicate ingestions.
- `status`: Tracks the job's state, crucial for monitoring and debugging.

### Vector Store (Qdrant)

A Qdrant collection named `web_content` stores the vector embeddings and their associated text.

**Collection Point Structure:**
- **Vector:** A high-dimensional float array (384 dimensions for `all-MiniLM-L6-v2`).
- **Payload:** A JSON object containing the context and a foreign key.
    ```json
    {
        "text": "This is a chunk of text from the webpage...",
        "document_id": "eb999f6c-29c4-4481-b713-776424595852",
        "url": "[https://example.com/some-article](https://example.com/some-article)"
    }
    ```
- **ID:** Each point has its own unique UUID, ensuring every text chunk is a distinct entry.

---

## 📡 API Documentation

### Ingest URL

Submits a new URL for asynchronous background processing.

- **Endpoint:** `POST /ingest-url`
- **Request Body:**
    ```json
    {
        "url": "[https://example.com/some-article-to-process](https://example.com/some-article-to-process)"
    }
    ```
- **Success Response:** `202 Accepted`
    ```json
    {
        "message": "URL accepted for ingestion.",
        "document_id": "eb999f6c-29c4-4481-b713-776424595852",
        "status_endpoint": "http://localhost:8000/status/eb999f6c-29c4-4481-b713-776424595852"
    }
    ```
- **`curl` Example (CMD/Bash):**
    ```bash
    curl -X POST http://localhost:8000/ingest-url -H "Content-Type: application/json" -d "{\"url\": \"[https://wow.groq.com/lpu-inference-engine/](https://wow.groq.com/lpu-inference-engine/)\"}"
    ```
- **PowerShell Example:**
    ```powershell
    Invoke-WebRequest -Uri http://localhost:8000/ingest-url -Method POST -Headers @{"Content-Type"="application/json"} -Body '{"url": "[https://wow.groq.com/lpu-inference-engine/](https://wow.groq.com/lpu-inference-engine/)"}'
    ```

### Query Knowledge Base

Asks a question against the ingested content.

- **Endpoint:** `POST /query`
- **Request Body:**
    ```json
    {
        "question": "What is an LPU?",
        "top_k": 3
    }
    ```
- **Success Response:** `200 OK`
    ```json
    {
        "answer": "An LPU, or Language Processing Unit, is a new type of processing unit system created by Groq, purpose-built for the sequential nature of Large Language Models to provide fast AI inference.",
        "context": [
            {
                "text": "The Groq LPU is a new type of end-to-end processing unit system that provides the fastest inference...",
                "url": "[https://wow.groq.com/lpu-inference-engine/](https://wow.groq.com/lpu-inference-engine/)",
                "score": 0.91
            }
        ]
    }
    ```
- **`curl` Example (CMD/Bash):**
    ```bash
    curl -X POST http://localhost:8000/query -H "Content-Type: application/json" -d "{\"question\": \"What is an LPU?\"}"
    ```
- **PowerShell Example:**
    ```powershell
    Invoke-WebRequest -Uri http://localhost:8000/query -Method POST -Headers @{"Content-Type"="application/json"} -Body '{"question": "What is an LPU?"}'
    ```

---

## 🛠️ Setup and Deployment

1.  **Prerequisites:** Ensure you have **Docker** and **Docker Compose** installed and running on your system.

2.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/your-username/web-rag-engine.git](https://github.com/your-username/web-rag-engine.git)
    cd web-rag-engine
    ```

3.  **Configure Environment Variables:** Create a `.env` file from the provided example and add your Groq API key.
    ```bash
    # For Windows
    copy .env.example .env

    # For macOS/Linux
    cp .env.example .env
    ```
    Open the newly created `.env` file and paste your `GROQ_API_KEY`.

4.  **Build and Run Services:** Use Docker Compose to build the application image and start all services.
    ```bash
    docker-compose up --build
    ```
    The first time you run this, it may take a few minutes to download the base images and the local embedding model. Subsequent startups will be much faster.

5.  **Stop Services:** To stop all running containers, press `Ctrl+C` in the terminal, then run:
    ```bash
    docker-compose down
    ```