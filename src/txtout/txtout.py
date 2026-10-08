#!/usr/bin/env python3

import argparse
import csv
import os
from pathlib import Path


# ==================================================
# DEFAULT CONFIGURATION
# ==================================================
#
# NOTE ON LANGUAGE SUPPORT:
# This exporter does NOT use a whitelist of source-code
# extensions - it includes every file by default UNLESS
# it matches an exclude rule below. That means LaTeX
# (.tex), HTML (.html/.htm), C (.c/.h), C++ (.cpp/.hpp/
# .cc), Java (.java), Python (.py), Rust (.rs), Go (.go),
# and any other plain-text source file are already
# included automatically. Only compiled/binary artifacts
# (below) are excluded by default.

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "build",
    "dist",
    "target",
    ".pytest_cache",
    ".mypy_cache",
}

DEFAULT_EXCLUDE_FILES = {
    ".DS_Store",
    "Thumbs.db",
}

DEFAULT_EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".so",
    ".dll",
    ".exe",
    ".bin",
    ".o",
    ".a",
    ".class",
    ".jar",
    ".zip",
    ".gz",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".mp4",
    ".mp3",
    ".sqlite",
    ".db",
}


# ==================================================
# CONFIGURATION
# ==================================================

class RepoConfig:

    def __init__(self):

        self.root = Path.cwd()
        self.output = Path("project.export")
        self.root_label = "Project_Root"

        self.exclude_dirs = set(DEFAULT_EXCLUDE_DIRS)
        self.exclude_files = set(DEFAULT_EXCLUDE_FILES)
        self.exclude_extensions = set(
            DEFAULT_EXCLUDE_EXTENSIONS
        )

        self.exclude_paths = set()

        self.show_hidden = False

        # Maximum file size: 1 GB
        self.max_file_size = 1_000_000_000


# ==================================================
# LOAD EXCLUSIONS FROM CSV
# ==================================================
#
# Two formats are supported:
#
# 1. STRUCTURED (explicit, unambiguous):
#
#       type,name
#       dir,node_modules
#       ext,.log
#       file,secrets.env
#       path,app/generated
#
# 2. SIMPLE (one pattern per line, no header, type is
#    auto-detected by inspecting the actual project
#    tree):
#
#       src1
#       .txt
#       app/test.py
#       app/pycache
#
#    Detection rules, checked in this order, for each
#    bare (no "/") entry:
#      - if a DIRECTORY with that exact name exists
#        anywhere under the project root -> excluded
#        as a directory name (matches everywhere)
#      - elif it starts with "."               -> extension
#      - elif a FILE with that exact name exists
#        anywhere under the project root -> excluded
#        as a filename (matches everywhere)
#      - elif it contains a "."                -> treated
#        as an extension (the part after the last dot)
#      - otherwise                              -> treated
#        as a directory name
#    An entry containing "/" or "\" is always treated as
#    an exact path relative to the project root (file or
#    directory) - never matched by name elsewhere.

def _dir_exists_anywhere(root, name):

    for dirpath, dirnames, _filenames in os.walk(root):

        if name in dirnames:
            return True

    return False


def _file_exists_anywhere(root, name):

    for _dirpath, _dirnames, filenames in os.walk(root):

        if name in filenames:
            return True

    return False


def _classify_simple_entry(entry, config):

    normalized = entry.replace("\\", "/").strip()

    if not normalized:
        return

    if "/" in normalized:

        clean = normalized.strip("/")
        config.exclude_paths.add(clean)
        print(f"Exclude (path)      : {clean}")
        return

    if _dir_exists_anywhere(config.root, normalized):

        config.exclude_dirs.add(normalized)
        print(f"Exclude (directory) : {normalized}")
        return

    if normalized.startswith("."):

        ext = normalized.lower()
        config.exclude_extensions.add(ext)
        print(f"Exclude (extension) : {ext}")
        return

    if _file_exists_anywhere(config.root, normalized):

        config.exclude_files.add(normalized)
        print(f"Exclude (file)      : {normalized}")
        return

    if "." in normalized:

        ext = "." + normalized.rsplit(".", 1)[-1]
        config.exclude_extensions.add(ext.lower())
        print(f"Exclude (extension) : {ext.lower()}")

    else:

        config.exclude_dirs.add(normalized)
        print(f"Exclude (directory) : {normalized}")


def load_exclusions(csv_file, config):

    csv_file = Path(csv_file).resolve()

    if not csv_file.is_file():
        raise FileNotFoundError(
            f"Exclusion CSV not found: {csv_file}"
        )

    with csv_file.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        rows = [
            row for row in csv.reader(file)
            if any(cell.strip() for cell in row)
        ]

    if not rows:
        return

    header = [
        cell.strip().lower()
        for cell in rows[0]
    ]

    # ----------------------------------------------
    # STRUCTURED FORMAT: type,name
    # ----------------------------------------------

    if {"type", "name"}.issubset(set(header)):

        type_idx = header.index("type")
        name_idx = header.index("name")

        for row in rows[1:]:

            kind = (
                row[type_idx].strip().lower()
                if len(row) > type_idx else ""
            )

            name = (
                row[name_idx].strip()
                if len(row) > name_idx else ""
            )

            if not name:
                continue

            if kind == "dir":

                config.exclude_dirs.add(name)

            elif kind == "file":

                config.exclude_files.add(name)

            elif kind == "ext":

                if not name.startswith("."):
                    name = "." + name

                config.exclude_extensions.add(
                    name.lower()
                )

            elif kind == "path":

                config.exclude_paths.add(
                    name.replace("\\", "/").strip("/")
                )

            else:

                print(
                    f"Warning: Unknown exclusion type "
                    f"'{kind}' for '{name}'"
                )

        return

    # ----------------------------------------------
    # SIMPLE FORMAT: one entry per line, auto-detected
    # ----------------------------------------------

    for row in rows:

        entry = row[0].strip()

        if not entry:
            continue

        _classify_simple_entry(entry, config)


# ==================================================
# EXCLUSION CHECK
# ==================================================

def should_exclude(path, config):

    if path.name in config.exclude_files:
        return True

    if path.suffix.lower() in config.exclude_extensions:
        return True

    relative_path = path.relative_to(
        config.root
    ).as_posix()

    if relative_path in config.exclude_paths:
        return True

    return False


# ==================================================
# BINARY FILE CHECK
# ==================================================

def is_binary(path):

    try:

        with path.open("rb") as file:
            chunk = file.read(8192)

        return b"\0" in chunk

    except OSError:

        return True


# ==================================================
# COLLECT FILES
# ==================================================

def get_files(config):

    root = config.root
    files = []

    output = config.output.resolve()

    def walk(directory):

        try:

            entries = sorted(
                directory.iterdir(),
                key=lambda p: (
                    not p.is_dir(),
                    p.name.lower()
                )
            )

        except OSError as error:

            print(
                f"Warning: Cannot read directory "
                f"{directory}: {error}"
            )
            return

        for path in entries:

            # Avoid symbolic links
            if path.is_symlink():
                continue

            # Skip hidden files and directories
            if (
                not config.show_hidden
                and path.name.startswith(".")
            ):
                continue

            # Exclude directories
            if path.is_dir():

                if path.name in config.exclude_dirs:
                    continue

                if should_exclude(path, config):
                    continue

                walk(path)

            # Process files
            elif path.is_file():

                if should_exclude(path, config):
                    continue

                # Never include the output file itself
                if path.resolve() == output:
                    continue

                files.append(path)

    walk(root)

    return sorted(
        files,
        key=lambda p: p.relative_to(root).as_posix().lower()
    )


# ==================================================
# BUILD DIRECTORY TREE
# ==================================================

def build_tree(root, files, label="Project_Root"):

    # Build a set of all included directories
    directories = set()

    for file in files:

        parent = file.parent

        while parent != root:

            directories.add(parent)
            parent = parent.parent

    included_files = set(files)

    def tree_lines(directory, prefix=""):

        entries = []

        for path in directories:

            if path.parent == directory:
                entries.append(path)

        for path in included_files:

            if path.parent == directory:
                entries.append(path)

        entries.sort(
            key=lambda p: (
                not p.is_dir(),
                p.name.lower()
            )
        )

        lines = []

        for index, path in enumerate(entries):

            last = index == len(entries) - 1

            branch = (
                "└── " if last else "├── "
            )

            name = path.name

            if path.is_dir():
                name += "/"

            lines.append(
                prefix + branch + name
            )

            if path.is_dir():

                extension = (
                    "    " if last else "│   "
                )

                lines.extend(
                    tree_lines(
                        path,
                        prefix + extension
                    )
                )

        return lines

    return (
        [label + "/"]
        + tree_lines(root)
    )


# ==================================================
# READ FILE CONTENT
# ==================================================

def read_file(path, config):

    try:

        if path.stat().st_size > config.max_file_size:

            return (
                "[SKIPPED: File exceeds maximum size "
                f"of {config.max_file_size} bytes]"
            )

        if is_binary(path):

            return "[SKIPPED: Binary file]"

        return path.read_text(
            encoding="utf-8",
            errors="replace"
        )

    except OSError as error:

        return f"[ERROR READING FILE: {error}]"


# ==================================================
# GENERATE EXPORT
# ==================================================

def generate_export(config):

    root = config.root.resolve()

    print(f"Scanning: {root}")

    files = get_files(config)

    lines = []


    # ----------------------------------------------
    # txtout INFORMATION
    # ----------------------------------------------

    export_filename = config.output.name

    lines.append(
        f"# This project export file <{export_filename}> was created using the"
    )
    lines.append(
        "# txtout tool developed by Viki."
    )
    lines.append("#")
    lines.append(
        "# Check the repository for more details:"
    )
    lines.append(
        "# https://github.com/neoviki/txtout"
    )
    lines.append("#")
    lines.append(
        "# To restore this project, you need the txtin tool."
    )
    lines.append("#")
    lines.append(
        "# Install txtout using:"
    )
    lines.append("#")
    lines.append(
        "# pipx install git+https://github.com/neoviki/txtout.git"
    )
    lines.append("#")
    lines.append(
        "# The above command installs both txtin and txtout, which you can"
    )
    lines.append(
        "# use to import and export projects."
    )
    lines.append("#")
    lines.append(
        "# Once the tools are installed, create a new empty directory, enter it,"
    )
    lines.append(
        f"# copy the <{export_filename}> file into the directory, and run:"
    )
    lines.append("#")
    lines.append(
        f"# txtin {export_filename}"
    )
    lines.append("#")
    lines.append(
        "# This will reconstruct the project structure and file contents."
    )
    lines.append("")

    # ----------------------------------------------
    # REPOSITORY STRUCTURE
    # ----------------------------------------------

    lines.append("=" * 70)
    lines.append("REPOSITORY STRUCTURE")
    lines.append("=" * 70)
    lines.append("")

    lines.extend(
        build_tree(root, files, label=config.root_label)
    )

    # ----------------------------------------------
    # FILE CONTENTS
    # ----------------------------------------------

    lines.append("")
    lines.append("")
    lines.append("=" * 70)
    lines.append("FILE CONTENTS")
    lines.append("=" * 70)

    for path in files:

        relative_path = path.relative_to(
            root
        ).as_posix()

        lines.append("")
        lines.append("")
        lines.append(
            f"### FILE: {relative_path}"
        )
        lines.append("-" * 70)

        content = read_file(
            path,
            config
        )

        lines.append(content)

    # ----------------------------------------------
    # WRITE OUTPUT
    # ----------------------------------------------

    output = config.output.resolve()

    output.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    print()
    print("=" * 50)
    print("REPOSITORY EXPORT COMPLETE")
    print("=" * 50)
    print(f"Repository    : {root}")
    print(f"Files exported: {len(files)}")
    print(f"Output        : {output}")
    print("=" * 50)


# ==================================================
# COMMAND LINE
# ==================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Export repository directory structure "
            "and file contents into one text file."
        )
    )

    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help=(
            "Repository directory (default: the current "
            "working directory you run this script from - "
            "NOT the script's own directory)"
        )
    )

    parser.add_argument(
        "-o",
        "--output",
        default="project.export",
        help=(
            "Output file (default: project.export). "
            "Any filename/extension is accepted, e.g. "
            "-o project.txt or -o myrepo.export"
        )
    )

    parser.add_argument(
        "--root-label",
        default="Project_Root",
        help=(
            "Label used for the top of the tree preview "
            "instead of your real folder name "
            "(default: Project_Root)"
        )
    )

    parser.add_argument(
        "-e",
        "--exclude-csv",
        help="CSV file containing exclusions"
    )

    parser.add_argument(
        "--exclude-dirs",
        nargs="*",
        default=[],
        help="Additional directory names to exclude"
    )

    parser.add_argument(
        "--exclude-files",
        nargs="*",
        default=[],
        help="Additional filenames to exclude"
    )

    parser.add_argument(
        "--exclude-ext",
        nargs="*",
        default=[],
        help="Additional file extensions to exclude"
    )

    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden files and directories"
    )

    parser.add_argument(
        "--max-size",
        type=int,
        default=1_000_000_000,
        help="Maximum file size in bytes (default: 1 GB)"
    )

    args = parser.parse_args()

    # ----------------------------------------------
    # INITIALIZE CONFIG
    # ----------------------------------------------

    config = RepoConfig()

    config.root = Path(args.root).resolve()
    config.output = Path(args.output).resolve()

    config.show_hidden = args.include_hidden
    config.max_file_size = args.max_size
    config.root_label = args.root_label

    # ----------------------------------------------
    # LOAD CSV EXCLUSIONS
    # ----------------------------------------------

    if args.exclude_csv:
        # User explicitly provided -e
        exclude_csv = Path(args.exclude_csv).resolve()

    else:
        # Automatically check the project root
        exclude_csv = config.root / "excludes.csv"

    if exclude_csv.is_file():
        print(f"Using exclusion file: {exclude_csv}")
        print(
            f"Generating project with exclusions "
            f"from {exclude_csv.name}"
        )

        load_exclusions(exclude_csv, config)

    elif args.exclude_csv:
        parser.error(
            f"Exclusion CSV not found: {exclude_csv}"
        )
    else:
        print(
            "No excludes.csv found. "
            "Generating project without CSV exclusions."
        )

    # ----------------------------------------------
    # COMMAND-LINE EXCLUSIONS
    # ----------------------------------------------

    config.exclude_dirs.update(
        args.exclude_dirs
    )

    config.exclude_files.update(
        args.exclude_files
    )

    for ext in args.exclude_ext:

        if not ext.startswith("."):
            ext = "." + ext

        config.exclude_extensions.add(
            ext.lower()
        )

    # ----------------------------------------------
    # VALIDATE
    # ----------------------------------------------

    if not config.root.is_dir():

        parser.error(
            "Repository directory does not exist."
        )

    if config.max_file_size < 0:

        parser.error(
            "--max-size cannot be negative."
        )

    # ----------------------------------------------
    # GENERATE
    # ----------------------------------------------

    generate_export(config)


# ==================================================
# ENTRY POINT
# ==================================================

if __name__ == "__main__":
    main()
