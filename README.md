# AI Software Engineering Agent - Full Pipeline

Observes a repo, finds bugs, proposes a verified fix, and opens a PR - all automated.

## What's tested vs. what to verify yourself

Everything here was written and tested as far as possible in a sandboxed dev
environment. Here's exactly what was confirmed working, and what needs your
machine to fully verify (because of API keys / Docker / network access I
didn't have):

| Module | Status |
|---|---|
| `repo_observer.py`, `code_chunker.py` | ✅ Fully tested end-to-end (Day 1) |
| `static_analysis.py` | ✅ Fully tested - confirmed it catches real bugs |
| `search_index.py` | ✅ ChromaDB logic tested; embedding model download blocked in dev sandbox (huggingface.co not reachable there) - will work on your machine |
| `llm_client.py`, `bug_reasoning.py`, `fix_generator.py` | ✅ Code compiles cleanly; needs your `GROQ_API_KEY` to actually run |
| `sandbox_runner.py` | ✅ Diff-apply logic fully tested and confirmed correct; Docker test-running needs Docker (you have it) |
| `pr_creator.py` | ✅ Code compiles cleanly; needs your `GITHUB_TOKEN` and a repo you own to test |

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**tree-sitter version note:** must be exactly `0.21.3`. Newer versions break
compatibility with `tree-sitter-languages` (you'll see `TypeError: __init__()
takes exactly 1 argument (2 given)` if the version is wrong).

## Add your keys

```bash
cp .env.example .env
```

Open `.env` and fill in:
- `GROQ_API_KEY` - from console.groq.com (free, no credit card)
- `GITHUB_TOKEN` - a classic PAT with `repo` scope, from github.com/settings/tokens

**Never commit `.env` to git** - it's already in `.gitignore`.

## Run each piece individually (recommended first)

```bash
python repo_observer.py       # Day 1: clone + list files
python code_chunker.py        # Day 1: extract functions/classes
python search_index.py        # Day 2: build searchable index (needs internet for model download)
python static_analysis.py     # Day 2: run ruff + mypy
python llm_client.py          # quick test that Groq API key works
python bug_reasoning.py       # Day 2: LLM explains a bug
python fix_generator.py       # Day 3: LLM proposes a diff
python sandbox_runner.py      # Day 3: tests the diff-apply logic
```

Each script has a small demo in its `if __name__ == "__main__":` block, so
you can run any file directly to see it work in isolation before trusting
the full pipeline.

## Run the full pipeline

**Before running against a real repo:** create your own throwaway public
GitHub repo, seed it with a small intentional bug, and point the pipeline at
that first. Never run PR-creation against a repo you don't own without
permission.

1. Open `main_pipeline.py`
2. Edit the values at the bottom: `repo_url`, `dest_dir`, `repo_owner`, `repo_name`
3. Keep `create_real_pr=False` for your first run - this lets you review the
   proposed diff and test results without actually opening a PR
4. Run:
   ```bash
   python main_pipeline.py
   ```
5. Review the output. If the diff and test results look right, change
   `create_real_pr=True` and run again to actually open the PR

## How the pieces connect

```
repo_observer + code_chunker  →  raw code broken into functions/classes
        ↓
search_index (Chroma)         →  makes code searchable by meaning
static_analysis (ruff/mypy)   →  finds candidate issues
        ↓
bug_reasoning (LLM)           →  explains root cause, filters false positives
        ↓
fix_generator (LLM)           →  proposes a fix as a diff
        ↓
sandbox_runner (Docker)       →  proves the fix actually works
        ↓
pr_creator (GitHub API)       →  opens the PR, only if verified
```

`main_pipeline.py` runs all of this in order.

## Troubleshooting

- **"GROQ_API_KEY not found"** - check your `.env` file exists and is in the
  same folder as the scripts (not inside `venv/`)
- **Docker errors** - confirm `docker ps` works in your terminal before
  running the pipeline
- **`git apply` fails** - this usually means the LLM's diff didn't exactly
  match the file's current content; this is a known limitation of LLM-
  generated diffs and the retry loop is the intended fix (see the guide's
  Phase 3 notes on retrying with test failure feedback)
- **PR creation fails with 403** - your GitHub token likely doesn't have
  `repo` scope, or it's expired - generate a new one