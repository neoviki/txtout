"""
Tests for txtout.txtin

Run with:
    pip install -e .
    pip install pytest
    pytest tests/ -v
"""

from pathlib import Path

import pytest

from txtout.txtout import RepoConfig, generate_export
from txtout.txtin import (
    extract_file_sections,
    import_project,
    is_placeholder,
    is_safe_relative_path,
)


def make_file(path: Path, content: str = "content") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def export_project(root: Path, output: Path, **overrides) -> Path:
    config = RepoConfig()
    config.root = root
    config.output = output
    for key, value in overrides.items():
        setattr(config, key, value)
    generate_export(config)
    return output


def read_tree(root: Path):
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in root.rglob("*")
        if p.is_file()
    }


# ==================================================
# Round-trip fidelity
# ==================================================

def test_roundtrip_preserves_structure_and_content(tmp_path):
    root = tmp_path / "original"
    make_file(root / "main.py", "def main():\n    pass\n")
    make_file(root / "src" / "utils" / "helper.rs", "fn helper() -> i32 { 42 }")
    make_file(root / "docs" / "notes.tex", "\\documentclass{article}\n")
    make_file(root / "README.html", "<html><body>Test</body></html>")

    export_path = tmp_path / "project.export"
    export_project(root, export_path)

    restored = tmp_path / "restored"
    import_project(str(export_path), str(restored), overwrite=False, dry_run=False)

    assert read_tree(root) == read_tree(restored)


def test_roundtrip_preserves_trailing_newline_on_every_file(tmp_path):
    # Regression test: an earlier version of the marker regex was
    # greedy and swallowed a file's own trailing newline whenever it
    # wasn't the last file in the export.
    root = tmp_path / "original"
    make_file(root / "a_first.py", "line one\n")
    make_file(root / "m_middle.py", "line two\n")
    make_file(root / "z_last.py", "line three\n")

    export_path = tmp_path / "project.export"
    export_project(root, export_path)

    restored = tmp_path / "restored"
    import_project(str(export_path), str(restored), overwrite=False, dry_run=False)

    for name in ("a_first.py", "m_middle.py", "z_last.py"):
        original_bytes = (root / name).read_bytes()
        restored_bytes = (restored / name).read_bytes()
        assert original_bytes == restored_bytes, f"{name} lost its exact byte content"


def test_roundtrip_empty_file(tmp_path):
    root = tmp_path / "original"
    make_file(root / "empty.py", "")

    export_path = tmp_path / "project.export"
    export_project(root, export_path)

    restored = tmp_path / "restored"
    import_project(str(export_path), str(restored), overwrite=False, dry_run=False)

    assert (restored / "empty.py").read_text(encoding="utf-8") == ""


# ==================================================
# Overwrite / dry-run behavior
# ==================================================

def test_import_does_not_overwrite_existing_file_by_default(tmp_path):
    root = tmp_path / "original"
    make_file(root / "main.py", "new content")

    export_path = tmp_path / "project.export"
    export_project(root, export_path)

    destination = tmp_path / "destination"
    make_file(destination / "main.py", "existing content - should survive")

    import_project(str(export_path), str(destination), overwrite=False, dry_run=False)

    assert (destination / "main.py").read_text(encoding="utf-8") == "existing content - should survive"


def test_import_overwrite_replaces_existing_file(tmp_path):
    root = tmp_path / "original"
    make_file(root / "main.py", "new content")

    export_path = tmp_path / "project.export"
    export_project(root, export_path)

    destination = tmp_path / "destination"
    make_file(destination / "main.py", "old content")

    import_project(str(export_path), str(destination), overwrite=True, dry_run=False)

    assert (destination / "main.py").read_text(encoding="utf-8") == "new content"


def test_dry_run_creates_no_files(tmp_path):
    root = tmp_path / "original"
    make_file(root / "main.py", "content")

    export_path = tmp_path / "project.export"
    export_project(root, export_path)

    destination = tmp_path / "destination"
    import_project(str(export_path), str(destination), overwrite=False, dry_run=True)

    assert not (destination / "main.py").exists()


# ==================================================
# Placeholder handling (binary / oversized / errored files)
# ==================================================

def test_placeholder_files_are_not_written(tmp_path):
    root = tmp_path / "original"
    (root).mkdir()
    (root / "mystery.dat").write_bytes(b"\x00\x01binary")
    make_file(root / "main.py", "real content")

    export_path = tmp_path / "project.export"
    export_project(root, export_path)

    destination = tmp_path / "destination"
    import_project(str(export_path), str(destination), overwrite=False, dry_run=False)

    assert not (destination / "mystery.dat").exists()
    assert (destination / "main.py").read_text(encoding="utf-8") == "real content"


@pytest.mark.parametrize(
    "content,expected",
    [
        ("[SKIPPED: Binary file]", True),
        ("[SKIPPED: File exceeds maximum size of 100 bytes]", True),
        ("[ERROR READING FILE: permission denied]", True),
        ("normal file content", False),
        ("", False),
    ],
)
def test_is_placeholder(content, expected):
    assert is_placeholder(content) == expected


# ==================================================
# Path safety
# ==================================================

@pytest.mark.parametrize(
    "path,expected",
    [
        ("src/main.py", True),
        ("main.py", True),
        # A leading slash is stripped before the path is joined onto
        # the destination directory, so it's neutralized (contained)
        # rather than rejected outright - same approach tar/zip use.
        ("/etc/passwd", True),
        # ".." components are always rejected, since they can escape
        # the destination even after the leading-slash strip.
        ("../../etc/passwd", False),
        ("a/../../b", False),
        ("", False),
    ],
)
def test_is_safe_relative_path(path, expected):
    assert is_safe_relative_path(path) == expected


def test_import_skips_unsafe_paths_without_writing_outside_destination(tmp_path):
    malicious_export = tmp_path / "malicious.export"
    malicious_export.write_text(
        "=" * 70 + "\n"
        "FILE CONTENTS\n"
        + "=" * 70 + "\n"
        "\n\n"
        "### FILE: ../../escaped.txt\n"
        + "-" * 70 + "\n"
        "should not be written outside destination\n",
        encoding="utf-8",
    )

    destination = tmp_path / "safe_destination"
    import_project(str(malicious_export), str(destination), overwrite=False, dry_run=False)

    escaped_file = tmp_path.parent / "escaped.txt"
    assert not (tmp_path / "escaped.txt").exists()
    assert not (destination / ".." / "escaped.txt").resolve().exists()


# ==================================================
# Parsing edge cases
# ==================================================

def test_extract_file_sections_handles_no_markers():
    assert extract_file_sections("just some random text, no markers") == []


def test_extract_file_sections_handles_multiple_files():
    # 3 separator newlines follow each file's own content (that's
    # what export_project.py actually produces between entries).
    text = (
        "FILE CONTENTS\n"
        "\n\n"
        "### FILE: a.py\n"
        + "-" * 70 + "\n"
        "content a\n"      # this file's own trailing newline
        "\n\n\n"           # the 3 separator newlines before the next marker
        "### FILE: b.py\n"
        + "-" * 70 + "\n"
        "content b"        # this file has no trailing newline
    )

    sections = extract_file_sections(text)

    assert [path for path, _ in sections] == ["a.py", "b.py"]
    assert sections[0][1] == "content a\n"
    assert sections[1][1] == "content b"


def test_missing_export_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        import_project(str(tmp_path / "nope.export"), str(tmp_path / "dest"), overwrite=False, dry_run=False)
