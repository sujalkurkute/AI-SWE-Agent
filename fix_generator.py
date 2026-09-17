"""
Day 3 - Step 1: Fix Proposal (v2 - more reliable)

IMPORTANT DESIGN CHANGE: asking an LLM to write a unified diff directly
(with exact line numbers in @@ headers) is unreliable - LLMs frequently
get the line-count math wrong, producing diffs that `git apply` rejects
with "No valid patches in input".

The fix: ask the LLM for the corrected FULL FILE content instead (much
easier for it to get right), then use Python's difflib to compute the
diff ourselves. This guarantees a syntactically valid diff every time,
since we're doing the line-counting with code, not asking the LLM to.
"""
import re
import difflib
from llm_client import ask_llm


FIX_SYSTEM_PROMPT = """You are a precise software engineer. You output ONLY
the complete, corrected version of the file. Do not include any explanation,
markdown formatting, or text outside the code itself. Output the ENTIRE file
content, not just the changed lines.

IMPORTANT FIX PHILOSOPHY: when a type checker or static analysis tool flags
a mismatch between a function's declared signature (parameter types, return
type) and its actual behavior, prefer fixing the IMPLEMENTATION to match the
declared signature, not the other way around. A function's signature is
usually part of its public contract - other code may depend on it. Changing
a return type annotation from `str` to `int` "fixes" the type checker but
silently breaks every caller that expected a string. Only change a
signature if the bug explanation explicitly states the signature itself
(not just the implementation) is wrong."""


def propose_fix(file_path: str, full_file_content: str, bug_explanation: str) -> str:
    """Ask the LLM for the corrected file content, then compute a proper
    unified diff ourselves (never trust an LLM's raw diff line numbers)."""
    prompt = f"""File: {file_path}

Current file content:
```
{full_file_content}
```

Bug to fix:
{bug_explanation}

Output the complete corrected file content. Output nothing else - no
explanation, no markdown code fences, just the raw file content."""

    response = ask_llm(prompt, system=FIX_SYSTEM_PROMPT)
    fixed_content = extract_code(response)

    # CRITICAL: the diff must match the REAL file on disk byte-for-byte in
    # its unchanged parts, or git apply rejects it. That means we must NEVER
    # alter full_file_content (the original) - it has to stay exactly as it
    # was read from disk, trailing newline or not. What we DO need to fix is
    # fixed_content (the LLM's output), which may have a different trailing-
    # newline convention than the original purely by LLM habit, not because
    # the LLM intended to change the file's ending. So: strip whatever
    # trailing newline fixed_content has, then match the original's actual
    # ending state exactly (present or absent).
    fixed_content = fixed_content.rstrip("\n")
    if full_file_content.endswith("\n"):
        fixed_content += "\n"
    # else: original had no trailing newline, so fixed_content stays without one too

    diff_lines = list(difflib.unified_diff(
        full_file_content.splitlines(keepends=True),
        fixed_content.splitlines(keepends=True),
        fromfile=file_path,
        tofile=file_path,
    ))
    return _add_no_newline_markers(diff_lines)


def _add_no_newline_markers(diff_lines: list[str]) -> str:
    """The unified diff spec requires a literal '\\ No newline at end of file'
    line immediately after any content line that doesn't end in a newline.
    difflib doesn't add this automatically, and without it git apply fails
    with 'corrupt patch' whenever the original or fixed file has no trailing
    newline (a very common case for small/simple files)."""
    result = []
    for line in diff_lines:
        if line.startswith(("---", "+++")):
            result.append(line if line.endswith("\n") else line + "\n")
            continue
        if not line.endswith("\n"):
            result.append(line + "\n")
            result.append("\\ No newline at end of file\n")
        else:
            result.append(line)
    return "".join(result)


def extract_code(text: str) -> str:
    """Strip markdown code fences if the LLM added them despite instructions."""
    match = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1)
    return text


def is_valid_diff(diff_text: str) -> bool:
    """Basic sanity check: does this look like a real unified diff.
    An EMPTY diff (no changes) is also technically 'valid' but means the
    LLM didn't actually change anything - the caller should check for that
    separately if needed."""
    lines = diff_text.strip().splitlines()
    if not lines:
        return False
    has_header = any(line.startswith("---") for line in lines)
    has_hunk = any(line.startswith("@@") for line in lines)
    return has_header and has_hunk


if __name__ == "__main__":
    # Test with your actual seeded bug file
    file_path = r"C:\Users\Lenovo\Desktop\test\agent_test_repo\buggy_math.py"
    with open(file_path) as f:
        content = f.read()

    bug_explanation = (
        "The function add_numbers() declares it returns a str but actually "
        "returns an int (a + b). Fix the type mismatch so it returns a str."
    )

    diff = propose_fix(file_path, content, bug_explanation)
    print("=== Proposed diff (computed with difflib - guaranteed valid format) ===")
    print(diff)
    print(f"\nLooks like a valid diff: {is_valid_diff(diff)}")