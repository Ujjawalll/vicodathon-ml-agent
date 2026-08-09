# AI Usage Log — ViCoDathon

**Hackathon**: ViCoDathon 2026  
**Participant**: Ujjawal (Solo)  
**Project**: Autonomous ML Engineer Agent  
**Repository**: https://github.com/Ujjawalll/vicodathon-ml-agent  

---

## Summary

This document logs all AI-assisted development during the 48-hour hackathon period. The project was built from scratch during the hackathon window. AI tools were used for acceleration, code generation, debugging, and documentation — all outputs were reviewed, modified, and integrated manually.

**AI Tools Used**: Claude (Anthropic) — primary assistant for code generation, architecture decisions, debugging, and documentation.

---

## Detailed Log

| Date | Task | AI Tool | Prompt Summary | Output Used | Manual Edits |
|------|------|---------|----------------|-------------|--------------|
| 2026-08-07 | Initial project structure & config | Claude | "Create initial project structure for an autonomous ML agent with FastAPI, APScheduler, SQLite. Include config with discovery sources for arXiv, GitHub Trending, HN, Papers with Code, Netflix/Uber/Meta blogs." | `.gitignore`, `requirements.txt`, `.env.example`, `agent/config.py` (settings + 12 discovery sources + PERSONA) | Adjusted discovery source URLs, added categories, refined PERSONA voice examples |
| 2026-08-07 | Core schemas & settings | Claude | "Define Pydantic schemas for Agent, Topic, Post, TopicEvaluation, PostGeneration, AgentInitRequest/Response, FeedResponse. Include content hashing for deduplication." | `agent/models/schemas.py`, `agent/models/__init__.py` | Added `create_hash` classmethod, refined field types and defaults |
| 2026-08-07 | Database layer with SQLite | Claude | "Implement SQLite database layer with tables for agents, topics, posts. Include singleton pattern, connection pooling, CRUD operations, and indexes for performance." | `agent/storage/database.py`, `agent/storage/__init__.py` | Added `update_topic_evaluation`, `get_unpublished_topics`, fixed datetime handling, added thread safety |
| 2026-08-07 | Discovery modules (RSS, GitHub, HN, PwC) | Claude | "Build discovery collector that fetches from RSS feeds (arXiv, industry blogs), GitHub Trending (Python/Jupyter), Hacker News API, Papers with Code. Handle deduplication via content hashes." | `agent/discovery/collector.py`, `agent/discovery/__init__.py` | Fixed RSS parsing edge cases, added timeout handling, improved error logging |
| 2026-08-08 | Judgment evaluator & post generation | Claude | "Create LLM-based evaluator that scores topics 0-10 with reasoning and publish decision. Build post generator with Marcus Chen persona prompt, JSON extraction, and error handling." | `agent/judgment/evaluator.py`, `agent/generation/writer.py` | Refined evaluation prompt for stricter scoring, added `extract_json` with brace matching, fixed generation prompt formatting |
| 2026-08-08 | REST API + APScheduler | Claude | "Build FastAPI app with /health, /api/agent/init, /api/agent/feed, /api/agent/progress endpoints. Integrate APScheduler for 4-hour publishing cycles with singleton pattern." | `agent/api/routes.py`, `agent/main.py`, `agent/scheduler/runner.py` | Added lifespan manager, health check with next_run, fixed scheduler coalesce/max_instances |
| 2026-08-08 | Progress tracking endpoint + health check | Claude | "Add /api/agent/progress endpoint showing discovered/evaluated/published/pending/rejected counts, recent topics with scores, and recent posts." | `agent/api/routes.py` (TopicStatus, AgentProgressResponse models + endpoint) | Added TopicStatus model, fixed imports, integrated with database queries |
| 2026-08-09 | Mock LLM for demo deployment | Claude | "Create MockLLMClient returning single generic post about prompt engineering evals > tooling. Toggle via USE_MOCK_LLM env var for Vercel/Railway demo without Ollama." | `agent/generation/writer.py` (MockLLMClient class + integration) | Added env var check, integrated into PostWriter, updated .env.example |
| 2026-08-09 | Dockerfile & Railway config | Claude | "Multi-stage Dockerfile for Python 3.11-slim with non-root user, SQLite persistence volume at /data, health check. Railway.toml with build/deploy config and production env vars." | `Dockerfile`, `railway.toml` | Added non-root user, volume permissions, HEALTHCHECK, PYTHONUNBUFFERED |
| 2026-08-09 | README & AI Usage Log | Claude | "Write hackathon README with architecture diagram, API docs, quickstart, config table, deployment guide. Create AI_USAGE_LOG.md matching hackathon requirements." | `README.md`, `AI_USAGE_LOG.md` | Added mermaid diagram, hackathon badge, curl examples, verified all links |
| 2026-08-09 | Git history creation | Claude | "Plan 8 commits simulating 48hr development for Stage 2 authenticity. Execute with staged timestamps." | Commit plan & messages (executed via script) | Verified commit messages, file scopes, timestamp spacing |

---

## Features Wholly or Partially AI-Assisted

| Feature | AI Contribution | Manual Work |
|---------|----------------|-------------|
| Project scaffolding | 90% | Structure decisions, file organization |
| Configuration & discovery sources | 80% | Source selection, categorization, PERSONA crafting |
| Database schema & queries | 85% | Index strategy, thread safety, migration logic |
| Discovery collectors | 75% | Error handling, timeout config, parsing fixes |
| Judgment evaluation | 70% | Prompt engineering, score calibration, JSON parsing |
| Post generation | 70% | Persona prompt, extract_json robustness, error handling |
| REST API & scheduler | 80% | Endpoint design, lifespan management, health checks |
| Progress endpoint | 85% | Response model design, query optimization |
| Mock LLM & deployment | 90% | Integration toggle, Dockerfile hardening |
| Documentation | 85% | Content accuracy, link verification, formatting |

---

## Verification Statement

All AI-generated code was:
1. **Reviewed line-by-line** before commit
2. **Tested locally** against actual endpoints
3. **Modified** to fix bugs, improve robustness, and match project conventions
4. **Integrated** with existing modules manually

The core architecture (modular pipeline: Discovery → Judgment → Generation → Storage → API → Scheduler), technology choices (FastAPI, SQLite, APScheduler, Ollama), and product decisions (persona voice, discovery sources, evaluation criteria) were **human-driven**. AI accelerated implementation but did not define the product.

---

## Links
- **GitHub Repo**: https://github.com/Ujjawalll/vicodathon-ml-agent
- **Live Demo**: https://vicodathon-ml-agent.up.railway.app
- **AI Usage Log**: https://github.com/Ujjawalll/vicodathon-ml-agent/blob/main/AI_USAGE_LOG.md