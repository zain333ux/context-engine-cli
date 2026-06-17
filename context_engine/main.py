"""Command-line interface for Context Engine."""

import argparse
import concurrent.futures
import fnmatch
import os
import re
from pathlib import Path


DEFAULT_OUTPUT_FILE = "codebase_context.txt"
DEFAULT_IGNORED_EXTENSIONS = {
    ".7z",
    ".bin",
    ".bmp",
    ".class",
    ".dll",
    ".doc",
    ".docx",
    ".dylib",
    ".exe",
    ".gif",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".pyc",
    ".pyo",
    ".pyd",
    ".pdf",
    ".png",
    ".so",
    ".tar",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
    ".log",
    ".tmp",
}
DEFAULT_IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
}
YELLOW = "\033[33m"
RESET = "\033[0m"
IgnoreRule = tuple[re.Pattern[str], bool, str]


def print_warning(message: str) -> None:
    """Print a clean yellow warning message."""
    print(f"{YELLOW}Warning: {message}{RESET}")


def estimate_tokens(text: str) -> int:
    """Estimate LLM tokens using the rough rule that 1 token is 4 characters."""
    return estimate_tokens_from_chars(len(text))


def estimate_tokens_from_chars(char_count: int) -> int:
    """Estimate LLM tokens from a character count."""
    return (char_count + 3) // 4


def get_ignored_patterns(target_dir: Path) -> set[str]:
    """Read ignore patterns from defaults and local ignore files once."""
    patterns = set(DEFAULT_IGNORED_DIRECTORIES)
    patterns.update(f"*{extension}" for extension in DEFAULT_IGNORED_EXTENSIONS)

    for ignore_file_name in (".gitignore", ".contextignore"):
        ignore_file_path = target_dir / ignore_file_name
        try:
            with ignore_file_path.open("r", encoding="utf-8") as ignore_file:
                for line in ignore_file:
                    pattern = line.strip()
                    if not pattern or pattern.startswith("#"):
                        continue
                    if pattern.startswith("!"):
                        continue
                    patterns.add(pattern)
        except FileNotFoundError:
            pass
        except OSError:
            pass

    return patterns


def parse_ignore_extensions(raw_ignore: str | None) -> set[str]:
    """Parse comma-separated extensions into normalized .ext values."""
    if not raw_ignore:
        return set()

    extensions = set()
    for item in raw_ignore.split(","):
        extension = item.strip()
        if not extension:
            continue
        if not extension.startswith("."):
            extension = f".{extension}"
        extensions.add(extension.lower())
    return extensions


def _entry_is_dir(entry: os.DirEntry[str]) -> bool:
    try:
        return entry.is_dir(follow_symlinks=False)
    except OSError:
        return False


def _safe_scandir(path: Path) -> list[os.DirEntry[str]]:
    try:
        with os.scandir(path) as entries:
            return list(entries)
    except OSError:
        return []


def compile_ignore_patterns(ignore_patterns: set[str]) -> list[IgnoreRule]:
    """Compile ignore patterns once so traversal checks are cheap."""
    compiled_rules: list[IgnoreRule] = []

    for pattern in ignore_patterns:
        normalized_pattern = pattern.replace("\\", "/").strip()
        if not normalized_pattern:
            continue

        directory_only = normalized_pattern.endswith("/")
        normalized_pattern = normalized_pattern.rstrip("/")
        if not normalized_pattern:
            continue

        if normalized_pattern.startswith("/"):
            match_mode = "path"
            normalized_pattern = normalized_pattern.lstrip("/")
        elif "/" in normalized_pattern:
            match_mode = "path"
        else:
            match_mode = "part"

        compiled_rules.append(
            (re.compile(fnmatch.translate(normalized_pattern)), directory_only, match_mode)
        )

    return compiled_rules


def _relative_path(path: Path, target_dir: Path) -> str:
    try:
        return path.relative_to(target_dir).as_posix()
    except ValueError:
        return path.as_posix()


def should_ignore_path(
    path: Path,
    target_dir: Path,
    ignore_rules: list[IgnoreRule],
    is_directory: bool = False,
) -> bool:
    """Return True when a path matches any precompiled ignore rule."""
    relative_path = _relative_path(path, target_dir)
    path_parts = relative_path.split("/")

    for rule, directory_only, match_mode in ignore_rules:
        if directory_only and not is_directory:
            continue

        if match_mode == "path":
            if rule.match(relative_path):
                return True
            continue

        if any(rule.match(part) for part in path_parts):
            return True

    return False


def should_ignore_entry(
    entry: os.DirEntry[str],
    target_dir: Path,
    ignore_rules: list[IgnoreRule],
) -> bool:
    """Return True when a scanned directory entry matches a precompiled rule."""
    path = Path(entry.path)
    is_directory = _entry_is_dir(entry)
    return should_ignore_path(path, target_dir, ignore_rules, is_directory)


def generate_file_tree(target_dir: Path, ignore_rules: list[IgnoreRule]) -> tuple[str, list[Path]]:
    """Recursively map the directory tree and collect valid file paths."""
    files: list[Path] = []
    tree_lines = [target_dir.name]

    def walk(directory: Path, prefix: str = "") -> None:
        entries: list[os.DirEntry[str]] = [
            entry
            for entry in _safe_scandir(directory)
            if not should_ignore_entry(entry, target_dir, ignore_rules)
        ]
        entries.sort(key=lambda entry: (not _entry_is_dir(entry), entry.name.lower()))

        for index, entry in enumerate(entries):
            is_last = index == len(entries) - 1
            connector = "`-- " if is_last else "|-- "
            tree_lines.append(f"{prefix}{connector}{entry.name}")

            entry_path = Path(entry.path)
            if _entry_is_dir(entry):
                extension = "    " if is_last else "|   "
                walk(entry_path, f"{prefix}{extension}")
            else:
                files.append(entry_path)

    walk(target_dir)
    return "\n".join(tree_lines), files


def build_directory_tree(target_dir: Path, ignore_rules: list[IgnoreRule]) -> str:
    """Build a printable directory tree for the target codebase."""
    directory_tree, _ = generate_file_tree(target_dir, ignore_rules)
    return directory_tree


def collect_source_files(target_dir: Path, ignore_rules: list[IgnoreRule]) -> list[Path]:
    """Collect source files that should be included in the context output."""
    _, source_files = generate_file_tree(target_dir, ignore_rules)
    return source_files


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def build_context_file(
    tree_string: str,
    valid_files: list[Path],
    output_path: Path,
    max_tokens: int | None = None,
) -> tuple[int, int, int]:
    """Read files concurrently and write sections in deterministic file order."""
    separator = "=" * 80
    processed_count = 0
    skipped_count = 0
    header = (
        "CODEBASE CONTEXT\n"
        f"{separator}\n"
        "Directory Tree\n"
        f"{separator}\n"
        f"{tree_string}\n\n"
    )
    current_char_count = len(header)
    current_token_count = estimate_tokens_from_chars(current_char_count)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def read_file_section(file_path: Path) -> tuple[Path, str | None, str | None]:
        try:
            contents = file_path.read_text(encoding="utf-8")
        except PermissionError:
            return file_path, None, f"Permission denied, skipped {_display_path(file_path)}"
        except UnicodeDecodeError:
            return file_path, None, f"Could not decode as UTF-8, skipped {_display_path(file_path)}"
        except OSError as error:
            return file_path, None, f"Could not read {_display_path(file_path)} ({error})"

        file_section = (
            f"{separator}\n"
            f"File: {_display_path(file_path)}\n"
            f"{separator}\n"
            f"{contents}"
        )
        if contents and not contents.endswith("\n"):
            file_section += "\n"
        file_section += "\n"

        return file_path, file_section, None

    with output_path.open("w", encoding="utf-8") as output_file:
        output_file.write(header)

        if max_tokens is not None and current_token_count > max_tokens:
            print_warning("Directory tree alone exceeds the max token limit; skipped all files.")
            return 0, len(valid_files), current_token_count

        max_workers = min(32, (os.cpu_count() or 1) + 4)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = executor.map(read_file_section, valid_files)

            for file_path, file_section, warning in results:
                if warning is not None:
                    skipped_count += 1
                    print_warning(warning)
                    continue

                if file_section is None:
                    skipped_count += 1
                    continue

                next_char_count = current_char_count + len(file_section)
                next_token_count = estimate_tokens_from_chars(next_char_count)
                if max_tokens is not None and next_token_count > max_tokens:
                    skipped_count += len(valid_files) - processed_count - skipped_count
                    print_warning(
                        "Max token limit reached; skipped "
                        f"{_display_path(file_path)} and remaining files."
                    )
                    break

                output_file.write(file_section)
                current_char_count = next_char_count
                current_token_count = next_token_count
                processed_count += 1

    return processed_count, skipped_count, current_token_count


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="context-engine",
        usage="context-engine TARGET_DIR [-o OUTPUT] [-i EXTENSIONS] [--max-tokens N]",
        description="Aggregate codebase files into one text file for LLM consumption.",
        epilog="Example: context-engine ./my-project -o context.txt --max-tokens 100000",
    )
    parser.add_argument(
        "target_dir",
        metavar="TARGET_DIR",
        type=Path,
        help="Directory to scan. This argument is required.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT_FILE,
        help=f"Output file name. Defaults to {DEFAULT_OUTPUT_FILE}.",
    )
    parser.add_argument(
        "-i",
        "--ignore",
        default=None,
        help="Additional comma-separated file extensions to ignore, e.g. .png,.zip,db.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Maximum estimated tokens to write before stopping.",
    )
    return parser


def run(args: argparse.Namespace) -> Path:
    """Validate arguments and coordinate the context generation workflow."""
    target_dir = args.target_dir.expanduser().resolve()
    if not target_dir.exists():
        raise FileNotFoundError(f"Target directory does not exist: {target_dir}")
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Target path is not a directory: {target_dir}")
    if args.max_tokens is not None and args.max_tokens <= 0:
        raise ValueError("--max-tokens must be a positive integer")

    print(f"Scanning directory: {target_dir}...")
    ignore_patterns = get_ignored_patterns(target_dir)
    ignore_patterns.update(f"*{extension}" for extension in parse_ignore_extensions(args.ignore))
    ignore_rules = compile_ignore_patterns(ignore_patterns)
    output_path = Path(args.output).expanduser()
    if not output_path.is_absolute():
        output_path = Path(os.getcwd()) / output_path

    tree_string, valid_files = generate_file_tree(target_dir, ignore_rules)
    processed_count, skipped_count, estimated_tokens = build_context_file(
        tree_string,
        valid_files,
        output_path,
        args.max_tokens,
    )
    print(
        f"Successfully processed {processed_count} files. "
        f"Skipped {skipped_count} files. "
        f"Estimated tokens: {estimated_tokens}."
    )

    return output_path


def main() -> None:
    """CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    try:
        output_path = run(args)
    except (FileNotFoundError, NotADirectoryError, ValueError) as error:
        parser.error(str(error))
    print(f"Context written to: {output_path}")


if __name__ == "__main__":
    main()
