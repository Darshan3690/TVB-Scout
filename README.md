# TVB Scout

Autonomous Company Discovery & Verification Agent.

TVB Scout discovers prospective companies through public web search and GitHub, researches each candidate, and applies deterministic Python rules to decide whether it meets a strict target profile. It is designed to surface evidence, not to manufacture a list of companies.

## Problem

Finding early-stage technology platforms with a narrow funding range, limited United States presence, a known founder, and a publicly verifiable founder email is a research-heavy workflow. A company can look promising in a directory or GitHub but still fail the actual criteria.

## Solution

The app uses a single orchestrator to gather dynamic candidates, deduplicate them, collect public evidence, and classify every researched company as qualified or rejected. It never uses a stored company list, guesses an email address, or treats GitHub popularity as funding evidence.

## Target criteria

A qualified lead must have public evidence for all of the following:

1. Funding or revenue from $1M to $5M USD, inclusive.
2. A genuine technology-related platform.
3. Minimal or no United States presence, verified affirmatively.
4. An identified CEO, founder, or co-founder.
5. A public, non-generic professional email tied to that founder and the company domain.

Missing or weak evidence results in rejection. The app may return fewer than the target number of leads rather than fabricate a result.

## Architecture

```text
Streamlit UI
  -> Orchestrator
      -> Web discovery + GitHub discovery
      -> Domain/name de-duplication
      -> Evidence-first research
      -> Deterministic qualification
      -> Qualified/rejected results + CSV exports
```

## Discovery and validation strategy

- Web queries are generated from technology, geography, and funding term combinations at runtime.
- GitHub repository search supplies only candidate signals; stars never count as funding proof.
- Research requests targeted public evidence for funding, platform capabilities, US presence, founder identity, and founder email.
- When `LLM_API_KEY` and `OPENAI_MODEL` are configured, an optional structured extraction adapter reads only the evidence already collected by the app. Its output is treated as a hint and cannot bypass direct evidence checks or deterministic qualification.
- Final qualification is code in `agent/filter.py`, not an LLM decision.
- The rejected tab retains every rejected candidate with its first deterministic failure reason.

## Tech stack

- Python 3.11+
- Streamlit
- Requests public-search and GitHub API adapters
- Pandas CSV export
- Pytest for deterministic logic

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Environment variables

Copy `.env.example` to `.env` and only add keys you own.

- `SERPER_API_KEY` (recommended): Google search engine in clean JSON format via Serper.dev (2,500 free queries).
- `TAVILY_API_KEY` (optional): Tavily Search API (1,000 free queries).
- `GITHUB_TOKEN` (optional): higher GitHub API rate limit.
- `LLM_API_KEY` (optional: enables structured LLM evidence extraction with `OPENAI_MODEL`).
- `OPENAI_MODEL` (required together with `LLM_API_KEY` to enable structured evidence extraction).

No API key is required to launch the app. When keys are present, search runs against high-throughput JSON APIs with automatic retry and rate-limiting backoff.

## Testing

```bash
pytest
```

The test suite covers funding bounds, final qualification, domain/name de-duplication, and founder-email validation.

## Deployment

The repository includes a `Dockerfile` and `render.yaml` for a Render web-service deployment. Configure optional keys in the host's secret manager, never in Git:

1. Create a new Render Blueprint from this repository.
2. Add `SERPAPI_KEY`, `GITHUB_TOKEN`, and any LLM credentials only when available.
3. Deploy and open the generated service URL.

The app remains usable without optional keys, subject to public search and GitHub rate limits.

## Limitations

Public founder emails and affirmative proof of minimal US presence are intentionally difficult to establish. The default policy is strict: a lack of evidence is a rejection, not a positive claim. Search-engine availability and rate limits can also reduce discovery results.

## Future improvements

- Add a configured, structured LLM extraction adapter with source-level citations.
- Add source quality ranking and a human review queue.
- Add deployment configuration for Streamlit Community Cloud, Render, or Railway.
- Add persistent run history and cached source snapshots.

> The system uses AI-compatible discovery and research adapters while deterministic Python rules perform final qualification. When information cannot be verified, the system leaves it blank or rejects the candidate rather than generating unsupported information.
