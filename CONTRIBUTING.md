# Contributing to RepoDx

Thanks for helping! RepoDx stays small on purpose: one Python file, no
dependencies, and checks that a beginner can read.

## Reporting a false alarm or a missed secret

Open an issue with:

- the RepoDx version (`repodx --version`)
- the finding title and the file type (for example "OpenAI API key in a `.ts` file")
- the line that caused it, **with the secret replaced by fake characters of the same shape**

Never paste a real key into an issue. If you did, rotate the key.

## Adding a check

1. Write a small function in `repodx.py` that returns `make_finding(...)` results.
2. Add a plain-language fix to `FIXES`. Say what to do, not only what is wrong.
3. Call it from `build_report`.
4. Add tests in `tests/test_repodx.py`. Build fake keys at runtime with `fake(...)`
   so no literal secret is committed.
5. Run it on a few real repositories and check that it does not raise false alarms.

Pick severities carefully:

- **critical**: someone can use it against you right now (a live key, a public write rule)
- **warning**: likely a mistake that should be fixed before sharing
- **info**: a suggestion

## Running tests

```bash
python3 -m unittest discover
python3 repodx.py .   # the repo must keep scoring 100
```
