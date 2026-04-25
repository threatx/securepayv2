# AI Disclosure Statement — SecurePay V2

**Course:** CS6747
**Student:** Yajwin Jain

---

## 1. AI Tools Used

| Tool | Version | Purpose |
|------|---------|---------|

---

## 2. AI Usage by Component

### 2.1 Data Pipeline Documentation (`PIPELINE.md`)
- **AI usage:** Improving content, formatting, and structuring the pipeline documentation (Anthropic, 2026)
- **Student contribution:** Pipeline architecture design, agent flow design, stage sequencing, quality criteria

### 2.2 Pipeline Agents (`.claude/agents/`)
Agents: extractor, validator, scam_verifier, dedup_checker, patterns_extractor, scenario_classifier, patterns_verifier, ingestor, tracker
- **AI usage:** Formatting, grammar improvements, and strengthening agent prompt content (Anthropic, 2026)
- **Student contribution:** Higher-level design of each agent's role, pipeline flow, validation rules, taxonomy definition, and quality thresholds

### 2.3 Data Scrapers (`scrapers/`)
Scripts: `reddit_scraper.py`, `reddit_converter.py`, `google_news_scraper.py`, `playstore_scraper.py`, `verifier.py`, `v2/reddit_scraper.py`, `v2/reddit_allsearch.py`, `v2/consumercomplaints_scraper.py`
- **AI usage:** Entire code generation — all scraper code was completely created through AI (Anthropic, 2026)
- **Student contribution:** Requirements specification, target source identification, output format definition, testing and validation of scraped data

### 2.4 Embeddings Generation (`scripts/generate_hierarchical_embeddings.py`)
- **AI usage:** Implementing complex code logic (Anthropic, 2026)
- **Student contribution:** Coding, architecture design, requirements definition, testing

### 2.5 RAG Analyzer & Hierarchical Search (`app/backend/`)
Files: `rag_analyzer.py`, `hierarchical_search.py`
- **AI usage:** Code review, syntax corrections, formatting, sentence construction, and prompt construction for LLM calls (Anthropic, 2026)
- **Student contribution:** Entire code written by student — architecture, implementation, testing

### 2.6 Foundation Backend (`app/backend/`)

**`db.py`** — No AI usage. Entirely written by student.

**`embeddings.py`**
- **AI usage:** Adding comments and error handling (Anthropic, 2026)
- **Student contribution:** Core implementation, architecture, testing

**`search.py`**
- **AI usage:** Writing test statements (Anthropic, 2026)
- **Student contribution:** Core implementation, architecture, testing

### 2.7 Community Platform (`app/backend/community.py`)
- **AI usage:** Formatting and syntax (Anthropic, 2026)
- **Student contribution:** Core implementation, architecture, testing

### 2.8 Awareness Chatbot (`app/backend/awareness_chatbot.py`)
- **AI usage:** Writing LLM prompts (Anthropic, 2026)
- **Student contribution:** Core implementation, architecture, RAG pipeline design, testing

### 2.9 Awareness Search (`app/backend/awareness_search.py`)
- No AI usage. Entirely written by student.

### 2.10 API Server (`app/backend/api.py`)
- **AI usage:** Code generation (Anthropic, 2026)
- **Student contribution:** High-level pseudocode, requirements definition

### 2.11 Frontend (`app/frontend/`)
Files: `index.html`, `community.html`, `awareness.html`, `css/style.css`, `css/community.css`, `css/awareness.css`, `js/app.js`, `js/community.js`, `js/awareness.js`
- **AI usage:** Code generation (Anthropic, 2026)
- **Student contribution:** Requirements definition, UI design, testing

### 2.12 Pipeline Scripts (`scripts/`)
Scripts: `ingest.py`, `get_next_batch.py`, `check_dedup.py`
- **AI usage:** Making code cleaner and well-structured, implementing complex code logic (Anthropic, 2026)
- **Student contribution:** High-level pseudocode, coding, requirements definition, testing

---

## 3. Development Process

---

## 4. Responsibility Statement

All AI-generated content was reviewed, tested, and validated by the student. The student is responsible for the final submitted work, including all code, documentation, and analysis.

---

## 5. References
