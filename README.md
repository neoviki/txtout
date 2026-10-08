# txtout

Flatten an entire project (directory tree and file contents) into a single, readable, portable plain-text file using `txtout`, and reconstruct it later with `txtin`, preserving the exact directory structure and file contents.


Useful for:

* Pasting a whole codebase into an LLM prompt (for small projects)
* Sending a project as a single attachment
* Snapshotting and restoring a project tree
* Comparing two project snapshots to quickly identify added, removed, or modified files

## Install

```bash
# Directly from Git (recommended)
pipx install git+https://github.com/neoviki/txtout.git

# From a cloned checkout
pip install .

# From a cloned checkout, isolated
pipx install .
```

All methods install the `txtout` and `txtin` commands on your `PATH` — no
manual `chmod` or symlinking needed.


```bash
txtout --help
txtin --help
```
## Update to a Newer Version

If installed with `pipx`, update the installed package with:

```bash
pipx upgrade txtout
```

To reinstall directly from the latest Git repository version:

```bash
pipx uninstall txtout
pipx install git+https://github.com/neoviki/txtout.git
```

## Uninstall

To remove `txtout`:

```bash
pipx uninstall txtout
```

This removes the installed `txtout` and `txtin` commands.


## Usage

### Export

```bash
txtout                            # export current dir -> project.export
txtout .                          # export current dir -> project.export
txtout . -o mybackup.txt          # any output name/extension works
txtout . -e excluded_files.csv    # apply exclusions from a CSV
```

### Import (restore)

```bash
txtin project.export                        # restore into current dir
txtin project.export -d ./restored           # restore into another dir
txtin project.export --overwrite              # overwrite existing files
txtin project.export --dry-run                # preview only, no writes
```

## Exclude CSV Format

You can specify files, directories, and extensions to exclude in a CSV file named excludes.csv.

By default, txtout searches for excludes.csv in the current directory. If you specify a different exclusion file using the -e option, it uses that file instead.

For example:

```text
src1
.txt
app/test.py
app/pycache
node_modules
.log
```

Each line can contain a file, directory, extension, or path to exclude.

- No `/` and a matching **directory** exists anywhere in the tree -> excludes that directory name everywhere
- Starts with `.` -> excluded as a file **extension**, everywhere
- No `/` and a matching **file** exists anywhere in the tree -> excludes that filename everywhere
- Contains `/` -> excluded as an **exact path** relative to the project root (file or directory)

## Notes

- All plain-text source files are included by default (Python, Rust, Go,
  C/C++, Java, LaTeX, HTML, etc.) - only binary/compiled artifacts
  (`.pyc`, `.dll`, `.jar`, images, ...) are excluded by default.
- The tree preview inside the export file always shows a generic
  `Project_Root/` label instead of your real folder name (override with
  `--root-label`).
- `txtout` prints the resolved directory it's about to scan
  (`Scanning: /abs/path`) before it runs, so you can confirm it's using
  the folder you expect.

## License

MIT - see [LICENSE](LICENSE).

## Acknowledgments

This project was developed collaboratively with the support of LLM-based tools, including Claude Sonnet 5, Perplexity, and OpenAI. These tools supported the project’s optimization, documentation, installation instructions, and test-case preparation.
