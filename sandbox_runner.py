"""
Day 3 - Step 2: Sandboxed Verification
Applies a proposed diff to a DISPOSABLE COPY of the repo inside a Docker
container, then runs the test suite. If tests fail, we can feed the error
back to the LLM and retry. This proves a fix actually works before a human
ever sees it.
"""
import os
import shutil
import subprocess
import tempfile


def make_disposable_copy(repo_path: str) -> str:
    """Copy the repo to a temp directory so we never touch the original."""
    temp_dir = tempfile.mkdtemp(prefix="agent_sandbox_")
    dest = os.path.join(temp_dir, "repo")
    shutil.copytree(repo_path, dest)
    return dest


def apply_diff(repo_copy_path: str, diff_text: str) -> tuple[bool, str]:
    """Apply a unified diff to the disposable copy using `git apply`.
    Returns (success, output/error message)."""
    diff_file = os.path.join(repo_copy_path, "_agent_fix.diff")
    # newline='' prevents Python's default text-mode write from translating
    # \n to \r\n on Windows - important because diff_text may already
    # contain real \r\n sequences (preserved from a CRLF source file), and
    # double-translating them would corrupt the patch again.
    with open(diff_file, "w", newline="") as f:
        f.write(diff_text)

    result = subprocess.run(
        ["git", "apply", "--verbose", "_agent_fix.diff"],
        cwd=repo_copy_path, capture_output=True, text=True,
    )
    os.remove(diff_file)

    if result.returncode != 0:
        return False, result.stderr
    return True, result.stdout


def run_tests_in_docker(repo_copy_path: str, python_image: str = "python:3.11-slim") -> tuple[bool, str]:
    """Run the test suite inside a fresh Docker container.
    The container has no access to anything outside repo_copy_path, so a
    broken fix can never damage your real system."""
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{os.path.abspath(repo_copy_path)}:/workspace",
        "-w", "/workspace",
        python_image,
        "sh", "-c", "pip install -e . --quiet 2>/dev/null; pip install pytest --quiet; pytest -x -q",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        passed = result.returncode == 0
        output = result.stdout + result.stderr
        return passed, output
    except subprocess.TimeoutExpired:
        return False, "Test run timed out after 180 seconds."
    except FileNotFoundError:
        return False, "Docker not found - is Docker installed and running?"


def run_tests_locally(repo_copy_path: str) -> tuple[bool, str]:
    """Fallback: run tests directly (no Docker) - less safe, but useful for
    quick local testing when Docker isn't available."""
    result = subprocess.run(
        ["python3", "-m", "pytest", "-x", "-q"],
        cwd=repo_copy_path, capture_output=True, text=True, timeout=120,
    )
    return result.returncode == 0, result.stdout + result.stderr


def verify_fix(repo_path: str, diff_text: str, use_docker: bool = True) -> dict:
    """Full verification pipeline: copy repo -> apply diff -> run tests."""
    copy_path = make_disposable_copy(repo_path)
    try:
        applied, apply_msg = apply_diff(copy_path, diff_text)
        if not applied:
            return {"success": False, "stage": "apply_diff", "message": apply_msg}

        if use_docker:
            passed, test_output = run_tests_in_docker(copy_path)
        else:
            passed, test_output = run_tests_locally(copy_path)

        return {
            "success": passed,
            "stage": "run_tests",
            "message": test_output,
        }
    finally:
        shutil.rmtree(copy_path, ignore_errors=True)


if __name__ == "__main__":
    # Test the apply_diff logic directly (no Docker needed for this part)
    import tempfile

    test_dir = tempfile.mkdtemp()
    test_file = os.path.join(test_dir, "sample.py")
    with open(test_file, "w") as f:
        f.write("def add(a, b):\n    return a - b\n")  # deliberately wrong

    subprocess.run(["git", "init", "-q"], cwd=test_dir)
    subprocess.run(["git", "add", "."], cwd=test_dir)
    subprocess.run(["git", "-c", "user.email=a@a.com", "-c", "user.name=a",
                     "commit", "-q", "-m", "init"], cwd=test_dir)

    test_diff = """--- a/sample.py
+++ b/sample.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""
    success, msg = apply_diff(test_dir, test_diff)
    print(f"Diff applied: {success}")
    print(f"Message: {msg}")

    with open(test_file) as f:
        print(f"\nFile content after fix:\n{f.read()}")

    shutil.rmtree(test_dir, ignore_errors=True)