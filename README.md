# RepoDx

[![tests](https://github.com/omerbek/repodx/actions/workflows/tests.yml/badge.svg)](https://github.com/omerbek/repodx/actions/workflows/tests.yml)
[![repodx](https://img.shields.io/badge/repodx-A%20100%2F100-brightgreen)](https://github.com/omerbek/repodx)

**Check your AI-built project before you push it.**
One command, zero dependencies, and nothing leaves your machine.

Coding agents such as Cursor, Claude Code, Lovable, Bolt and Replit ship apps fast.
They also paste API keys into source files, commit `.env` files, create
Supabase tables without Row Level Security and leave Firebase rules wide open.
In 2025, public GitHub commits leaked about 28.6 million new secrets, and leaked
AI-service keys grew 81% in one year
([GitGuardian, State of Secrets Sprawl 2026](https://blog.gitguardian.com/the-state-of-secrets-sprawl-2026/)).
Bots find a leaked key within minutes.

RepoDx scans your project folder, gives it a score, and tells you in plain
language how to fix each problem.

![RepoDx scanning a sample project](docs/demo.svg)

## Installation

Install from PyPI with an isolated tool manager:

```bash
pipx install repodx
# or
uv tool install repodx
```

Run it once without installing anything (Python 3.9+ is the only requirement):

```bash
curl -sSL https://github.com/omerbek/repodx/releases/latest/download/repodx.py | python3 - .
```

Install the tagged GitHub version directly:

```bash
pipx install git+https://github.com/omerbek/repodx@v0.3.0
# or
uv tool install git+https://github.com/omerbek/repodx@v0.3.0
```

On Windows, you can also download `repodx.py` and run `python repodx.py .`

## Usage

```bash
repodx                    # scan the current folder
repodx path/to/project    # scan another folder
repodx --json             # machine-readable output
repodx --format markdown  # report for PR comments or CI summaries
repodx --badge            # print a README badge with your score
repodx --fail-on critical # only fail on critical findings (default: warning)
```

Exit codes: `0` means nothing at or above `--fail-on` was found, `1` means
something was found, and `2` means the path is not a folder.

### GitHub Action

```yaml
# .github/workflows/repodx.yml
name: repodx
on: [push, pull_request]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: omerbek/repodx@v0.3.0
        with:
          fail-on: warning # critical, warning, info or never
```

The action writes the report to the job summary and fails the job when it finds
problems.

### pre-commit hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/omerbek/repodx
    rev: v0.3.0
    hooks:
      - id: repodx
```

### Badge

Run `repodx --badge` and paste the output into your README:

```markdown
[![repodx](https://img.shields.io/badge/repodx-A%2094%2F100-brightgreen)](https://github.com/omerbek/repodx)
```

## What it checks

| Severity | Check |
| --- | --- |
| critical | API keys and tokens: OpenAI, Anthropic, AWS, GitHub, Stripe, Supabase secret keys, Slack, Hugging Face, Groq, SendGrid, Telegram bots, private keys |
| critical | Supabase `service_role` JWTs (the JWT is decoded to check its role; public `anon` keys are not reported) |
| critical | Database URLs with a real password (`postgres://`, `mysql://`, `mongodb+srv://`, `redis://` ...), except local hosts and placeholders |
| critical | `.env` and `.env.local` files that are not ignored (other variants such as `.env.production`, and files with only `NEXT_PUBLIC_`/`VITE_` variables, are warnings) |
| critical | Firebase `firestore.rules`, `storage.rules` or `database.rules.json` that let anyone write (public reads are reported as info) |
| critical / warning | Files over 100 MB (GitHub rejects them) and over 50 MB |
| warning | Google API keys (public if they are Firebase web keys, secret if they are Gemini, Maps or Cloud keys) |
| warning | Supabase migrations that create tables without `enable row level security` |
| warning | Committed junk: `node_modules/`, `__pycache__/`, virtualenvs, `dist/`, `.next/`, `coverage/`, `.log`, `.tmp`, `.DS_Store` |
| warning | Missing `.gitignore` or missing `.env`, `node_modules/` and `__pycache__/` entries |
| warning | Missing README or LICENSE |
| info | Code reads environment variables but there is no `.env.example` |
| info | README without Installation or Usage sections (English and Turkish headings are recognized) |
| info | `AGENTS.md` or `CLAUDE.md` over 300 lines (coding agents tend to ignore long instruction files) |

To keep false alarms rare, RepoDx:

- skips values that look like documentation placeholders (`AKIAIOSFODNN7EXAMPLE`,
  `[YOUR-PASSWORD]`, `xoxb-0000...`, `-----BEGIN PRIVATE KEY-----\n...`) and the
  public demo keys of the local Supabase CLI
- reports secrets and `.env` files in test and example folders as warnings, not
  critical
- only expects `node_modules/` in `.gitignore` when there is a `package.json`,
  and `__pycache__/` when there are Python files

RepoDx reads your `.gitignore`, including `!` re-include rules. Files that Git
would not commit are not reported, and ignored folders are not scanned. Found
secrets are masked in the output (`sk-pro...l2`).

The score starts at 100. Each critical finding subtracts 25, each warning 8
and each info 2, and each kind of problem counts at most three times.
Grades: A ≥ 90, B ≥ 80, C ≥ 65, D ≥ 50, F below 50.

## Tested on real projects

Before each release, RepoDx is run on large public repositories to catch false
alarms. Results for 0.3.0:

| Repository | Files | Time | Critical | Result |
| --- | ---: | ---: | ---: | --- |
| vercel/ai-chatbot | 181 | 0.1 s | 0 | 100 (A) |
| langchain-ai/langchain | 3,165 | 2.3 s | 0 | 98 (A) |
| fastapi/fastapi | 3,139 | 1.6 s | 0 | 90 (A) |
| openai/openai-cookbook | 3,601 | 3.1 s | 0 | four data files over 50 MB |
| psf/requests | 128 | 0.2 s | 0 | test certificates' private keys (warnings) |
| supabase/supabase | 17,564 | 6.9 s | 0 | example tables without RLS, example `.env` files |
| vercel/next.js | 32,215 | 7.5 s | 0 | example `.env` files, test certificates |
| firebase/quickstart-js | 436 | 0.3 s | 1 | `database.rules.json` has `".write": true` (real) |

The first version of these checks raised 136 critical alarms on the same
repositories. Almost all of them were documentation placeholders and test
fixtures, and the rules above were added to filter them out.

## Silencing false positives

- Add `repodx:ignore` in a comment on the line to skip that line.
- Add a `.repodxignore` file (gitignore syntax) to skip whole paths, such as
  test fixtures:

  ```gitignore
  tests/fixtures/
  docs/examples/*.md
  ```

## What RepoDx does not do

- It scans the files in your folder, not your Git history. If a key was ever
  pushed, rotate it: deleting the file does not remove it from history. For
  history scans, use [Gitleaks](https://github.com/gitleaks/gitleaks) or
  [TruffleHog](https://github.com/trufflesecurity/trufflehog).
- It does not connect to your live Supabase or Firebase project. The RLS and
  rules checks only read the files in your repo.
- It is a fast first check, not a full security audit.

## Contributing

Found a false alarm or a missed secret? [Open an issue](https://github.com/omerbek/repodx/issues/new/choose)
with the line (with the secret replaced). See [CONTRIBUTING.md](CONTRIBUTING.md).

## Development

RepoDx is a single Python file with no dependencies, so it is easy to read and
extend. Each check is a small function in `repodx.py` that returns findings.

The `sample_repo/` folder is intentionally broken, and every credential in it
is fake. It is used by the tests and by the example above.

Run the test suite:

```bash
python3 -m unittest discover
```

Adding a check:

1. Write a function that returns `make_finding(...)` results.
2. Add its fix text to `FIXES`.
3. Call it from `build_report`.
4. Add a test in `tests/test_repodx.py`.
