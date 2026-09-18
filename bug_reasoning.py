"""
Day 2 - Step 3: Bug Reasoning
Takes a static analysis finding, pulls in the surrounding code, and asks
the LLM to explain the real root cause (and judge if it's a true positive) -
this filters out static analyzer noise instead of just dumping raw warnings.
"""
from static_analysis import Finding
from llm_client import ask_llm


BUG_REASONING_SYSTEM_PROMPT = """You are a careful senior software engineer reviewing
static analysis findings. For each finding, you decide if it's a real, meaningful bug
or a false positive / trivial style nit. Be concise and direct."""


def explain_finding(finding: Finding, surrounding_code: str) -> str:
    """Ask the LLM to explain a static analysis finding in plain terms."""
    prompt = f"""A static analysis tool ({finding.tool}) flagged this issue:

File: {finding.file}
Line: {finding.line}
Rule: {finding.rule_id}
Message: {finding.message}

Here is the surrounding code:
```python
{surrounding_code}
```

Answer in this exact format:
VERDICT: [Real bug / Likely false positive / Minor style issue]
EXPLANATION: <2-3 sentences on the root cause, in plain language>
SUGGESTED_FIX: <one sentence describing the fix approach, or "N/A" if not applicable>
"""
    return ask_llm(prompt, system=BUG_REASONING_SYSTEM_PROMPT)


def get_surrounding_code(file_path: str, target_line: int, context_lines: int = 10) -> str:
    """Read a window of lines around the flagged line, for context."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except OSError as e:
        return f"<could not read file: {e}>"

    start = max(0, target_line - context_lines - 1)
    end = min(len(lines), target_line + context_lines)
    snippet_lines = lines[start:end]
    return "".join(f"{start + i + 1}: {line}" for i, line in enumerate(snippet_lines))


if __name__ == "__main__":
    import os
    from static_analysis import run_all_static_analysis

    # Absolute path to your agent_test_repo (the one with buggy_math.py)
    REPO_PATH = r"C:\Users\Lenovo\Desktop\test\agent_test_repo2"
    findings = run_all_static_analysis(REPO_PATH)

    print(f"Analyzing {len(findings)} findings with LLM reasoning...\n")
    for finding in findings[:3]:  # just the first 3, to keep API usage light
        context = get_surrounding_code(finding.file, finding.line)
        print(f"=== {finding.tool}: {finding.rule_id} at {finding.file}:{finding.line} ===")
        explanation = explain_finding(finding, context)
        print(explanation)
        print()