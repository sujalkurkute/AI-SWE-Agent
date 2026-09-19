# AI Software Engineering Agent

An autonomous agent that observes a code repository, understands its structure,
finds bugs, proposes fixes, verifies those fixes in an isolated sandbox against
the real test suite, and — only if the fix is proven correct — opens a real
GitHub Pull Request.

Built entirely on a free tech stack: Groq's free-tier LLM API, ChromaDB,
tree-sitter, ruff, mypy, and Docker.

## Status: fully working, end-to-end

This isn't a partial demo — the complete pipeline has been run successfully
against two separate real repositories, each producing a **verified fix and a
real merged/open Pull Request**:

- `sujalkurkute/agent_test_repo` — fixed a return-type mismatch (`str` vs `int`)
- `sujalkurkute/agent_test_repo2` — fixed a return-type mismatch (`int` vs `float`
  from true division), correctly using integer division (`a // b`) rather than
  silently changing the function's public signature

Both runs show the sandbox correctly **rejecting** incorrect fixes (e.g. a fix
that satisfied the type checker but broke the actual test) before accepting the
one that genuinely worked - proof the verification loop does real work, not
just a rubber stamp.

## Architecture

```
repo_observer + code_chunker   →  clones a repo, parses code into functions/
                                   classes via tree-sitter (not naive line splits)
        ↓
search_index (ChromaDB)        →  embeds code chunks, makes the repo searchable
                                   by meaning, not just keyword
static_analysis (ruff + mypy)  →  runs real analyzers, returns structured findings
        ↓
bug_reasoning (LLM)            →  explains each finding in plain language,
                                   filters out false positives / style nits
        ↓
fix_generator (LLM + difflib)  →  LLM proposes the corrected file; a real unified
                                   diff is computed in Python (never trusts the
                                   LLM to get diff line numbers right)
        ↓
sandbox_runner (Docker)        →  applies the diff to a disposable copy of the
                                   repo, runs the REAL test suite inside a
                                   container - proves the fix actually works
        ↓
pr_creator (GitHub API)        →  branches, commits, pushes, and opens a PR -
                                   but only for fixes that passed verification
```

`main_pipeline.py` runs all of this in order, end to end.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**tree-sitter version note:** must be exactly `0.21.3`. Newer versions break
compatibility with `tree-sitter-languages` (you'll see
`TypeError: __init__() takes exactly 1 argument (2 given)` if the version is
wrong).

## Add your keys

```bash
cp .env.example .env
```

Fill in:
- `GROQ_API_KEY` - free, from console.groq.com (no credit card required)
- `GITHUB_TOKEN` - a classic Personal Access Token with `repo` scope, from
  github.com/settings/tokens

**Never commit `.env`** - it's already excluded in `.gitignore`.

## Run each piece individually first

```bash
python repo_observer.py       # clone + list files
python code_chunker.py        # extract functions/classes via tree-sitter
python search_index.py        # build a searchable embedding index (needs internet)
python static_analysis.py     # run ruff + mypy, print findings
python llm_client.py          # sanity check: confirms your Groq key works
python bug_reasoning.py       # LLM explains a real finding
python fix_generator.py       # LLM proposes a fix, converted to a real diff
python sandbox_runner.py      # tests the diff-apply mechanism directly
```

Each file has a small working demo in its `if __name__ == "__main__":` block.

## Run the full pipeline

**Before running against a real repo:** create your own throwaway public
GitHub repo, seed it with a small intentional bug plus a test that exposes it,
and point the pipeline at that first. Never run PR-creation against a repo you
don't own without permission.

1. Open `main_pipeline.py`, edit the config at the bottom: `repo_url`,
   `dest_dir`, `repo_owner`, `repo_name`
2. Keep `create_real_pr=False` on your first run - lets you review the
   proposed diff and test results before anything gets pushed
3. Run: `python main_pipeline.py`
4. If the diff and test results look right, flip `create_real_pr=True` and
   run again to actually open the PR

### What a seeded bug needs to be reliably caught and fixed

The most reliable pattern (proven twice): give a function a type hint that
doesn't match its actual return value, and write one test asserting the
correct type:

```python
def add_numbers(a: int, b: int) -> str:
    return a + b  # mypy will flag this - returns int, not str
```

```python
def test_add_numbers():
    assert isinstance(add_numbers(2, 3), str)  # fails until the bug is fixed
```

This gives `mypy` something concrete to flag, and gives the sandbox a real,
objective way to verify the fix. Avoid module-level code that crashes on
import (e.g. `print(divide(10, 0))` at the top level) - it prevents pytest
from even collecting your tests. Also avoid unused imports of packages not
installed in the Docker sandbox (e.g. `pandas`) unless you actually need
them - an unrelated `ModuleNotFoundError` will block verification of an
otherwise-correct fix.

## Lessons learned building this (real bugs hit and fixed)

These were genuine issues discovered and fixed during development - useful
context if you extend this project or explain it in an interview:

- **tree-sitter / tree-sitter-languages version conflict** - pinned to
  `tree-sitter==0.21.3`
- **LLM model deprecation** - Groq moved `llama-3.3-70b-versatile` to
  Enterprise-only; switched to `openai/gpt-oss-120b`
- **LLM-generated diffs are unreliable** - asking an LLM to write a unified
  diff directly produces invalid `@@` line-number headers; fixed by asking
  for the corrected full file and computing the diff with Python's `difflib`
  instead
- **Missing "No newline at end of file" markers** - the unified diff spec
  requires this marker when a file doesn't end in a newline; `difflib`
  doesn't add it automatically, causing `git apply` to reject valid-looking
  diffs with "corrupt patch"
- **CRLF vs LF line endings on Windows** - diffing a Windows CRLF file
  against LF-only LLM output made every unchanged line look modified;
  normalizing to LF once, upfront, fixed it
- **`git apply` rejects absolute Windows paths** - diff headers must use
  paths relative to the repo root, not `C:\Users\...\file.py`
- **Path duplication in PR creation** - GitPython's `repo.git.*` commands
  already run with `cwd` set to the repo path, so passing an already-joined
  path caused git to look for a doubled/nested path
- **Leftover feature branches block future pulls** - a repo left checked out
  on an agent-created branch (with no upstream tracking) makes `git pull`
  fail; fixed by always resetting to the default branch first
- **"Local changes would be overwritten by merge"** - the agent's own
  working copy can be left dirty from a previous run's in-place file
  normalization; fixed by unconditionally resetting the working copy before
  every pull, since it's disposable and agent-owned
- **Fixing the checker instead of the bug** - the LLM initially "fixed" a
  type mismatch by changing the return type annotation (`str` → `int`)
  instead of the implementation, which silently breaks callers; added an
  explicit instruction biasing the fix generator toward fixing the
  implementation, not the public signature

## Troubleshooting

- **"GROQ_API_KEY not found"** - check `.env` exists in the same folder as
  the scripts (not inside `venv/`), and is named `.env` exactly (not
  `.env.example`)
- **Docker errors** - confirm `docker ps` runs cleanly before running the
  pipeline; Docker Desktop must actually be started, not just installed
- **"no tests ran"** - the target repo has no test files; add at least one
  `test_*.py` so the sandbox has something to verify fixes against
- **PR creation fails with 403** - your GitHub token likely lacks `repo`
  scope, or has expired - generate a new one

## Disclaimer

Every PR this agent opens includes an explicit note disclosing that it was
AI-generated and should be reviewed before merging. This project is a
learning/portfolio tool - always review AI-generated changes before merging
them into anything that matters.
