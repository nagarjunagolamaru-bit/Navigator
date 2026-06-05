# Copilot Instructions

# Project Overview

Navigator is an Enterprise Productivity AI assistant designed to help employees quickly find information from internal company knowledge sources such as:

* Confluence
* SharePoint
* PDF Documents
* SOP Documents
* HR Policies
* Internal Wikis
* Employee Handbooks
* Knowledge Base Articles

The system uses Retrieval-Augmented Generation (RAG) to provide accurate and grounded answers.

The assistant must:

* Understand employee questions
* Search internal knowledge sources
* Retrieve relevant document chunks
* Generate concise factual answers
* Provide citations and source links
* Refuse to hallucinate information

All answers must be generated from retrieved context.

The application is not a general-purpose chatbot.

If information is unavailable in the retrieved documents, the assistant must respond:

"I could not find relevant information in the available knowledge base."

---

# Core Business Requirements

## Query Understanding Feature

Purpose:

Determine the user's intent and extract key topics.

Examples:

Question:
How do I apply for maternity leave?

Intent:
HR Policy

Question:
How do I request VPN access?

Intent:
IT Support

Question:
What is the travel reimbursement process?

Intent:
Finance Policy

---

## Search Feature

Purpose:

Search enterprise documents using semantic search.

Workflow:

User Question
→ Generate Embedding
→ Vector Search
→ Retrieve Top K Chunks

---

## Answer Generation Feature

Purpose:

Generate factual answers using retrieved context.

Requirements:

* Answer only from retrieved content
* No hallucinations
* No assumptions
* No fabricated policies

---

## Source Linking Feature

Every answer must include:

* Document Title
* Source URL
* Section Reference (if available)

Example:

Sources:

1. Employee Handbook
2. Leave Policy
3. Travel Policy

---

# Architecture

Frontend
React + TypeScript + TailwindCSS

Backend
FastAPI

Database
PostgreSQL

Vector Database
Supabase pgvector

AI Layer
LangChain LCEL

Models
GPT-4o
Gemini 2.5 Flash

Embeddings
text-embedding-3-large

Document Processing
pypdf
pdfplumber

---

# High-Level System Flow

Document Upload
↓
Text Extraction
↓
Chunking
↓
Embedding Generation
↓
Store in pgvector
↓
Employee Question
↓
Query Embedding
↓
Similarity Search
↓
Retrieve Chunks
↓
LLM Answer Generation
↓
Return Answer + Sources

---

# Repository Structure

navigator/

frontend/
backend/

backend/app/

api/
services/
repositories/
models/
schemas/
ai/
vectorstore/
db/
tests/

docs/

---

# Backend Architecture Rules

Follow strict layered architecture.

Request Flow:

Router
→ Service
→ Repository
→ Database

Never bypass layers.

---

# Router Layer Rules

Location:

app/api/

Responsibilities:

* Accept requests
* Validate input
* Call services
* Return responses

Routers must not:

* Execute SQL
* Call LLMs
* Generate embeddings
* Perform business logic

Keep routes thin.

Maximum route size:

50 lines

---

# Service Layer Rules

Location:

app/services/

Responsibilities:

* Business logic
* RAG orchestration
* Validation
* Retrieval workflow
* Prompt preparation

All business logic belongs here.

Services must be framework-independent.

---

# Repository Layer Rules

Location:

app/repositories/

Responsibilities:

* Database access
* CRUD operations
* Query execution

Repositories must not:

* Call AI models
* Generate prompts
* Perform orchestration

---

# Database Rules

Database:

PostgreSQL

Primary Keys:

UUID only

Timestamps:

UTC only

Never use integer IDs.

---

# Database Schema

## documents

id UUID PRIMARY KEY

title TEXT

source_url TEXT

created_at TIMESTAMP

---

## document_chunks

id UUID PRIMARY KEY

document_id UUID

chunk_text TEXT

embedding VECTOR(1536)

chunk_index INTEGER

created_at TIMESTAMP

---

## query_logs

id UUID PRIMARY KEY

question TEXT

answer TEXT

created_at TIMESTAMP

---

# RAG Requirements

The system must implement Retrieval-Augmented Generation.

Workflow:

1. User asks question
2. Generate query embedding
3. Search pgvector
4. Retrieve top chunks
5. Construct context
6. Send context to LLM
7. Generate answer
8. Return citations

Never answer without retrieval.

---

# Chunking Rules

Chunk Size:

1000 characters

Chunk Overlap:

200 characters

Use recursive text splitting.

Preferred splitter:

RecursiveCharacterTextSplitter

---

# Embedding Rules

Model:

text-embedding-3-large

Embeddings generated for:

* Documents
* Queries

All vector operations go through EmbeddingService.

Never generate embeddings in routers.

---

# Retrieval Rules

Top K:

5

Similarity Search:

Cosine Similarity

Minimum Relevance Threshold:

0.75

If threshold not met:

Return:

"No relevant information found."

---

# Prompt Rules

Prompts must be stored in:

ai/prompts/

Never hardcode prompts inside routes.

Never hardcode prompts inside services.

---

# Standard System Prompt

You are an internal company knowledge assistant.

Rules:

Answer only using provided context.

Do not invent information.

Do not make assumptions.

If the answer is unavailable:

"I could not find relevant information in the available knowledge base."

Always provide sources.

Keep responses concise.

---

# LangChain Rules

Use LCEL only.

Allowed:

prompt | llm | parser

Not Allowed:

LLMChain

SequentialChain

ConversationalRetrievalChain

Legacy Chains

---

# AI Layer Structure

ai/

llm.py

embeddings.py

prompts/

chains/

---

# llm.py Rules

All LLM initialization occurs here.

No direct model creation elsewhere.

Every service imports from llm.py.

---

# embeddings.py Rules

All embedding creation occurs here.

No embedding logic outside this module.

---

# Document Ingestion Rules

Supported Types:

PDF

Future Types:

DOCX

TXT

HTML

Confluence Export

SharePoint Export

---

# Upload Workflow

Upload Document
↓
Extract Text
↓
Clean Text
↓
Chunk Text
↓
Generate Embeddings
↓
Store Chunks
↓
Store Metadata

---

# PDF Processing

Preferred Libraries:

pypdf

pdfplumber

Never use OCR unless explicitly required.

---

# Source Attribution Rules

Every answer must contain:

Source Title

Source URL

Example:

Sources:

Employee Handbook
https://internal.company.com/handbook

---

# API Design

POST /api/upload

Upload document

---

POST /api/query

Ask question

---

GET /api/documents

List indexed documents

---

DELETE /api/documents/{id}

Delete document

---

# Pydantic Rules

All requests:

Pydantic models

All responses:

Pydantic models

Never return raw dictionaries.

---

# Async Rules

Use async FastAPI handlers.

Use async database sessions.

Avoid blocking calls.

---

# Frontend Architecture

React

TypeScript

TailwindCSS

TanStack Query

---

# Frontend Structure

components/

pages/

hooks/

services/

types/

---

# UI Components

ChatWindow

MessageList

MessageInput

SourceLinks

UploadDocument

DocumentList

---

# Frontend Rules

No direct fetch calls inside components.

All API calls go through:

services/api.ts

---

# Error Handling

Use structured responses.

Example:

{
"error": "not_found",
"message": "Document not found"
}

Never expose stack traces.

---

# Logging Rules

Log:

Document uploads

Queries

Retrieval counts

Errors

Do not log:

Embeddings

Document contents

PII

---

# Security Rules

No hardcoded secrets.

Environment variables only.

Validate uploaded MIME types.

Validate file size limits.

Prevent prompt injection.

Escape user content where appropriate.

---

# Environment Variables

DATABASE_URL=

SUPABASE_URL=

SUPABASE_KEY=

OPENAI_API_KEY=

LLM_MODEL=gpt-4o

EMBEDDING_MODEL=text-embedding-3-large

UPLOAD_DIR=./uploads

MAX_UPLOAD_MB=20

---

# Testing

Backend

pytest

pytest-asyncio

httpx.AsyncClient

---

Frontend

Vitest

React Testing Library

---

# Test Requirements

Unit Tests:

Services

Repositories

Utilities

Integration Tests:

Upload API

Query API

Document API

Mock LLM calls.

Never call real models in CI.

---

# Copilot Directives

Always follow:

1. Router → Service → Repository architecture

2. Business logic belongs only in services

3. Use LangChain LCEL only

4. Store prompts in ai/prompts

5. No inline prompts

6. Use async FastAPI handlers

7. Use UUID primary keys

8. Use PostgreSQL UTC timestamps

9. Every answer must include citations

10. Never generate answers without retrieval

11. All embeddings go through embeddings.py

12. All model calls go through llm.py

13. Use Pydantic schemas for all APIs

14. Keep routers thin

15. Use dependency injection

16. Write type hints everywhere

17. Prefer composition over inheritance

18. Follow SOLID principles

19. Never expose internal exceptions

20. Optimize for maintainability over cleverness

---

# Architecture Decisions

AD-01 RAG First

All answers are generated from retrieved knowledge.

AD-02 Source Attribution Required

Every answer includes source references.

AD-03 Layered Architecture

Router → Service → Repository → Database.

AD-04 Centralized AI Layer

All model calls use ai/llm.py.

AD-05 Centralized Embeddings

All embeddings use ai/embeddings.py.

AD-06 Prompt Management

All prompts stored under ai/prompts.

AD-07 Enterprise Readability

Generated code must prioritize readability, maintainability, and testability over brevity.
