#!/usr/bin/env python3

import argparse
import re
from pathlib import Path


# ==================================================
# CONFIGURATION
# ==================================================

FILE_CONTENTS_HEADER = "FILE CONTENTS"

# Matches the "### FILE: <path>" markers written by
# export_project.py, along with the blank lines and
# dashed separator line that surround them.
FILE_MARKER_RE = re.compile(
    r"\n\n\n### FILE: (?P<path>.+?)\n-{10,}\n"
)

# Placeholders written by export_project.py for files
# it could not (or chose not to) capture the content of.
PLACEHOLDER_PREFIXES = (
    "[SKIPPED:",
    "[ERROR READING FILE:",
)


# ==================================================
# LOAD EXPORT FILE
# ==================================================

def load_export(export_file):

    export_file = Path(export_file).resolve()

    if not export_file.is_file():
        raise FileNotFoundError(
            f"Export file not found: {export_file}"
        )

    return export_file.read_text(
        encoding="utf-8",
        errors="replace"
    )


# ==================================================
# EXTRACT FILE SECTIONS
# ==================================================

def extract_file_sections(text):

    # Restrict parsing to the FILE CONTENTS section
    # (if present) so the directory-tree preview can
    # never be mistaken for file markers.
    idx = text.find(FILE_CONTENTS_HEADER)

    if idx != -1:
        text = text[idx:]

    matches = list(FILE_MARKER_RE.finditer(text))

    sections = []

    for index, match in enumerate(matches):

        relative_path = match.group("path").strip()

        start = match.end()

        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        )

        content = text[start:end]

        sections.append((relative_path, content))

    return sections


# ==================================================
# HELPERS
# ==================================================

def is_placeholder(content):

    stripped = content.strip()

    return any(
        stripped.startswith(prefix)
        for prefix in PLACEHOLDER_PREFIXES
    )


def is_safe_relative_path(relative_path):

    if not relative_path:
        return False

    normalized = relative_path.replace("\\", "/").strip("/")

    if not normalized:
        return False

    parts = Path(normalized).parts

    if any(part in ("..", "") for part in parts):
        return False

    if Path(normalized).is_absolute():
        return False

    return True


# ==================================================
# IMPORT PROJECT
# ==================================================

def import_project(export_path, destination, overwrite, dry_run):

    text = load_export(export_path)

    sections = extract_file_sections(text)

    if not sections:
        print(
            "No '### FILE:' entries found in the export. "
            "Nothing to do."
        )
        return

    destination = Path(destination).resolve()

    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)

    print(f"Restoring into: {destination}")
    print()

    created = 0
    skipped_unsafe = 0
    skipped_placeholder = 0
    skipped_existing = 0

    for relative_path, content in sections:

        normalized = relative_path.replace("\\", "/").strip("/")

        if not is_safe_relative_path(relative_path):

            print(f"Skipping (unsafe path): {relative_path}")
            skipped_unsafe += 1
            continue

        target = destination / normalized

        if is_placeholder(content):

            print(f"Skipping (no content in export): {normalized}")
            skipped_placeholder += 1
            continue

        if target.exists() and not overwrite:

            print(f"Skipping (already exists): {normalized}")
            skipped_existing += 1
            continue

        if dry_run:

            print(f"Would create: {normalized}")
            created += 1
            continue

        target.parent.mkdir(parents=True, exist_ok=True)

        # Content may legitimately be empty (empty source
        # file); write it as-is.
        target.write_text(content, encoding="utf-8")

        print(f"Created: {normalized}")
        created += 1

    print()
    print("=" * 50)

    print(
        "PROJECT IMPORT (DRY RUN)"
        if dry_run
        else "PROJECT IMPORT COMPLETE"
    )

    print("=" * 50)
    print(f"Destination         : {destination}")
    print(f"Files created       : {created}")
    print(f"Skipped (exists)    : {skipped_existing}")
    print(f"Skipped (no data)   : {skipped_placeholder}")
    print(f"Skipped (unsafe)    : {skipped_unsafe}")
    print("=" * 50)


# ==================================================
# COMMAND LINE
# ==================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Recreate a project's directory structure and "
            "file contents from a file produced by "
            "export_project.py."
        )
    )

    parser.add_argument(
        "export_file",
        help="Path to the export file (e.g. project.export)"
    )

    parser.add_argument(
        "-d",
        "--destination",
        default=".",
        help=(
            "Directory to recreate the project in "
            "(default: current directory)"
        )
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite files that already exist at the destination"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without writing any files"
    )

    args = parser.parse_args()

    import_project(
        args.export_file,
        args.destination,
        args.overwrite,
        args.dry_run,
    )


# ==================================================
# ENTRY POINT
# ==================================================

if __name__ == "__main__":
    main()
