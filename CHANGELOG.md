# Changelog

## 0.3.1

- Published on PyPI: `pipx install repodx`

## 0.3.0

- Tested against eight large public repositories. Critical false alarms went from 136 to 0; the one remaining critical finding is real.
- Skip documentation placeholders (`...EXAMPLE`, `[YOUR-PASSWORD]`, `xoxb-0000...`, templated hosts) and the local Supabase CLI demo keys.
- Private keys are only reported when a real key body follows the header.
- Secrets and `.env` files in test and example folders are warnings.
- `.env` files that only contain public variables (`NEXT_PUBLIC_`, `VITE_`, ...) are warnings.
- Firebase rules: public writes are critical, public reads are info.
- `.gitignore` expectations follow the project type, and globs such as `.env*` count.
- `dist/` of a JavaScript GitHub Action is not junk.
- README "Quickstart", "Getting started" and "Running locally" sections count as Installation and Usage.
- Each kind of problem counts at most three times toward the score.
- About 3x faster on large repositories.

## 0.2.0

- Secret scanning, Supabase and Firebase checks, `.env` files, large files, LICENSE, `.env.example`, agent files.
- Score and grade, `--json`, `--format markdown`, `--badge`, `--fail-on`.
- `.repodxignore`, `repodx:ignore`, GitHub Action, pre-commit hook, `pyproject.toml`.

## 0.1.0

- Junk files, `.gitignore` and README checks.
