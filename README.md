# Hermes Agent Backport Patches

This repository packages reviewed fixes from [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) as reproducible, temporary backports.

It is not a Hermes Agent fork or an official NousResearch release. Upstream issues, pull requests, commits, and authors remain attributed to their original contributors. This repository records the selected fixes, pins the upstream source and container image, verifies the patch set, and produces test artifacts.

## Available backports

- Issue #91330: PR #91381 was selected over the narrower overlapping PR #91345.
- Issue #76932: a minimal `v2026.8.19` adaptation based on PR #77125 was selected after comparing PRs #48652, #71037, #77125, and #78423.
- Issue #88897: a minimal `v2026.8.19` adaptation of PR #89173 was selected without its unrelated formatting changes.

An open upstream PR is a candidate workaround, not proof that the fix has been accepted or released upstream. See [upstream provenance](docs/UPSTREAM-PROVENANCE.md) and [`patches/manifest.json`](patches/manifest.json) for the recorded authorship, source SHAs, and selection notes.

## Use the Release artifacts

See the [Release usage guide](docs/RELEASE-USAGE.md) for the exact downloads and commands.

- Non-container: use the patched source archive, or apply the three patch files to the exact clean upstream commit recorded in `upstream.json`.
- Container: load the supplied Docker archive with Docker or Podman. The derived image is built from the official image pinned by digest.

The official `install.sh` installation does not automatically receive these backports. Hermes upstream also prevents wheel distribution, so this project does not publish an unofficial wheel.

## Patch tool

Validate the reviewed manifest:

```bash
python scripts/patchctl.py validate
```

Check and apply the enabled patch series to a clean checkout at the pinned upstream commit:

```bash
python scripts/patchctl.py check /path/to/hermes-agent
python scripts/patchctl.py apply /path/to/hermes-agent
```

Create auditable revert commits for a checkout that has not changed since `patchctl.py apply`:

```bash
python scripts/patchctl.py reverse /path/to/hermes-agent
```

For a container rollback, replace the patched container with a clean image based on the desired official digest. Do not modify a running container or apply a runtime monkeypatch.

## Maintenance rules

1. Releases pin a full upstream source SHA and official container digest; `latest` is not a reproducible base.
2. Upstream monitoring reports changes but never enables a patch automatically.
3. Overlapping candidate PRs are reviewed and one implementation is selected; they are not stacked automatically.
4. Enabled patches record the selected PR, full head SHA, patch checksum, and attribution.
5. `git am --3way` preserves upstream authorship. Version-specific adaptations are separate attributed commits.
6. A conflict, unknown base, dirty checkout, or checksum mismatch stops the operation.
7. A backport is retired only after an official release contains the fix and the regression tests pass without the patch.

Release versions use `v<upstream-tag>-backport.<revision>`, for example `v2026.8.19-backport.1`.
