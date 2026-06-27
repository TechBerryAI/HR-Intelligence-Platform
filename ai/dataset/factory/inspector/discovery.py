"""File discovery and directory tree building."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .config import InspectorConfig
from .models import DirectoryNode, FileRecord, FileTimestamps
from .utils import relative_path, safe_stat_timestamps


def discover_files(config: InspectorConfig) -> tuple[list[Path], list[Path]]:
    """
    Discover files and directories under source_path.

    Returns:
        Tuple of (file_paths, directory_paths).
    """
    source = config.source_path
    if not source.exists():
        raise FileNotFoundError(f"SOURCE_NOT_FOUND: {source}")
    if not source.is_dir():
        raise NotADirectoryError(f"SOURCE_NOT_READABLE: {source}")

    files: list[Path] = []
    directories: list[Path] = []

    if config.recursive:
        iterator = source.rglob("*")
    else:
        iterator = source.glob("*")

    for path in iterator:
        if path.is_symlink() and not config.follow_symlinks:
            continue
        if path.is_dir():
            directories.append(path)
        elif path.is_file():
            files.append(path)

    files.sort(key=lambda p: p.as_posix())
    directories.sort(key=lambda p: p.as_posix())
    return files, directories


def build_directory_tree(
    source_root: Path,
    file_paths: list[Path],
    max_depth: int,
) -> tuple[DirectoryNode, int, int]:
    """
    Build a directory tree summary from discovered files.

    Returns:
        (root_node, max_depth, total_directories)
    """
    rel_files = [relative_path(fp, source_root) for fp in file_paths]

    dir_children: defaultdict[str, set[str]] = defaultdict(set)
    unique_dirs: set[str] = set()

    for rel in rel_files:
        parts = rel.split("/")
        for depth in range(len(parts) - 1):
            dir_path = "." if depth == 0 else "/".join(parts[:depth])
            child = parts[depth]
            dir_children[dir_path].add(child)
            unique_dirs.add("." if depth == 0 else "/".join(parts[: depth + 1]))
        if len(parts) > 1:
            unique_dirs.add("/".join(parts[:-1]))

    computed_max_depth = max((len(rel.split("/")) - 1 for rel in rel_files), default=0)

    def count_files_under(dir_path: str) -> int:
        if dir_path == ".":
            return len(rel_files)
        prefix = f"{dir_path}/"
        return sum(1 for rel in rel_files if rel.startswith(prefix))

    def make_node(dir_path: str, depth: int) -> DirectoryNode | None:
        if depth > max_depth:
            return None

        name = source_root.name if dir_path == "." else dir_path.split("/")[-1]
        children: list[DirectoryNode] = []

        for rel in sorted(rel_files):
            if dir_path == ".":
                if "/" not in rel:
                    if depth + 1 <= max_depth:
                        children.append(
                            DirectoryNode(
                                name=rel,
                                path=rel,
                                type="file",
                                depth=depth + 1,
                            )
                        )
            else:
                prefix = f"{dir_path}/"
                if rel.startswith(prefix):
                    remainder = rel[len(prefix) :]
                    if "/" not in remainder and depth + 1 <= max_depth:
                        children.append(
                            DirectoryNode(
                                name=remainder,
                                path=rel,
                                type="file",
                                depth=depth + 1,
                            )
                        )

        for child_name in sorted(dir_children.get(dir_path, set())):
            child_path = child_name if dir_path == "." else f"{dir_path}/{child_name}"
            child_node = make_node(child_path, depth + 1)
            if child_node is not None:
                children.append(child_node)

        return DirectoryNode(
            name=name,
            path="." if dir_path == "." else dir_path,
            type="directory",
            depth=depth,
            file_count=count_files_under(dir_path),
            children=children,
        )

    root = make_node(".", 0)
    if root is None:
        root = DirectoryNode(
            name=source_root.name,
            path=".",
            type="directory",
            depth=0,
            file_count=len(rel_files),
            children=[],
        )

    return root, computed_max_depth, len(unique_dirs)


def initial_file_record(path: Path, source_root: Path) -> FileRecord:
    """Create a FileRecord with basic stat metadata."""
    created_at, modified_at = safe_stat_timestamps(path)
    rel = relative_path(path, source_root)
    extension = path.suffix.lower().lstrip(".")
    try:
        size_bytes = path.stat().st_size
    except OSError as exc:
        return FileRecord(
            relative_path=rel,
            absolute_path=str(path),
            extension=extension,
            format="unknown",
            size_bytes=0,
            timestamps=FileTimestamps(created_at=created_at, modified_at=modified_at),
            read_error=str(exc),
        )

    return FileRecord(
        relative_path=rel,
        absolute_path=str(path),
        extension=extension,
        format="unknown",
        size_bytes=size_bytes,
        timestamps=FileTimestamps(created_at=created_at, modified_at=modified_at),
        zero_byte=size_bytes == 0,
    )
