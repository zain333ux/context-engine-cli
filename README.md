# Context Engine CLI

Bridge the gap between massive local codebases and Large Language Models (LLMs). Context Engine CLI turns a repository into a clean, single-file context bundle that is easier to inspect, share, and paste into AI tools.

## ✨ Features

- **Deterministic LLM-ready context** that preserves the original file traversal order, even while reading files concurrently.
- **Clean single-file output** with a directory tree and clearly separated file sections for easy LLM parsing.
- **Fast directory traversal** with `os.scandir`, avoiding slower recursive path walking.
- **Memory-safe output streaming** that writes directly to disk instead of building one huge string in RAM.
- **Concurrent file reading** with `ThreadPoolExecutor` for faster aggregation on large repositories.
- **`.gitignore` and `.contextignore` support** for project-specific filtering.
- **Precompiled ignore rules** using `fnmatch.translate` and `re.Pattern` for faster repeated matching.
- **Default binary and build-artifact exclusions** for files such as `.png`, `.exe`, `.pdf`, `.pyc`, `node_modules`, `__pycache__`, and `.git`.
- **Token estimation** using the practical rule of thumb `1 token ≈ 4 characters`.
- **Token budget control** with `--max-tokens` to stop before the output exceeds an LLM context window.
- **Clean terminal UX** with scan feedback, warnings for skipped files, and a final processing summary.

## 📦 Installation

Install from PyPI:

```bash
pip install context-engine-zain333
```

After installation, the `context-engine` command is available from your terminal:

```bash
context-engine --help
```

> On Windows, if the command is not recognized after installation, make sure your Python `Scripts` directory is on `PATH`.

## 🚀 Usage

Generate a clean context file for a local project:

```bash
context-engine ./my-project
```

By default, this creates:

```bash
codebase_context.txt
```

Write to a custom output file:

```bash
context-engine ./my-project --output project_context.txt
```

Ignore additional file extensions:

```bash
context-engine ./my-project --ignore .csv,.sqlite,.bak
```

Limit the estimated token budget:

```bash
context-engine ./my-project --max-tokens 100000
```

Combine options for larger repositories:

```bash
context-engine ./my-project \
  --output llm_context.txt \
  --ignore .png,.jpg,.sqlite \
  --max-tokens 100000
```

## 🧠 Why This Exists

LLMs work best when they receive structured, relevant context. Real repositories, however, are messy: they include dependency folders, caches, binaries, build output, generated files, and enough source code to overwhelm both memory and context windows.

Context Engine CLI creates a clean, LLM-friendly snapshot of a codebase by:

- rendering the directory tree,
- appending readable source files with clear file headers,
- skipping binary or unreadable files gracefully,
- respecting ignore rules,
- estimating final token usage,
- and streaming output safely to disk.

The result is a single text file that an LLM can parse without requiring you to manually copy files, prune noise, or guess whether the final context will fit.

## 🧾 Output Format

Each generated file starts with a directory tree, followed by clearly separated file sections:

```text
CODEBASE CONTEXT
================================================================================
Directory Tree
================================================================================
my-project
|-- context_engine
|   `-- main.py
`-- pyproject.toml

================================================================================
File: context_engine/main.py
================================================================================
[FILE CONTENT HERE]
```

## 🙈 Ignore Rules

Context Engine CLI reads ignore patterns once at startup from:

- built-in defaults,
- `.gitignore`,
- `.contextignore`,
- and the optional `--ignore` argument.

Use `.contextignore` for LLM-specific exclusions without changing your Git behavior:

```text
docs/archive/
*.snapshot
large-fixtures/
```

Negated ignore rules such as `!important.py` are currently skipped.

## ⚙️ CLI Reference

```bash
context-engine TARGET_DIR [-o OUTPUT] [-i EXTENSIONS] [--max-tokens N]
```

Arguments:

- `TARGET_DIR`: Directory to scan.
- `-o`, `--output`: Output file name. Defaults to `codebase_context.txt`.
- `-i`, `--ignore`: Additional comma-separated file extensions to ignore.
- `--max-tokens`: Maximum estimated tokens to write before stopping.

## 🛠 Development

Install locally in editable mode:

```bash
python -m pip install -e .
```

Run the CLI from source:

```bash
python -m context_engine.main ./my-project
```

Run a syntax check:

```bash
python -m compileall context_engine
```

Generate the local stress-test fixture:

```bash
python test_generator.py
context-engine test_env -o test_env_context.txt
```

## 📄 Package Metadata

- Package name: `context-engine-zain333`
- Python package: `context_engine`
- Entry point: `context-engine = context_engine.main:main`
- Python version: `>=3.10`
- Runtime dependencies: none beyond the Python standard library
