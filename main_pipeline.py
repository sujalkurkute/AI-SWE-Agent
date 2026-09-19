"""
Main Pipeline: The full agent, start to finish.

Given a repo, this will:
1. Clone it + chunk the code (Day 1)
2. Build a searchable index + run static analysis (Day 2)
3. Reason about a bug + propose a fix + verify it in Docker (Day 3)
4. Open a real PR with the verified fix (Day 4)

IMPORTANT: only run this against a repo you own / have permission to modify.
Never run the PR-creation step against someone else's repo without asking.
"""
from repo_observer import clone_repo, build_manifest
from code_chunker import chunk_repo
from static_analysis import run_all_static_analysis
import os
from bug_reasoning import explain_finding, get_surrounding_code
from fix_generator import propose_fix, is_valid_diff
from sandbox_runner import verify_fix
from pr_creator import full_pr_pipeline


def run_full_pipeline(
    repo_url: str,
    dest_dir: str,
    repo_owner: str,
    repo_name: str,
    max_findings_to_fix: int = 1,
    use_docker: bool = True,
    create_real_pr: bool = False,
):
    print("=" * 60)
    print("STEP 1: Cloning repo and chunking code")
    print("=" * 60)
    repo_path = clone_repo(repo_url, dest_dir)
    manifest = build_manifest(repo_path)
    chunks = chunk_repo(repo_path)
    print(f"Found {len(manifest)} files, {len(chunks)} code chunks.\n")

    print("=" * 60)
    print("STEP 2: Running static analysis")
    print("=" * 60)
    findings = run_all_static_analysis(repo_path)
    print(f"Found {len(findings)} static analysis findings.\n")

    if not findings:
        print("No findings to fix. Try a repo with known issues, or plant one on purpose.")
        return

    fixed_count = 0
    for finding in findings[:max_findings_to_fix]:
        print("=" * 60)
        print(f"STEP 3: Reasoning about {finding.tool} finding at "
              f"{finding.file}:{finding.line}")
        print("=" * 60)

        context = get_surrounding_code(finding.file, finding.line)
        explanation = explain_finding(finding, context)
        print(explanation)

        if "false positive" in explanation.lower():
            print("Skipping - LLM judged this a false positive.\n")
            continue

        print("\nSTEP 4: Proposing a fix...")
        # CRLF vs LF fix (v2): trying to *preserve* the original line ending
        # style (previous approach) doesn't work because the LLM always
        # returns LF-only content - so diffing a CRLF original against an
        # LF "fixed" version makes every unchanged line look modified (since
        # "line\r\n" != "line\n" as strings), which corrupts the diff.
        # Simpler and more robust: normalize the real file on disk to LF
        # once, upfront, so the original, the LLM output, and the eventual
        # sandbox copy are all consistently LF from this point on.
        with open(finding.file, "r", encoding="utf-8", errors="ignore", newline="") as f:
            raw_content = f.read()
        full_content = raw_content.replace("\r\n", "\n").replace("\r", "\n")
        if full_content != raw_content:
            with open(finding.file, "w", encoding="utf-8", newline="\n") as f:
                f.write(full_content)

        # git apply rejects absolute paths (especially Windows paths with a
        # drive letter like C:\...) in diff headers - it expects paths
        # relative to the repo root. We still READ the file using its real
        # absolute path above, but the diff itself references the relative
        # path, matching the same relative structure inside the sandbox copy.
        relative_path = os.path.relpath(finding.file, repo_path)
        diff = propose_fix(relative_path, full_content, explanation)

        if not is_valid_diff(diff):
            print("Generated diff didn't look valid. Skipping this finding.\n")
            continue

        print(f"Proposed diff:\n{diff}\n")

        print("STEP 5: Verifying fix in sandbox...")
        result = verify_fix(repo_path, diff, use_docker=use_docker)
        print(f"Verification result: {'PASSED' if result['success'] else 'FAILED'}")
        print(result["message"][:1000])

        if not result["success"]:
            print("Fix did not pass verification. Skipping PR for this finding.\n")
            continue

        fixed_count += 1

        if create_real_pr:
            print("\nSTEP 6: Creating pull request...")
            pr_url = full_pr_pipeline(
                repo_path=repo_path,
                repo_owner=repo_owner,
                repo_name=repo_name,
                diff_text=diff,
                bug_explanation=explanation,
                test_output=result["message"],
            )
            print(f"PR created: {pr_url}")
        else:
            print("\nSTEP 6 skipped (create_real_pr=False) - diff verified but not submitted.")

    print("\n" + "=" * 60)
    print(f"Pipeline complete. {fixed_count} fix(es) verified.")
    print("=" * 60)


if __name__ == "__main__":
    run_full_pipeline(
        repo_url="https://github.com/sujalkurkute/agent_test_repo2.git",
        dest_dir="workspace/repos/agent_test_repo2",
        repo_owner="sujalkurkute",
        repo_name="agent_test_repo2",
        max_findings_to_fix=4,  # tries all 4 findings so the real bug (mypy return-value) isn't cut off
        use_docker=True,
        create_real_pr=True,  # flip to True only once you've reviewed the diff/tests
    )