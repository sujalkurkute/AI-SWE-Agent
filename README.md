# Day 1 - Repo Observer + Code Chunking

## Setup
```bash
python -m venv venv
source venv/bin/activate       # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Note: tree-sitter is pinned to 0.21.3 because newer versions (0.22+) broke
compatibility with tree-sitter-languages. If you see an error like
`TypeError: __init__() takes exactly 1 argument (2 given)`, this pin is why
you need it. You'll see one harmless FutureWarning about `Language(path, name)`
being deprecated — that's fine, ignore it.

## Run
```bash
python day1_run.py
```

This will:
1. Clone the repo set in `day1_run.py` (defaults to a small test repo)
2. List all its Python files
3. Break every function/class into a "chunk" using tree-sitter
4. Save everything to `day1_output.json` so you can inspect it

## Try it on your own repo
Edit the `repo_url` and `dest_dir` at the bottom of `day1_run.py` to point at
any public GitHub repo you want.

## What "done" looks like
Open `day1_output.json` and check a few chunks under `"chunks"` — each one
should be a complete, real function or class body with the correct
`start_line`/`end_line`, not a random slice of text.