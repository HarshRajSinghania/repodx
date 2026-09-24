"""RepoDx: check a project for leaked secrets and repo hygiene before you push it."""

import argparse
import base64
import fnmatch
import json
import os
from pathlib import Path
import re
import sys


__version__ = "0.2.0"

COMMON_GITIGNORE_ENTRIES = ["__pycache__/", ".env", "node_modules/"]
VIRTUAL_ENVIRONMENT_DIRECTORY_NAMES = [".venv", "venv", "env"]
BUILD_OUTPUT_DIRECTORY_NAMES = [".next", ".nuxt", ".svelte-kit", "dist", "coverage"]
JUNK_FILE_SUFFIXES = [".tmp", ".log"]
README_FILE_NAMES = ["readme.md", "readme.markdown", "readme.rst", "readme.txt", "readme"]
README_INSTALLATION_HEADINGS = ["installation", "install", "kurulum"]
README_USAGE_HEADINGS = ["usage", "use", "kullanim", "kullanım"]


def read_gitignore_entries(repo_path, file_name=".gitignore"):
    gitignore_path = repo_path / file_name

    if not gitignore_path.exists():
        return None, []

    entries = []

    try:
        gitignore_text = gitignore_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as error:
        return [], [f"Could not read {file_name}: {error}"]

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
    if path.name in ["__pycache__", "node_modules"] + BUILD_OUTPUT_DIRECTORY_NAMES:
        return True

    return path.name in VIRTUAL_ENVIRONMENT_DIRECTORY_NAMES and is_virtual_environment(path)


def scan_tree(repo_path):
    """Walk the repo once and return the junk items and the files Git would pick up."""
    entries, _ = read_gitignore_entries(repo_path)
    excluded_entries, _ = read_gitignore_entries(repo_path, ".repodxignore")
    junk_items = []
    files = []

    for current_dir, dir_names, file_names in os.walk(repo_path):
        current_path = Path(current_dir)
        kept_dir_names = []

        for dir_name in dir_names:
            dir_path = current_path / dir_name
            relative_text = dir_path.relative_to(repo_path).as_posix()

            if dir_name == ".git":
                continue

            if is_path_ignored(excluded_entries, relative_text, is_directory=True):
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

            if is_path_ignored(excluded_entries, relative_text):
                continue

            if is_path_ignored(entries, relative_text):
                continue

            files.append(relative_text)
            is_junk = (
                file_name == ".DS_Store"
                or os.path.splitext(file_name)[1].lower() in JUNK_FILE_SUFFIXES
            )

            if is_junk:
                junk_items.append(relative_text)

    return sorted(junk_items), sorted(files)


def find_junk_files(repo_path):
    return scan_tree(repo_path)[0]


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


SEVERITIES = ["critical", "warning", "info"]
SEVERITY_PENALTIES = {"critical": 25, "warning": 8, "info": 2}
LARGE_FILE_WARNING_BYTES = 50 * 1024 * 1024
LARGE_FILE_LIMIT_BYTES = 100 * 1024 * 1024
MAX_SCANNED_FILE_BYTES = 2 * 1024 * 1024
AGENT_FILE_NAMES = ["agents.md", "claude.md"]
AGENT_FILE_MAX_LINES = 300
ENV_EXAMPLE_NAMES = [".env.example", ".env.sample", ".env.template", ".env.dist"]
LICENSE_FILE_NAMES = ["license", "license.md", "license.txt", "copying", "unlicense"]
INLINE_IGNORE_MARKER = "repodx:ignore"

# (name, regex). Only patterns with a distinctive prefix, to keep false alarms rare.
SECRET_PATTERNS = [
    ("Anthropic API key", r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("OpenAI API key", r"sk-(?:proj|svcacct|admin)-[A-Za-z0-9_\-]{20,}"),
    ("OpenAI API key", r"\bsk-[A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20}\b"),
    ("AWS access key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    ("GitHub token", r"\bgithub_pat_[A-Za-z0-9_]{60,}\b"),
    ("Stripe secret key", r"\b(?:sk|rk)_live_[A-Za-z0-9]{20,}\b"),
    ("Supabase secret key", r"\bsb_secret_[A-Za-z0-9_\-]{20,}"),
    ("Slack token", r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"),
    ("Hugging Face token", r"\bhf_[A-Za-z0-9]{34,}\b"),
    ("Groq API key", r"\bgsk_[A-Za-z0-9]{48,}\b"),
    ("SendGrid API key", r"\bSG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}\b"),
    ("Telegram bot token", r"\b\d{8,10}:AA[A-Za-z0-9_\-]{33}\b"),
    ("Private key", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"),
]
GOOGLE_API_KEY_PATTERN = r"\bAIza[0-9A-Za-z_\-]{35}\b"
JWT_PATTERN = r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"
DATABASE_URL_PATTERN = (
    r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss|amqps?)://"
    r"([^\s:/@'\"`]+):([^\s@/'\"`]+)@([^\s/:'\"`?]+)"
)
ENV_USAGE_PATTERN = r"process\.env\.|import\.meta\.env\.|os\.environ|os\.getenv\(|Deno\.env\.get"  # repodx:ignore
LOCAL_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "db", "postgres", "mysql", "redis", "mongo"]
PLACEHOLDER_PASSWORDS = ["password", "passwd", "pass", "secret", "changeme", "admin", "root", "test", "postgres"]
PLACEHOLDER_MARKERS = ["example", "xxx", "your", "<", "${", "{{", "***", "..."]

COMPILED_SECRET_PATTERNS = [(name, re.compile(pattern)) for name, pattern in SECRET_PATTERNS]

FIXES = {
    "secret": (
        "Delete the key from the file, then revoke/rotate it in the provider dashboard "
        "(assume it is already stolen if it was ever pushed). Load it from an environment "
        "variable or a secret manager instead, and keep the real value in an ignored .env file."
    ),
    "google-api-key": (
        "Firebase web config keys are public by design and are fine if your Security Rules are strict. "
        "Any other Google key (Gemini, Maps, Cloud) must not be in the repo: rotate it and restrict it "
        "to your app in Google Cloud Console."
    ),
    "database-url": (
        "Move the connection string into an ignored .env file and change the database password: "
        "anyone who can read the repo can log in to your database."
    ),
    "supabase-service-role": (
        "The service_role key bypasses Row Level Security. Never ship it to a browser or commit it: "
        "rotate it in Supabase (Settings > API) and use it only in server code via an environment variable."
    ),
    "supabase-rls": (
        "Add `alter table <name> enable row level security;` and write policies for each table. "
        "Without RLS, anyone with your public anon key can read and change every row."
    ),
    "firebase-rules": (
        "Replace `if true` / `true` with rules that check `request.auth` (for example "
        "`allow read, write: if request.auth != null && request.auth.uid == userId;`)."
    ),
    "env-file": (
        "Add `.env*` and `!.env.example` to .gitignore, run `git rm --cached <file>`, and rotate any "
        "secret it contained. Commit a `.env.example` with empty values instead."
    ),
    "large-file": (
        "GitHub rejects files over 100 MB and warns over 50 MB. Remove it from the repo, "
        "host it elsewhere, or track it with Git LFS."
    ),
    "junk": (
        "Add it to .gitignore and remove it from Git with `git rm -r --cached <path>`. "
        "Dependencies, caches and build output can always be recreated."
    ),
    "gitignore": "Add the missing entries to .gitignore (see github.com/github/gitignore for templates).",
    "readme": "Add a README.md that says what the project does, how to install it and how to use it.",
    "readme-section": "Add `## Installation` and `## Usage` sections so a stranger can run your project in minutes.",
    "license": (
        "Add a LICENSE file (choosealicense.com). Without one, nobody may legally use or copy your code, "
        "even if the repo is public."
    ),
    "env-example": (
        "Your code reads environment variables, but there is no .env.example. Add one listing every "
        "variable name with an empty or fake value, so others (and AI agents) know what to set."
    ),
    "agent-file-size": (
        "Keep AGENTS.md / CLAUDE.md short (under ~300 lines) and concrete: setup, test command, conventions. "
        "Long instruction files get ignored by coding agents."
    ),
}


def make_finding(check_id, severity, title, path=None, line=None, detail=None):
    return {
        "id": check_id,
        "severity": severity,
        "title": title,
        "path": path,
        "line": line,
        "detail": detail,
        "fix": FIXES[check_id],
    }


def mask_secret(value):
    if len(value) <= 8:
        return "*" * len(value)

    return value[:6] + "..." + value[-2:]


def read_text_file(path):
    try:
        if path.stat().st_size > MAX_SCANNED_FILE_BYTES:
            return None

        data = path.read_bytes()
    except OSError:
        return None

    if b"\0" in data[:4096]:
        return None

    return data.decode("utf-8", errors="replace")


def decode_jwt_payload(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, IndexError):
        return None


def is_placeholder(value):
    lowered = value.lower()
    return lowered in PLACEHOLDER_PASSWORDS or any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def scan_line_for_secrets(line):
    """Return (check_id, severity, title, secret_text) tuples found in one line."""
    hits = []

    for name, pattern in COMPILED_SECRET_PATTERNS:
        for match in pattern.finditer(line):
            hits.append(("secret", "critical", name, match.group(0)))

    for match in re.finditer(GOOGLE_API_KEY_PATTERN, line):
        hits.append(("google-api-key", "warning", "Google API key", match.group(0)))

    for match in re.finditer(JWT_PATTERN, line):
        payload = decode_jwt_payload(match.group(0))

        if isinstance(payload, dict) and payload.get("role") == "service_role":
            hits.append(("supabase-service-role", "critical", "Supabase service_role key", match.group(0)))

    for match in re.finditer(DATABASE_URL_PATTERN, line):
        user, password, host = match.groups()

        if host.lower() in LOCAL_HOSTS or is_placeholder(password):
            continue

        hits.append(("database-url", "critical", "Database URL with password", password))

    return hits


def check_file_contents(repo_path, files):
    findings = []
    uses_env_variables = False

    for relative_text in files:
        text = read_text_file(repo_path / relative_text)

        if text is None:
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            if INLINE_IGNORE_MARKER in line:
                continue

            if not uses_env_variables and re.search(ENV_USAGE_PATTERN, line):
                uses_env_variables = True

            for check_id, severity, title, secret_text in scan_line_for_secrets(line):
                findings.append(
                    make_finding(
                        check_id,
                        severity,
                        title,
                        relative_text,
                        line_number,
                        mask_secret(secret_text),
                    )
                )

    names = {relative_text.rsplit("/", 1)[-1].lower() for relative_text in files}

    if uses_env_variables and not names.intersection(ENV_EXAMPLE_NAMES):
        findings.append(make_finding("env-example", "info", "No .env.example file"))

    return findings


def check_env_files(files):
    findings = []

    for relative_text in files:
        name = relative_text.rsplit("/", 1)[-1].lower()

        if not re.fullmatch(r"\.env(\..+)?", name) or name in ENV_EXAMPLE_NAMES:
            continue

        # Frameworks such as Next.js commit .env.development/.env.production on purpose.
        if name == ".env" or name.endswith(".local"):
            findings.append(
                make_finding("env-file", "critical", "Environment file is not ignored", relative_text)
            )
        else:
            findings.append(
                make_finding("env-file", "warning", "Environment file will be committed", relative_text)
            )

    return findings


def check_large_files(repo_path, files):
    findings = []

    for relative_text in files:
        try:
            size = (repo_path / relative_text).stat().st_size
        except OSError:
            continue

        size_text = f"{size / (1024 * 1024):.0f} MB"

        if size > LARGE_FILE_LIMIT_BYTES:
            findings.append(
                make_finding("large-file", "critical", "File too large for GitHub", relative_text, detail=size_text)
            )
        elif size > LARGE_FILE_WARNING_BYTES:
            findings.append(
                make_finding("large-file", "warning", "Large file", relative_text, detail=size_text)
            )

    return findings


def strip_sql_comments(sql_text):
    sql_text = re.sub(r"/\*.*?\*/", " ", sql_text, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql_text)


def sql_table_name(raw_name):
    parts = [part.strip('"').lower() for part in raw_name.split(".")]

    if len(parts) == 2 and parts[0] != "public":
        return None

    return parts[-1]


def check_supabase_rls(repo_path, files):
    created_tables = {}
    protected_tables = set()

    for relative_text in files:
        if not relative_text.lower().endswith(".sql") or "supabase/" not in relative_text.lower():
            continue

        text = read_text_file(repo_path / relative_text)

        if text is None:
            continue

        text = strip_sql_comments(text)

        for match in re.finditer(
            r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w\".]+)", text, flags=re.IGNORECASE
        ):
            table_name = sql_table_name(match.group(1))

            if table_name:
                created_tables.setdefault(table_name, relative_text)

        for match in re.finditer(
            r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?([\w\".]+)\s+enable\s+row\s+level\s+security",
            text,
            flags=re.IGNORECASE,
        ):
            table_name = sql_table_name(match.group(1))

            if table_name:
                protected_tables.add(table_name)

    return [
        make_finding("supabase-rls", "warning", "Supabase table without Row Level Security", path, detail=table)
        for table, path in sorted(created_tables.items())
        if table not in protected_tables
    ]


def check_firebase_rules(repo_path, files):
    findings = []

    for relative_text in files:
        name = relative_text.rsplit("/", 1)[-1].lower()

        if name not in ["firestore.rules", "storage.rules", "database.rules.json"]:
            continue

        text = read_text_file(repo_path / relative_text) or ""

        for line_number, line in enumerate(text.splitlines(), start=1):
            code = line.split("//", 1)[0]

            if re.search(r"\ballow\b[^;]*:\s*if\s+true\s*;", code) or re.search(
                r"\"\.(read|write)\"\s*:\s*(true|\"true\")", code
            ):
                findings.append(
                    make_finding(
                        "firebase-rules", "critical", "Firebase rules allow public access", relative_text, line_number
                    )
                )

    return findings


def check_license(repo_path):
    names = {path.name.lower() for path in repo_path.iterdir() if path.is_file()}

    if names.intersection(LICENSE_FILE_NAMES):
        return []

    return [make_finding("license", "warning", "No LICENSE file")]


def check_agent_files(repo_path, files):
    findings = []

    for relative_text in files:
        if relative_text.lower() not in AGENT_FILE_NAMES:
            continue

        text = read_text_file(repo_path / relative_text) or ""
        line_count = len(text.splitlines())

        if line_count > AGENT_FILE_MAX_LINES:
            findings.append(
                make_finding(
                    "agent-file-size", "info", "Agent instruction file is long", relative_text, detail=f"{line_count} lines"
                )
            )

    return findings


def hygiene_findings(repo_path, junk_items):
    findings = [make_finding("junk", "warning", "Junk committed to the repo", item) for item in junk_items]

    for issue in check_gitignore(repo_path):
        prefix = "Missing .gitignore entry: "

        if issue.startswith(prefix):
            findings.append(
                make_finding("gitignore", "warning", "Missing .gitignore entries", detail=issue.removeprefix(prefix))
            )
        else:
            findings.append(make_finding("gitignore", "warning", issue))

    for issue in check_readme(repo_path):
        prefix = "Missing README heading: "

        if issue.startswith(prefix):
            findings.append(
                make_finding("readme-section", "info", "Missing README sections", detail=issue.removeprefix(prefix))
            )
        else:
            findings.append(make_finding("readme", "warning", issue))

    return findings


def build_report(repo_path):
    junk_items, files = scan_tree(repo_path)
    findings = []
    findings += check_file_contents(repo_path, files)
    findings += check_env_files(files)
    findings += check_supabase_rls(repo_path, files)
    findings += check_firebase_rules(repo_path, files)
    findings += check_large_files(repo_path, files)
    findings += hygiene_findings(repo_path, junk_items)
    findings += check_license(repo_path)
    findings += check_agent_files(repo_path, files)

    findings.sort(key=lambda finding: SEVERITIES.index(finding["severity"]))
    counts = {severity: 0 for severity in SEVERITIES}

    for finding in findings:
        counts[finding["severity"]] += 1

    score = max(0, 100 - sum(SEVERITY_PENALTIES[severity] * count for severity, count in counts.items()))

    return {
        "path": str(repo_path),
        "version": __version__,
        "score": score,
        "grade": grade_for_score(score),
        "counts": counts,
        "files_scanned": len(files),
        "findings": findings,
    }


def grade_for_score(score):
    for grade, minimum in [("A", 90), ("B", 80), ("C", 65), ("D", 50)]:
        if score >= minimum:
            return grade

    return "F"


def count_issues(report):
    return len(report["findings"])


def group_findings(findings):
    """Group findings that share a check and title, keeping severity order."""
    groups = {}

    for finding in findings:
        key = (finding["severity"], finding["id"], finding["title"])
        groups.setdefault(key, []).append(finding)

    return groups


def finding_location(finding):
    if not finding["path"]:
        return finding["detail"] or ""

    location = finding["path"]

    if finding["line"]:
        location += f":{finding['line']}"

    if finding["detail"]:
        location += f"  ({finding['detail']})"

    return location


def use_color(stream):
    return stream.isatty() and "NO_COLOR" not in os.environ  # repodx:ignore


def paint(text, color_code, enabled):
    return f"\033[{color_code}m{text}\033[0m" if enabled else text


def format_text(report, color=False):
    counts = report["counts"]
    grade_colors = {"A": "32", "B": "32", "C": "33", "D": "33", "F": "31"}
    severity_colors = {"critical": "31", "warning": "33", "info": "36"}
    lines = [
        "RepoDx report",
        f"Scanned path: {report['path']} ({report['files_scanned']} files)",
        "Score: "
        + paint(f"{report['score']}/100 ({report['grade']})", "1;" + grade_colors[report["grade"]], color),
        f"Found: {counts['critical']} critical, {counts['warning']} warnings, {counts['info']} info",
    ]

    if not report["findings"]:
        lines += ["", paint("No issues found. Safe to push.", "32", color)]
        return "\n".join(lines)

    for (severity, _check_id, title), group in group_findings(report["findings"]).items():
        lines.append("")
        lines.append(paint(f"[{severity.upper()}] {title}", "1;" + severity_colors[severity], color))

        for finding in group:
            location = finding_location(finding)

            if location:
                lines.append(f"  - {location}")

        lines.append(f"  Fix: {group[0]['fix']}")

    return "\n".join(lines)


def format_markdown(report):
    counts = report["counts"]
    lines = [
        f"## RepoDx: {report['score']}/100 ({report['grade']})",
        "",
        f"{counts['critical']} critical, {counts['warning']} warnings, {counts['info']} info "
        f"in {report['files_scanned']} files.",
    ]

    if not report["findings"]:
        return "\n".join(lines + ["", "No issues found."])

    lines += ["", "| Severity | Issue | Where |", "| --- | --- | --- |"]

    for finding in report["findings"]:
        where = finding_location(finding).replace("|", "\\|")
        where_cell = f"`{where}`" if where else ""
        lines.append(f"| {finding['severity']} | {finding['title']} | {where_cell} |")

    lines += ["", "### How to fix", ""]

    for (_severity, _check_id, title), group in group_findings(report["findings"]).items():
        lines.append(f"- **{title}**: {group[0]['fix']}")

    return "\n".join(lines)


def badge_markdown(report):
    colors = {"A": "brightgreen", "B": "green", "C": "yellow", "D": "orange", "F": "red"}
    message = f"{report['grade']} {report['score']}/100".replace(" ", "%20").replace("/", "%2F")
    url = f"https://img.shields.io/badge/repodx-{message}-{colors[report['grade']]}"
    return f"[![repodx]({url})](https://github.com/omerbek/repodx)"


def should_fail(report, fail_on):
    if fail_on == "never":
        return False

    failing = SEVERITIES[: SEVERITIES.index(fail_on) + 1]
    return any(report["counts"][severity] for severity in failing)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="repodx",
        description="Check a project for leaked secrets and repo hygiene problems before you push it.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path to scan. Defaults to the current folder.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format. Defaults to text.",
    )
    parser.add_argument(
        "--json",
        dest="format",
        action="store_const",
        const="json",
        help="Shortcut for --format json.",
    )
    parser.add_argument(
        "--fail-on",
        choices=SEVERITIES + ["never"],
        default="warning",
        help="Exit with code 1 when a finding of this severity or worse exists. Defaults to warning.",
    )
    parser.add_argument(
        "--badge",
        action="store_true",
        help="Print a README badge with your score instead of the report.",
    )
    parser.add_argument("--version", action="version", version=f"repodx {__version__}")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    repo_path = Path(args.path).resolve()

    if not repo_path.exists() or not repo_path.is_dir():
        print(f"Error: path is not a directory: {repo_path}", file=sys.stderr)
        return 2

    report = build_report(repo_path)

    if args.badge:
        print(badge_markdown(report))
    elif args.format == "json":
        print(json.dumps(report, indent=2))
    elif args.format == "markdown":
        print(format_markdown(report))
    else:
        print(format_text(report, color=use_color(sys.stdout)))

    return 1 if should_fail(report, args.fail_on) else 0


def cli():
    raise SystemExit(main())


if __name__ == "__main__":
    cli()
