# Support matrix

| Method | Artifact | Notes |
|---|---|---|
| Docker | Docker archive | Load the derived, digest-pinned image and run the same verification used for the official image. |
| Podman | Docker archive | Uses the same image archive and verification steps as Docker. |
| Non-container source | Patched source archive | Run in a separate environment with `uv sync --frozen`; dependencies are not bundled. |
| Existing source checkout | Reviewed `.patch` files | The checkout must match the exact clean commit in `upstream.json`; use the recorded patch order. |
| Official installer unchanged | Official release | Does not contain this project's temporary backports. |
| Runtime monkeypatch | None | Not supported. |
| Unpinned `latest` base | None | Not reproducible and therefore not supported for a backport release. |

The fast container overlay only supports ordinary source-file additions and modifications. Dependency manifests, lockfiles, Docker build files, frontend trees, deletions, and renames require a full rebuild from the matching official source instead of the overlay path.
