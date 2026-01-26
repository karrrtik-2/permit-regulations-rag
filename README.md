# Permit Regulations RAG System

A Retrieval-Augmented Generation (RAG) system that enables semantic search over US and Canadian state permit regulations for oversized/overweight vehicle transportation.

## What It Does

This system scrapes, processes, and indexes state-specific permit regulations from official sources, then allows natural language queries like:
- "What are Michigan's night travel restrictions for oversize loads?"
- "Does Texas require police escorts for superloads?"
- "What are the legal dimensions in California?"

## Architecture

User Query → Embedding Model → Vector Search → Context Retrieval → LLM Response


### Key Features

- **Semantic Search**: Uses sentence transformers (MiniLM-L6) and OpenAI embeddings for accurate retrieval
- **Multi-Model Support**: Compare results between open-source (MiniLM) and commercial (OpenAI Ada-002) embeddings
- **Structured Data Extraction**: Parses HTML regulations into clean JSON format
- **MongoDB Integration**: Stores and indexes permit data with vector search capabilities

## Setup

### Prerequisites

- Python 3.9+
- MongoDB Atlas account (or local MongoDB)
- OpenAI API key (optional, for Ada-002 embeddings)

### Installation

1. Clone the repository
```bash
git clone https://github.com/karrrtik-2/permit-regulations-rag.git
cd permit-regulations-rag
```
