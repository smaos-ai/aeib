---
name: knowledge-retrieval
description: Searches the local PostgreSQL knowledge base for codebase context, architecture patterns, and ingested documents. Use this automatically before writing code, refactoring, or answering questions about the system architecture to prevent hallucinations.
---

# Knowledge Retrieval Pipeline

## Quick Start

You have access to a local Spring Boot search engine (`http://localhost:8081`) connected to a pgvector PostgreSQL database.

### 1. To search for context:

Execute the Python helper script to search the database.

```bash
python .claude/skills/knowledge-retrieval/scripts/search_kb.py "<query>" [optional_language]
```

**Examples:**
- `python .claude/skills/knowledge-retrieval/scripts/search_kb.py "ChunkRepository native SQL"`
- `python .claude/skills/knowledge-retrieval/scripts/search_kb.py "full-text search" java`
- `python .claude/skills/knowledge-retrieval/scripts/search_kb.py "Testcontainers PostgreSQL"`

### 2. To ingest a new repository:

If the user asks you to ingest a repository, trigger the async Spring Boot endpoint:

```bash
curl -X POST http://localhost:8081/api/v1/ingest/start \
  -H "Content-Type: application/json" \
  -d '{"repoPath": "<local_path>", "repoName": "<name>", "repoUrl": "<url>"}'
```

**Response:**
```json
{
  "jobId": "uuid-string",
  "status": "QUEUED",
  "message": "Repository ingestion started in the background."
}
```

## Expected Behavior

- **ALWAYS** search the knowledge base before modifying files you do not fully understand.
- If the search returns no results, broaden your query or try different keywords.
- Do not output raw JSON to the user; synthesize the retrieved chunks into a helpful explanation.
- Include file paths and relevance scores in your explanation to help the user navigate the codebase.

## When to Use This Skill

Automatically invoke this skill when:
1. **Before writing code** in unfamiliar parts of the system
2. **When refactoring** — search for all usages of the component being changed
3. **Answering architecture questions** — ground answers in retrieved documents
4. **Investigating bugs** — search for error messages, exception types, or related functionality
5. **Understanding patterns** — search for "pattern", "strategy", or specific technique names

## Search Best Practices

| Goal | Query Example |
|------|-------|
| Find all usages of a class | `"LocalGitIngestionService"` |
| Find test strategies | `"Testcontainers integration test"` |
| Find API contracts | `"POST /api/v1/ingest"` |
| Find schema info | `"CREATE TABLE chunk"` |
| Find error handling | `"exception DataIntegrityViolation"` |
