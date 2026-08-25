# Contribution guidelines

Contributing to this project should be as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing a new feature or new device support

## Getting a working dev environment

The fastest way is via the included Dev Container (`.devcontainer.json`) - open this repo in
[VS Code](https://code.visualstudio.com/docs/devcontainers/containers) or a
[GitHub Codespace](https://github.com/features/codespaces) and it sets itself up automatically.

Without a Dev Container, from a Python 3.13 environment:

```bash
scripts/setup      # install runtime + test dependencies
scripts/test       # run the full test suite (100% line coverage is enforced)
scripts/lint       # run ruff, auto-fixing what it safely can
scripts/develop     # launch a real local Home Assistant instance with this
                    # integration mounted, to test interactively
```

## GitHub is used for everything

GitHub is used to host code, track issues and feature requests, and review pull requests.

1. Fork the repo and create your branch from `main`.
2. Make sure `scripts/test` and `scripts/lint` both pass.
3. If you changed user-facing behavior, update `README.md` and add an entry to
   `doc/CHANGELOG.md`.
4. Keep pull requests focused on one thing. A large PR mixing several unrelated changes is much
   harder to review than several small ones - if in doubt, split it up.
5. Open the pull request!

## Reporting bugs

Please use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml) - it's short, but the
device model and a diagnostics dump (**Settings -> Devices & services -> BLUETTI -> Download
diagnostics**) are usually what actually resolves a report, especially for anything about
missing or incorrect sensor/control values.

## Any contributions you make will be under the MIT License

By contributing, you agree that your contributions will be licensed under this project's
[MIT License](LICENSE).
