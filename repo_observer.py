"""
Day 1 - Step 1: Repo Observer
Clones a target repo and lists all Python files (respecting .gitignore).
"""
import os
from pathlib import Path
from git import Repo
import pathspec


def clone_repo(repo_url: str, dest_dir: str) -> str:
    """Clone repo_url into dest_dir. If it already exists, just pull latest."""
    dest = Path(dest_dir)
    if dest.exists() and any(dest.iterdir()):
        print(f"[repo_observer] Repo already exists at {dest}, pulling latest...")
        repo = Repo(dest)

        # A previous agent run may have created and left the repo checked
        # out on a feature branch (e.g. agent-fix-20260101120000) to open a
        # PR. That branch has no "upstream" tracking configured (it was
        # pushed without -u), so a plain `git pull` fails with "no tracking
        # information for the current branch". Always return to the repo's
        # actual default branch first, so pulling is well-defined.
        default_branch = _get_default_branch(repo)
        if repo.active_branch.name != default_branch:
            print(f"[repo_observer] Switching from '{repo.active_branch.name}' "
                  f"back to '{default_branch}' before pulling...")
            repo.git.checkout(default_branch)

        repo.remotes.origin.pull()
    else:
        print(f"[repo_observer] Cloning {repo_url} into {dest}...")
        Repo.clone_from(repo_url, dest)
    return str(dest)


def _get_default_branch(repo: Repo) -> str:
    """Figure out the repo's actual default branch (main, master, or
    whatever it's called) instead of assuming 'main'."""
    try:
        # origin/HEAD points at the remote's actual default branch
        result = repo.git.symbolic_ref("refs/remotes/origin/HEAD")
        return result.rsplit("/", 1)[-1]
    except Exception:
        # Fallback: whichever of these actually exists locally
        for candidate in ("main", "master"):
            if candidate in [h.name for h in repo.heads]:
                return candidate
        return repo.heads[0].name  # last resort: whatever the first branch is


def load_gitignore(repo_path: str) -> pathspec.PathSpec:
    """Load .gitignore rules so we skip files the repo itself ignores."""
    gitignore_file = Path(repo_path) / ".gitignore"
    patterns = []
    if gitignore_file.exists():
        patterns = gitignore_file.read_text().splitlines()
    # Always skip the .git folder itself
    patterns.append(".git/")
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def list_python_files(repo_path: str) -> list[str]:
    """Walk the repo and return all .py files not excluded by .gitignore."""
    spec = load_gitignore(repo_path)
    repo_path_obj = Path(repo_path)
    py_files = []

    for root, dirs, files in os.walk(repo_path):
        rel_root = os.path.relpath(root, repo_path)
        for f in files:
            if not f.endswith(".py"):
                continue
            rel_path = os.path.normpath(os.path.join(rel_root, f))
            if spec.match_file(rel_path):
                continue
            py_files.append(str(repo_path_obj / rel_path))

    return py_files


def build_manifest(repo_path: str) -> list[dict]:
    """Build a simple manifest: file path + size + line count for each .py file."""
    manifest = []
    for file_path in list_python_files(repo_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            manifest.append({
                "path": file_path,
                "size_bytes": os.path.getsize(file_path),
                "line_count": len(lines),
            })
        except (OSError, UnicodeDecodeError) as e:
            print(f"[repo_observer] Skipping {file_path}: {e}")
    return manifest


if __name__ == "__main__":
    # --- CONFIG: change these two lines to point at any repo you like ---
    REPO_URL = "https://github.com/pallets/itsdangerous.git"
    DEST_DIR = "workspace/repos/itsdangerous"
    # ----------------------------------------------------------------

    repo_path = clone_repo(REPO_URL, DEST_DIR)
    manifest = build_manifest(repo_path)

    print(f"\n[repo_observer] Found {len(manifest)} Python files.\n")
    for entry in manifest[:10]:
        print(f"  {entry['path']}  ({entry['line_count']} lines)")
    if len(manifest) > 10:
        print(f"  ... and {len(manifest) - 10} more")