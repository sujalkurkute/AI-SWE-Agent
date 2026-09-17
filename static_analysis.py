"""
Day 2 - Step 2: Static Analysis
Runs ruff and mypy on a repo, parses their JSON output into one unified
list of findings: [{file, line, message, severity, tool}]
"""
import json
import subprocess
from dataclasses import dataclass


@dataclass
class Finding:
    file: str
    line: int
    message: str
    tool: str
    rule_id: str = ""
    severity: str = "warning"


def run_ruff(repo_path: str) -> list[Finding]:
    """Run ruff (style + simple bug checks) and parse its JSON output."""
    try:
        result = subprocess.run(
            ["ruff", "check", repo_path, "--output-format=json"],
            capture_output=True, text=True, timeout=120,
        )
        # ruff exits non-zero when it finds issues - that's expected, not an error
        raw = json.loads(result.stdout) if result.stdout.strip() else []
    except FileNotFoundError:
        print("[static_analysis] ruff not installed - run: pip install ruff")
        return []
    except json.JSONDecodeError:
        print(f"[static_analysis] ruff output not valid JSON: {result.stdout[:200]}")
        return []

    findings = []
    for item in raw:
        findings.append(Finding(
            file=item.get("filename", ""),
            line=item.get("location", {}).get("row", 0),
            message=item.get("message", ""),
            tool="ruff",
            rule_id=item.get("code", ""),
            severity="warning",
        ))
    return findings


def run_mypy(repo_path: str) -> list[Finding]:
    """Run mypy (type checking) and parse its output.
    mypy's JSON output is one JSON object per line, not a single JSON array."""
    try:
        result = subprocess.run(
            ["mypy", repo_path, "--output=json", "--ignore-missing-imports"],
            capture_output=True, text=True, timeout=120,
        )
    except FileNotFoundError:
        print("[static_analysis] mypy not installed - run: pip install mypy")
        return []

    findings = []
    for line in result.stdout.strip().splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue  # mypy sometimes prints summary lines that aren't JSON
        findings.append(Finding(
            file=item.get("file", ""),
            line=item.get("line", 0),
            message=item.get("message", ""),
            tool="mypy",
            rule_id=item.get("code", "") or "",
            severity=item.get("severity", "warning"),
        ))
    return findings


def run_all_static_analysis(repo_path: str) -> list[Finding]:
    """Run every analyzer and merge results into one list, sorted by file+line."""
    findings = []
    findings.extend(run_ruff(repo_path))
    findings.extend(run_mypy(repo_path))
    findings.sort(key=lambda f: (f.file, f.line))
    return findings


if __name__ == "__main__":
    REPO_PATH = "workspace/repos/itsdangerous"

    findings = run_all_static_analysis(REPO_PATH)
    print(f"\n[static_analysis] Found {len(findings)} total findings.\n")

    for f in findings[:15]:
        print(f"  [{f.tool}] {f.file}:{f.line}  {f.rule_id}  {f.message}")

    if len(findings) > 15:
        print(f"  ... and {len(findings) - 15} more")