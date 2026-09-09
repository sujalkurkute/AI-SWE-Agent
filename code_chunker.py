"""
Day 1 - Step 2: Code Chunking with tree-sitter
Parses each Python file into an AST and pulls out each function/class as a
separate "chunk" (with its code, name, and line numbers) instead of naively
splitting by line count.
"""
from dataclasses import dataclass
from tree_sitter_languages import get_parser

from repo_observer import clone_repo, build_manifest


@dataclass
class CodeChunk:
    file_path: str
    symbol_name: str
    symbol_type: str  # "function" or "class"
    start_line: int
    end_line: int
    code: str

    def preview(self, max_lines: int = 3) -> str:
        lines = self.code.splitlines()
        shown = "\n".join(lines[:max_lines])
        if len(lines) > max_lines:
            shown += "\n    ..."
        return shown


# Python's tree-sitter node types for the things we care about
FUNCTION_NODE_TYPES = {"function_definition"}
CLASS_NODE_TYPES = {"class_definition"}


def _get_symbol_name(node, source_bytes: bytes) -> str:
    """Pull the identifier (name) out of a function/class definition node."""
    for child in node.children:
        if child.type == "identifier":
            return source_bytes[child.start_byte:child.end_byte].decode("utf-8")
    return "<unknown>"


def chunk_file(file_path: str) -> list[CodeChunk]:
    """Parse one Python file and return a CodeChunk for every top-level and
    nested function/class definition found."""
    parser = get_parser("python")

    with open(file_path, "rb") as f:
        source_bytes = f.read()

    tree = parser.parse(source_bytes)
    chunks: list[CodeChunk] = []

    def walk(node):
        if node.type in FUNCTION_NODE_TYPES or node.type in CLASS_NODE_TYPES:
            symbol_type = "function" if node.type in FUNCTION_NODE_TYPES else "class"
            name = _get_symbol_name(node, source_bytes)
            code = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
            chunks.append(CodeChunk(
                file_path=file_path,
                symbol_name=name,
                symbol_type=symbol_type,
                start_line=node.start_point[0] + 1,   # tree-sitter is 0-indexed
                end_line=node.end_point[0] + 1,
                code=code,
            ))
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return chunks


def chunk_repo(repo_path: str) -> list[CodeChunk]:
    """Chunk every Python file in the repo's manifest."""
    manifest = build_manifest(repo_path)
    all_chunks: list[CodeChunk] = []
    for entry in manifest:
        try:
            all_chunks.extend(chunk_file(entry["path"]))
        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"[code_chunker] Skipping {entry['path']}: {e}")
    return all_chunks


if __name__ == "__main__":
    REPO_URL = "https://github.com/pallets/itsdangerous.git"
    DEST_DIR = "workspace/repos/itsdangerous"

    repo_path = clone_repo(REPO_URL, DEST_DIR)
    chunks = chunk_repo(repo_path)

    print(f"\n[code_chunker] Extracted {len(chunks)} function/class chunks.\n")
    for chunk in chunks[:5]:
        print(f"--- {chunk.symbol_type}: {chunk.symbol_name} "
              f"({chunk.file_path}:{chunk.start_line}-{chunk.end_line}) ---")
        print(chunk.preview())
        print()