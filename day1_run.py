"""
Day 1 - Final Step: Run the full pipeline and save results.
This ties repo_observer.py + code_chunker.py together and saves a
JSON file you can open and inspect, proving Day 1 works end-to-end.
"""
import json
from dataclasses import asdict

from repo_observer import clone_repo, build_manifest
from code_chunker import chunk_repo


def run_day1(repo_url: str, dest_dir: str, output_json: str = "day1_output.json"):
    print(f"=== Day 1 Pipeline: {repo_url} ===\n")

    # Step 1: clone + list files
    repo_path = clone_repo(repo_url, dest_dir)
    manifest = build_manifest(repo_path)
    print(f"[1/2] Found {len(manifest)} Python files.")

    # Step 2: chunk into functions/classes
    chunks = chunk_repo(repo_path)
    print(f"[2/2] Extracted {len(chunks)} function/class chunks.")

    # Save everything to JSON so you can open it and inspect the results
    output = {
        "repo_url": repo_url,
        "file_count": len(manifest),
        "chunk_count": len(chunks),
        "files": manifest,
        "chunks": [asdict(c) for c in chunks],
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Day 1 complete. Full results saved to {output_json}")
    print(f"   Open that file and check: are the chunks real, complete functions?")


if __name__ == "__main__":
    run_day1(
        repo_url="https://github.com/pallets/itsdangerous.git",
        dest_dir="workspace/repos/itsdangerous",
    )