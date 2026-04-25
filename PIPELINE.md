<!-- AI-Assisted Development Notice -->
<!-- This file was developed with AI assistance using Claude Code CLI (Anthropic, 2026). -->
<!-- AI was used for: improving content, formatting, and structuring pipeline documentation -->
<!-- Student contribution: pipeline architecture design, agent flow design, stage sequencing, quality criteria -->
<!-- Reference: Anthropic. (2026). Claude Code CLI (Claude Opus 4 / Sonnet 4) [Large language model]. https://claude.ai/claude-code -->

You are operating the SecurePay V2 data pipeline. Your job is to process raw fraud records from JSONL source files through an 8-stage LLM agent pipeline and ingest them into a Supabase PostgreSQL database.

## Project Location
Working directory: /Users/yajwin/Desktop/CS6747/securepayv2

## Pipeline Overview
The pipeline has 8 stages, each handled by a specialized agent. Records flow as JSON arrays through file-based I/O:

1. **tracker** → Gets next batch of raw records from source files, splits into batch files
2. **extractor** → Cleans raw text, extracts structured fields (loss_amount, iocs, source_url)
3. **validator** → Checks: raw_text present, source_url present, is a scam narrative, UPI payment mechanism
4. **scam_verifier** → Confirms real fraud occurred (not complaints, not awareness posts, not aftermath posts)
5. **dedup_checker** → Checks source_url against DB to reject duplicates
6. **patterns_extractor** → Extracts mechanisms (scammer actions) and red_flags (warning signs) from raw_text
7. **scenario_classifier** → Classifies scam type from a 17-category taxonomy
8. **patterns_verifier** → Prunes/fixes mechanisms, red_flags, scam_type (removes speculation, enforces naming)
9. **ingestor** → Inserts approved records into Supabase via scripts/ingest.py

## How to Run a Batch

### Step 1: Get records from tracker
Use the tracker agent to get 50 records and split into 10 batch files of 5:
- It calls `python3 scripts/get_next_batch.py --size 50`
- Creates batch files at `/tmp/pipeline/run_{timestamp}/batch_01_raw.json` through `batch_10_raw.json`
- State is tracked in `data/import_state.json` — advances automatically

### Steps 2-8: Run each stage
For each stage, launch 10 agents in parallel (one per batch). Each agent takes:
- Input file: previous stage's output (e.g., `batch_01_raw.json` → `batch_01_extracted.json`)
- Output file: this stage's output

File naming convention per batch:
- `batch_XX_raw.json` → extractor → `batch_XX_extracted.json`
- `batch_XX_extracted.json` → validator → `batch_XX_validated.json`
- `batch_XX_validated.json` → scam_verifier → `batch_XX_scamverified.json`
- `batch_XX_scamverified.json` → dedup_checker → `batch_XX_deduped.json`
- `batch_XX_deduped.json` → patterns_extractor → `batch_XX_patterns.json`
- `batch_XX_patterns.json` → scenario_classifier → `batch_XX_classified.json`
- `batch_XX_classified.json` → patterns_verifier → `batch_XX_verified.json`
- `batch_XX_verified.json` → ingestor (no output file, writes to DB)

### Step 9: Ingest
The ingestor pipes the verified JSON to `scripts/ingest.py` which handles all DB inserts.

## Agent Invocation Pattern
Each agent (stages 2-8) is invoked with the Agent tool using:
- `subagent_type`: the agent name (e.g., "extractor", "validator")
- `model`: "haiku" (for all agents)
- `prompt`: "Input file: /path/to/batch_XX_input.json\nOutput file: /path/to/batch_XX_output.json"

For the ingestor:
- `prompt`: "Input file: /path/to/batch_XX_verified.json"

Launch all 10 batch agents in parallel per stage. Wait for all to complete before moving to the next stage.

## Current State
- 500 records already processed (from reddit_upi_fraud, nilansh_reddit_verified, and part of v2_reddit_500_verified)
- ~115 scenarios currently in DB
- Currently partway through v2_reddit_500_verified.jsonl (line_pos=257 of 618)
- 3 more source files pending after that

## What to Be Careful About

1. **Always run stages sequentially** — stage N+1 depends on stage N's output. Only parallelize WITHIN a stage (10 batches).
2. **Check agent outputs** — after each stage, verify all 10 output files exist before proceeding.
3. **Records get filtered at each stage** — a batch of 5 raw records might yield 0-5 approved records by the end. This is expected. Pipeline yield is ~38%.
4. **Dedup is critical** — the dedup_checker queries the live DB. If you run the same records twice, they'll be rejected as duplicates (which is correct).
5. **Don't modify import_state.json manually** — the tracker script manages it.
6. **The ingestor is the ONLY stage that writes to DB** — all other stages are file-to-file.
7. **If an agent fails or returns bad output** — don't retry blindly. Check what went wrong. Common issues: malformed JSON, agent hitting context limits.
8. **Aftermath posts should be rejected** — scam_verifier rejects posts that only discuss aftermath (police, banks, courts) without describing how the scam actually happened.
9. **Non-UPI records should be rejected** — validator rejects fraud involving only debit cards/CVV/net banking/NEFT with zero UPI involvement.
10. **Mechanism names must be 2-4 words snake_case** — patterns_verifier enforces this strictly. Count underscores: 1-3 underscores = valid.

## To start a pipeline run
Say: "Run the pipeline" or "Process next batch"
