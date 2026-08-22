# Project Notes

Guidance for any AI assistant (Claude or otherwise) working in this repo, distilled from what
actually mattered across this project's PR series (#126-#132).

## Architecture: this integration has no static per-model data

Every entity is derived dynamically from whatever `fn_code`/`fn_type`/`sensor_info` the BLUETTI
cloud API returns for a device's `stateList` (see `sensor.py`, `switch.py`, `select.py`). There is
no local per-model register or protocol map. This means:

- A "missing sensor" report almost never means a mapping bug in this repo - it usually means the
  cloud simply isn't sending that field for that model. Don't guess a fix; ask for a diagnostics
  dump first (`doc/diagnostics/` has reference samples; `CONTRIBUTING.md` has the download steps).
- Do not fabricate device-specific behavior, register values, or protocol details that aren't
  backed by an actual diagnostics dump or a real device you can test against.

## Verify, don't guess

- Before pinning a GitHub Action by SHA, resolve the tag through the GitHub API
  (`gh api repos/<owner>/<repo>/git/refs/tags/<tag>`) rather than writing one from memory. A
  fabricated SHA either fails outright or silently pins the wrong commit.
- Before relying on Home Assistant internals (a helper's exact signature, a schema's key order,
  an entity base class's default behavior), check the installed `homeassistant` package's actual
  source rather than assuming - `python -c "import inspect; ..."` against a real venv is cheap and
  has caught real bugs in this project.

## Before committing

- Run the full test suite with coverage enforced: `scripts/test` (100% line coverage is a hard
  requirement here, not a suggestion - see `.github/workflows/tests.yml`).
- Run `scripts/lint` (ruff) and make sure it's clean.
- Clean up any local venvs/caches created for testing before staging changes.

## Keep pull requests focused

This project's single largest PR (#124) had to be retroactively split into seven smaller ones
after review feedback, at real cost. Prefer several small, single-topic PRs over one large one -
see `CONTRIBUTING.md`.

## Commit attribution

Commits in this repo include `Co-Authored-By: Claude <...>` when AI-assisted. This is a deliberate
choice, not an oversight - keep it.
