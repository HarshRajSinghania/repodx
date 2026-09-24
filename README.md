# RepoDx

RepoDx is a tiny command-line repository hygiene checker.

It scans a local folder and reports a few common cleanup issues:

- temporary files such as `.tmp` and `.log`
- Python cache folders such as `__pycache__/`
- Python virtual environments (`.venv/`, `venv/`, `env/` folders that
  contain a `pyvenv.cfg`)
- `.DS_Store`
- `node_modules/`
- missing or incomplete `.gitignore`
- missing README installation and usage sections (`README.md`, `README.rst`,
  `README.txt` or `README`, in any letter case)

Files and folders that your `.gitignore` already ignores are not reported.
Junk folders are reported once and are not scanned inside, so large
`node_modules/` folders do not slow the scan down.

RepoDx is intentionally small. It does not try to compete with larger audit
tools that run dozens or hundreds of checks. The goal is a fast, readable
starter tool that can be understood by a beginner.

## Installation

Clone the repository and run it with Python:

```powershell
git clone https://github.com/omerbek/repodx.git
cd repodx
python repodx.py .
```

On macOS or Linux:

```bash
git clone https://github.com/omerbek/repodx.git
cd repodx
python3 repodx.py .
```

RepoDx uses only the Python standard library. No package installation is
required.

## Usage

Scan the current folder:

```powershell
python repodx.py .
```

On macOS or Linux:

```bash
python3 repodx.py .
```

Scan another folder:

```powershell
python repodx.py C:\path\to\project
```

On macOS or Linux:

```bash
python3 repodx.py /path/to/project
```

Example output:

```text
RepoDx report
Scanned path: C:\Users\omer\Desktop\githubprojem\sample_repo
Issues found: 8

Junk files
  - __pycache__/
  - debug.log
  - node_modules/

.gitignore
  - Missing .gitignore entry: __pycache__/
  - Missing .gitignore entry: .env
  - Missing .gitignore entry: node_modules/

README
  - Missing README heading: Installation
  - Missing README heading: Usage
```

## Why This Exists

Many AI-assisted projects are created quickly, but their repositories often
keep generated files, local logs, or incomplete documentation. RepoDx gives a
small first-pass report before a project is shared.

## What RepoDx Does Not Do

RepoDx v0.1 does not scan for secrets or API keys. Mature tools such as
Gitleaks and TruffleHog already handle that job better. A future version may
call Gitleaks if it is installed.

RepoDx v0.1 also does not analyze unused dependencies. That problem is easy to
get wrong and is outside the first release.

## Development

The `sample_repo/` folder is intentionally broken. It is used by tests and by
the example report above. Its `.gitignore` ignores `*.tmp`, so `cache.tmp` is
not reported.

Run the test suite:

```powershell
python -m unittest discover
```

On macOS or Linux:

```bash
python3 -m unittest discover
```
