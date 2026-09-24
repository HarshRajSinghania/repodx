import argparse
import fnmatch
import os
from pathlib import Path
import re


COMMON_GITIGNORE_ENTRIES = ["__pycache__/", ".env", "node_modules/"]
VIRTUAL_ENVIRONMENT_DIRECTORY_NAMES = [".venv", "venv", "env"]
JUNK_FILE_SUFFIXES = [".tmp", ".log"]
README_FILE_NAMES = ["readme.md", "readme.markdown", "readme.rst", "readme.txt", "readme"]
README_INSTALLATION_HEADINGS = ["installation", "install", "kurulum"]
README_USAGE_HEADINGS = ["usage", "use", "kullanim", "kullanım"]


def read_gitignore_entries(repo_path):
    gitignore_path = repo_path / ".gitignore"

    if not gitignore_path.exists():
        return None, []

    entries = []

    try:
        gitignore_text = gitignore_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as error:
        return [], [f"Could not read .gitignore: {error}"]

    for line in gitignore_text.splitlines():
        clean_line = line.strip()

        if clean_line and not clean_line.startswith("#"):
            entries.append(clean_line)

    return entries, []


def normalize_gitignore_directory_entry(entry):
    normalized_entry = entry.removeprefix("**/").strip("/")

    while normalized_entry.endswith("/**") or normalized_entry.endswith("/*"):
        if normalized_entry.endswith("/**"):
            normalized_entry = normalized_entry[:-3].strip("/")
        else:
            normalized_entry = normalized_entry[:-2].strip("/")

    return normalized_entry


def has_gitignore_entry(entries, expected_entry):
    if entries is None:
        return False

    normalized_expected = normalize_gitignore_directory_entry(expected_entry)

    for entry in entries:
        normalized_entry = normalize_gitignore_directory_entry(entry)

        if normalized_entry == normalized_expected:
            return True

    return False


def is_path_ignored(entries, relative_text, is_directory=False):
    if not entries:
        return False

    name = relative_text.rsplit("/", 1)[-1].lower()
    relative_text = relative_text.lower()
    ignored = False

    # Later entries win, so a "!pattern" can re-include an earlier match.
    for entry in entries:
        negated = entry.startswith("!")
        pattern = entry.removeprefix("!").removeprefix("**/").lstrip("/").lower()
        directory_only = pattern.endswith("/")
        pattern = pattern.rstrip("/")

        if not pattern or (directory_only and not is_directory):
            continue

        candidates = [pattern]

        # "node_modules/*" and "node_modules/**" are read as ignoring the folder.
        if is_directory:
            candidates.append(normalize_gitignore_directory_entry(pattern))

        matched = False

        for candidate in candidates:
            target = relative_text if "/" in candidate else name

            if candidate and fnmatch.fnmatchcase(target, candidate):
                matched = True

        if matched:
            ignored = not negated

    return ignored


def is_virtual_environment(path):
    return (path / "pyvenv.cfg").is_file()


def is_junk_directory(path):
    if path.name in ["__pycache__", "node_modules"]:
        return True

    return path.name in VIRTUAL_ENVIRONMENT_DIRECTORY_NAMES and is_virtual_environment(path)


def find_junk_files(repo_path):
    entries, _ = read_gitignore_entries(repo_path)
    junk_items = []

    for current_dir, dir_names, file_names in os.walk(repo_path):
        current_path = Path(current_dir)
        kept_dir_names = []

        for dir_name in dir_names:
            dir_path = current_path / dir_name
            relative_text = dir_path.relative_to(repo_path).as_posix()

            if dir_name == ".git":
                continue

            is_ignored = is_path_ignored(entries, relative_text, is_directory=True)

            # Junk folders are reported once and never walked into.
            if is_junk_directory(dir_path):
                if not is_ignored:
                    junk_items.append(relative_text + "/")
                continue

            # Git cannot track anything inside an ignored folder.
            if is_ignored:
                continue

            kept_dir_names.append(dir_name)

        dir_names[:] = kept_dir_names

        for file_name in file_names:
            relative_text = (current_path / file_name).relative_to(repo_path).as_posix()
            is_junk = (
                file_name == ".DS_Store"
                or os.path.splitext(file_name)[1].lower() in JUNK_FILE_SUFFIXES
            )

            if is_junk and not is_path_ignored(entries, relative_text):
                junk_items.append(relative_text)

    return sorted(junk_items)


def check_gitignore(repo_path):
    entries, read_issues = read_gitignore_entries(repo_path)

    if entries is None:
        return ["Missing .gitignore file"]

    if read_issues:
        return read_issues

    missing_entries = []

    for expected_entry in COMMON_GITIGNORE_ENTRIES:
        if not has_gitignore_entry(entries, expected_entry):
            missing_entries.append(f"Missing .gitignore entry: {expected_entry}")

    return missing_entries


def markdown_headings(markdown_text):
    headings = []
    inside_fenced_code_block = False
    previous_text_line = None

    for line in markdown_text.splitlines():
        stripped_line = line.strip()

        if stripped_line.startswith("```") or stripped_line.startswith("~~~"):
            inside_fenced_code_block = not inside_fenced_code_block
            previous_text_line = None
            continue

        if inside_fenced_code_block:
            continue

        if re.match(r"^\s{0,3}(=+|-+)\s*$", line) and previous_text_line:
            headings.append(previous_text_line.strip().lower())
            previous_text_line = None
            continue

        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$", line)

        if match:
            headings.append(match.group(1).strip().lower())
            previous_text_line = None
            continue

        previous_text_line = stripped_line or None

    return headings


def has_any_heading(headings, expected_headings):
    for heading in headings:
        plain_heading = re.sub(r"[^\w\s]", "", heading)

        if plain_heading in expected_headings:
            return True

    return False


def rst_headings(rst_text):
    headings = []
    previous_text_line = None

    for line in rst_text.splitlines():
        stripped_line = line.strip()

        if re.match(r"^([=\-~^\"'`*+#:.])\1+\s*$", line):
            if previous_text_line:
                headings.append(previous_text_line.lower())
            previous_text_line = None
            continue

        previous_text_line = stripped_line or None

    return headings


def find_readme(repo_path):
    names = {path.name.lower(): path for path in repo_path.iterdir() if path.is_file()}

    for readme_name in README_FILE_NAMES:
        if readme_name in names:
            return names[readme_name]

    return None


def check_readme(repo_path):
    readme_path = find_readme(repo_path)

    if readme_path is None:
        return ["Missing README file"]

    try:
        readme_text = readme_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as error:
        return [f"Could not read {readme_path.name}: {error}"]

    if readme_path.suffix.lower() == ".rst":
        headings = rst_headings(readme_text)
    else:
        headings = markdown_headings(readme_text)

    issues = []

    if not has_any_heading(headings, README_INSTALLATION_HEADINGS):
        issues.append("Missing README heading: Installation")

    if not has_any_heading(headings, README_USAGE_HEADINGS):
        issues.append("Missing README heading: Usage")

    return issues


def build_report(repo_path):
    junk_items = find_junk_files(repo_path)
    gitignore_issues = check_gitignore(repo_path)
    readme_issues = check_readme(repo_path)

    return {
        "junk_items": junk_items,
        "gitignore_issues": gitignore_issues,
        "readme_issues": readme_issues,
    }


def count_issues(report):
    return (
        len(report["junk_items"])
        + len(report["gitignore_issues"])
        + len(report["readme_issues"])
    )


def print_section(title, items):
    print()
    print(title)

    if not items:
        print("  OK")
        return

    for item in items:
        print(f"  - {item}")


def print_report(repo_path, report):
    total_issues = count_issues(report)

    print("RepoDx report")
    print(f"Scanned path: {repo_path}")
    print(f"Issues found: {total_issues}")

    print_section("Junk files", report["junk_items"])
    print_section(".gitignore", report["gitignore_issues"])
    print_section("README", report["readme_issues"])


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scan a repository for basic hygiene issues."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path to scan. Defaults to the current folder.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    repo_path = Path(args.path).resolve()

    if not repo_path.exists() or not repo_path.is_dir():
        print(f"Error: path is not a directory: {repo_path}")
        return 2

    report = build_report(repo_path)
    print_report(repo_path, report)

    if count_issues(report) > 0:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
