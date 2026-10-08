"""
Tests for txtout.txtout

Run with:
    pip install -e .
    pip install pytest
    pytest tests/ -v
"""

from pathlib import Path

import pytest

from txtout.txtout import (
    RepoConfig,
    generate_export,
    get_files,
    load_exclusions,
)


def make_file(path: Path, content: str = "content") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_config(root: Path, output: Path) -> RepoConfig:
    config = RepoConfig()
    config.root = root
    config.output = output
    return config


# ==================================================
# Basic export / tree building
# ==================================================

def test_export_includes_all_language_files(tmp_path):
    root = tmp_path / "proj"
    make_file(root / "main.py", "print(1)")
    make_file(root / "app.rs", "fn main() {}")
    make_file(root / "notes.tex", "\\documentclass{article}")
    make_file(root / "index.html", "<html></html>")
    make_file(root / "Main.java", "class Main {}")
    make_file(root / "main.go", "package main")
    make_file(root / "main.c", "int main() {}")

    output = tmp_path / "out.export"
    config = make_config(root, output)
    generate_export(config)

    text = output.read_text(encoding="utf-8")
    for name in ("main.py", "app.rs", "notes.tex", "index.html", "Main.java", "main.go", "main.c"):
        assert f"### FILE: {name}" in text


def test_output_file_excludes_itself(tmp_path):
    root = tmp_path / "proj"
    make_file(root / "main.py", "print(1)")

    output = root / "project.export"
    config = make_config(root, output)
    generate_export(config)

    text = output.read_text(encoding="utf-8")
    assert "### FILE: project.export" not in text


def test_default_root_label_is_project_root(tmp_path):
    root = tmp_path / "02_Python"
    make_file(root / "main.py", "print(1)")

    output = tmp_path / "out.export"
    config = make_config(root, output)
    generate_export(config)

    text = output.read_text(encoding="utf-8")
    assert "Project_Root/" in text
    assert "02_Python/" not in text


def test_custom_root_label(tmp_path):
    root = tmp_path / "proj"
    make_file(root / "main.py", "print(1)")

    output = tmp_path / "out.export"
    config = make_config(root, output)
    config.root_label = "MyLabel"
    generate_export(config)

    text = output.read_text(encoding="utf-8")
    assert "MyLabel/" in text


# ==================================================
# Binary / size handling
# ==================================================

def test_binary_file_is_skipped_with_placeholder(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    # .dat is not in the default excluded extensions, so this proves
    # it's the binary-content sniff (not extension filtering) that
    # produces the placeholder.
    (root / "mystery.dat").write_bytes(b"\x00\x01\x02binarydata")

    output = tmp_path / "out.export"
    config = make_config(root, output)
    generate_export(config)

    text = output.read_text(encoding="utf-8")
    assert "### FILE: mystery.dat" in text
    assert "[SKIPPED: Binary file]" in text


def test_file_over_max_size_is_skipped(tmp_path):
    root = tmp_path / "proj"
    make_file(root / "big.txt", "x" * 200)

    output = tmp_path / "out.export"
    config = make_config(root, output)
    config.max_file_size = 50
    generate_export(config)

    text = output.read_text(encoding="utf-8")
    assert "[SKIPPED: File exceeds maximum size of 50 bytes]" in text


def test_file_under_max_size_is_included(tmp_path):
    root = tmp_path / "proj"
    make_file(root / "small.txt", "hello")

    output = tmp_path / "out.export"
    config = make_config(root, output)
    config.max_file_size = 50
    generate_export(config)

    text = output.read_text(encoding="utf-8")
    assert "hello" in text
    assert "[SKIPPED" not in text


# ==================================================
# Hidden files
# ==================================================

def test_hidden_files_excluded_by_default(tmp_path):
    root = tmp_path / "proj"
    make_file(root / ".env", "SECRET=1")
    make_file(root / "main.py", "print(1)")

    output = tmp_path / "out.export"
    config = make_config(root, output)
    generate_export(config)

    files = get_files(config)
    names = [f.name for f in files]
    assert ".env" not in names
    assert "main.py" in names


def test_hidden_files_included_with_flag(tmp_path):
    root = tmp_path / "proj"
    make_file(root / ".env", "SECRET=1")

    output = tmp_path / "out.export"
    config = make_config(root, output)
    config.show_hidden = True
    generate_export(config)

    text = output.read_text(encoding="utf-8")
    assert "### FILE: .env" in text


# ==================================================
# Exclusions: simple (auto-detect) CSV format
# ==================================================

def test_simple_format_excludes_matching_directory(tmp_path):
    root = tmp_path / "proj"
    make_file(root / "src1" / "a.py", "excluded")
    make_file(root / "keep.py", "kept")

    csv_file = tmp_path / "exclude.csv"
    csv_file.write_text("src1\n", encoding="utf-8")

    config = make_config(root, tmp_path / "out.export")
    load_exclusions(csv_file, config)
    generate_export(config)

    text = config.output.read_text(encoding="utf-8")
    assert "### FILE: src1/a.py" not in text
    assert "### FILE: keep.py" in text


def test_simple_format_extension_when_no_matching_dir(tmp_path):
    root = tmp_path / "proj"
    make_file(root / "notes.txt", "excluded")
    make_file(root / "lib" / "data.txt", "excluded too")
    make_file(root / "keep.py", "kept")

    csv_file = tmp_path / "exclude.csv"
    csv_file.write_text(".txt\n", encoding="utf-8")

    config = make_config(root, tmp_path / "out.export")
    load_exclusions(csv_file, config)
    generate_export(config)

    text = config.output.read_text(encoding="utf-8")
    assert "### FILE: notes.txt" not in text
    assert "### FILE: lib/data.txt" not in text
    assert "### FILE: keep.py" in text


def test_simple_format_exact_path_only_matches_that_path(tmp_path):
    root = tmp_path / "proj"
    make_file(root / "app" / "test.py", "excluded")
    make_file(root / "lib" / "test.py", "kept - different path, same filename")

    csv_file = tmp_path / "exclude.csv"
    csv_file.write_text("app/test.py\n", encoding="utf-8")

    config = make_config(root, tmp_path / "out.export")
    load_exclusions(csv_file, config)
    generate_export(config)

    text = config.output.read_text(encoding="utf-8")
    assert "### FILE: app/test.py" not in text
    assert "### FILE: lib/test.py" in text


def test_simple_format_exact_directory_path(tmp_path):
    root = tmp_path / "proj"
    make_file(root / "app" / "pycache" / "cache.dat", "excluded")
    make_file(root / "app" / "keep.py", "kept")

    csv_file = tmp_path / "exclude.csv"
    csv_file.write_text("app/pycache\n", encoding="utf-8")

    config = make_config(root, tmp_path / "out.export")
    load_exclusions(csv_file, config)
    generate_export(config)

    text = config.output.read_text(encoding="utf-8")
    assert "### FILE: app/pycache/cache.dat" not in text
    assert "### FILE: app/keep.py" in text


def test_simple_format_no_header_required(tmp_path):
    # First line is real data, not mistaken for a header
    root = tmp_path / "proj"
    make_file(root / "keepme.log", "kept")

    csv_file = tmp_path / "exclude.csv"
    csv_file.write_text("nonexistent_dir_name\n", encoding="utf-8")

    config = make_config(root, tmp_path / "out.export")
    # Should not raise even though there's no "type,name" header
    load_exclusions(csv_file, config)
    generate_export(config)

    text = config.output.read_text(encoding="utf-8")
    assert "### FILE: keepme.log" in text


# ==================================================
# Exclusions: structured (type,name) CSV format
# ==================================================

def test_structured_format_still_supported(tmp_path):
    root = tmp_path / "proj"
    make_file(root / "node_modules" / "pkg.js", "excluded")
    make_file(root / "secrets.env", "excluded")
    make_file(root / "app.log", "excluded")
    make_file(root / "generated" / "out.txt", "excluded")
    make_file(root / "keep.py", "kept")

    csv_file = tmp_path / "exclude.csv"
    csv_file.write_text(
        "type,name\n"
        "dir,node_modules\n"
        "file,secrets.env\n"
        "ext,log\n"
        "path,generated\n",
        encoding="utf-8",
    )

    config = make_config(root, tmp_path / "out.export")
    load_exclusions(csv_file, config)
    generate_export(config)

    text = config.output.read_text(encoding="utf-8")
    assert "### FILE: node_modules/pkg.js" not in text
    assert "### FILE: secrets.env" not in text
    assert "### FILE: app.log" not in text
    assert "### FILE: generated/out.txt" not in text
    assert "### FILE: keep.py" in text


def test_missing_exclusion_csv_raises(tmp_path):
    config = make_config(tmp_path, tmp_path / "out.export")
    with pytest.raises(FileNotFoundError):
        load_exclusions(tmp_path / "does_not_exist.csv", config)
