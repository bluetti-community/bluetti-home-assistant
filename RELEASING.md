# Releasing

## Version numbers

Semantic versioning: `MAJOR.MINOR.PATCH`.

- **MAJOR** — a change that breaks an existing setup: an entity that disappears
  or is renamed, a config entry that has to be re-created, a minimum Home
  Assistant version that rises.
- **MINOR** — new entities, a new option, a new part of the cloud API used.
- **PATCH** — a fix that changes nothing else.

A build put in front of one account or one region before everyone else is a
prerelease, `MAJOR.MINOR.PATCH.bN` — the dot before the phase is what this
repository's release workflow accepts.

The tag is the version, and the release workflow writes it into
`custom_components/bluetti/manifest.json` itself: that version travels to
BLUETTI's servers as `x-app-ver`, so it is never edited by hand.

## Release notes

Written by hand, from the merged pull requests. GitHub's "Generate release
notes" button gives the skeleton (`.github/release.yml` sets the categories);
the text that ships says what changed for the person running it.

```markdown
## ✨ New Features
- **Short subject**: what it does, and what it was confirmed against. (#123)

## 🐛 Bug Fixes
- **Short subject**: the symptom, then the cause in one clause. (#124)

**Full Changelog**: https://github.com/bluetti-community/bluetti-home-assistant/compare/<previous>...<this>
```

Rules that matter more than the layout:

- One line per change, leading with the subject in bold, ending with its pull
  request number.
- A claim about an account, a region or a device names what it was confirmed
  on, or says it is unconfirmed.
- No release is shipped until its GitHub release exists: the tag alone does not
  reach HACS, and the zip asset is built by the release workflow.
