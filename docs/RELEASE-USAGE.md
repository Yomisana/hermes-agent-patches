# Hermes Agent @VERSION@ usage guide

This is a temporary backport built from the official NousResearch Hermes Agent `v2026.8.19` source and a digest-pinned official container image. Test it before replacing another installation.

## Choose the download

| Use case | Download |
|---|---|
| Docker or Podman | `@DOCKER_ARCHIVE@` and `SHA256SUMS` |
| Non-container | `@SOURCE_ARCHIVE@` and `SHA256SUMS` |
| Patch an existing clean source checkout | all three `.patch` files, `manifest.json`, `upstream.json`, and `SHA256SUMS` |
| Review provenance | `manifest.json`, `provenance.json`, `upstream.json`, and `upstream-status.json` |

The patch order is significant:

1. `91330-profile-write-boundary-pr-91381.patch`
2. `76932-profile-session-isolation-backport.patch`
3. `88897-profile-database-routing-backport.patch`

## Verify downloads

Linux or macOS:

```bash
sha256sum -c SHA256SUMS
```

Windows PowerShell, for example:

```powershell
Get-FileHash .\@DOCKER_ARCHIVE@ -Algorithm SHA256
Get-Content .\SHA256SUMS
```

Do not use a file whose hash does not match.

## Container usage

Docker:

```bash
docker load -i @DOCKER_ARCHIVE@
docker image inspect hermes-agent:@VERSION@
docker run --rm hermes-agent:@VERSION@ --version
```

Podman:

```bash
podman load -i @DOCKER_ARCHIVE@
podman image inspect hermes-agent:@VERSION@
podman run --rm hermes-agent:@VERSION@ --version
```

When creating a Hermes container, use the same ports, environment variables, and `/opt/data` volume that you would use with the official image, but select `hermes-agent:@VERSION@`. Keep credentials and endpoint configuration outside the image.

To roll back, stop the patched container and recreate it from the desired official image digest. Do not reverse patches inside a running container.

## Non-container usage: patched source archive

The source archive is already patched:

```bash
tar -xzf @SOURCE_ARCHIVE@
cd hermes-agent
uv sync --frozen
uv run hermes --version
uv run hermes
```

Use a separate directory or environment instead of overwriting another Hermes installation. The archive contains source code, not every Python dependency. If dependencies are unavailable, use the container archive instead. Hermes upstream prevents wheel builds, so this Release does not include an unofficial wheel.

To roll back, stop using the extracted directory and return to a clean official installation. Preserve user data unless you intentionally want to remove it.

## Non-container usage: apply patches to source

The checkout must be clean and its `HEAD` must equal the `commitSha` in `upstream.json`:

```bash
git rev-parse HEAD
git status --short
git am --3way \
  91330-profile-write-boundary-pr-91381.patch \
  76932-profile-session-isolation-backport.patch \
  88897-profile-database-routing-backport.patch
```

If application fails:

```bash
git am --abort
```

Alternatively, clone this patch repository and use the guarded commands:

```bash
python scripts/patchctl.py check /path/to/hermes-agent
python scripts/patchctl.py apply /path/to/hermes-agent
python scripts/patchctl.py reverse /path/to/hermes-agent
```

`reverse` only accepts commits recorded by the preceding `apply`, with no later change to `HEAD`.

## Verification scope

Confirm that the CLI or image starts, existing configuration can be read, profiles cannot read each other's sessions, an isolated desktop cannot operate on another profile or machine-wide profile endpoints, and `profile=default` remains routed to the launch profile when scoped.

`manifest.json` describes the enabled fixes. `upstream-status.json` is a build-time upstream snapshot, not a live status report.
