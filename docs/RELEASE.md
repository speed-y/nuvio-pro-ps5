# Release

## Versioning

`VERSION` holds the release version, for example `0.1.0-alpha.1`. The title
records its own content version in `sce_sys/param.json` as `contentVersion`, for
example `01.000.001`. The build copies that file's identity and content version
into the generated title. Raise the content version in every release so an
installed console sees the update, and so the store catalog can read it from the
tag.

The PS5 Homebrew Store catalog accepts pre-release tags. Use a fixed tag such as
`v0.1.0-alpha.1`, never a moving tag such as `latest` or `nightly`.

## PR test releases

Pull requests within the same repository publish an experimental GitHub prerelease after host checks and a new native build pass.
External fork pull requests cannot publish releases.
Find the download in the repository's Releases page or the publishing job's summary.

Checks run for pull requests and pushes to `main`, without duplicate feature-branch push runs.
New commits cancel superseded check runs. All commits still run host, documentation and privacy checks.
Documentation-only changes skip native compilation and publication.
In a mixed PR, documentation updates reuse a successful verification record for identical non-Markdown source, when available.
A missing record requires a build. Cancelling an unfinished build cannot create that record.

The fixed tag is `pr-<number>-<tested-merge-commit-prefix>`.
The release records the PR head and tested merge commit.
It attaches the existing CI packages without rebuilding them, verifies their checksums, and does not replace earlier release assets on reruns.
These releases are not marked latest.
They retain the app's content version and are test candidates, not store updates.
The release notes explicitly state that console validation remains pending.

Download `PPSA99996.zip` and `SHA256SUMS` for installation.
Download `nuvio-pro-ps5-<version>.zip` for source and build receipts.
CI artifacts remain available for 14 days. GitHub Release assets do not use that expiration.
Asset URLs use the current repository, not the upstream repository.

## Cut a release

1. Raise `VERSION` and `contentVersion` in `sce_sys/param.json` on your branch before merging to `main`.
2. Run `make check`.
3. Build the candidate with `make build` if native code changed.
4. Test the candidate on the console and record the result in
   [Validation](VALIDATION.md).
5. Commit the source and the documentation, then merge the pull request into `main`.

Merging or pushing to `main` triggers the Release workflow automatically.
The `verify-version` job compares `VERSION` and `contentVersion` against the latest `v*` tag and the previous `main` commit.
If either version does not advance or the tag already exists, the release build fails before packaging.

Pull request checks run `scripts/check_release_version.py` as a non-blocking warning when `VERSION` or `contentVersion` still matches `main`.
After `verify-version` passes, the workflow calls `build.yml` to run host checks, compile the title and helpers, and package `PPSA99996.zip`, `nuvio-pro-ps5-<version>.zip`, and `SHA256SUMS`.
The publishing job verifies `SHA256SUMS`, generates categorized release notes from `.github/release.yml` against the previous `v*` tag, creates tag `v<VERSION>`, and publishes the release.
Versions with a prerelease suffix such as `-alpha.3` publish as prereleases, while stable versions mark the release latest.
Reruns preserve an existing release and its assets. Release runs do not cancel an active publication.

Pushing a matching `v*` tag also triggers the Release workflow.
Manual runs of the Release workflow upload downloadable artifacts without creating a GitHub release, even on a tag.
Select the optional `macos` input to check macOS build compatibility alongside Linux.
Only Linux packages enter versioned releases. Both platforms use the shared build workflow, with separate caches and artifact names.
Artifacts use `nuvio-<OS>-<architecture>-<commit>` names and expire after 14 days.

```sh
git tag v0.1.0-alpha.1
git push origin v0.1.0-alpha.1
```

A documentation change needs no native rebuild. A new native build can carry
different bytes because the build records the build date and time.

## Package locally

Run the package command from a Git checkout:

```sh
make release
```

| Artifact | Contents |
|---|---|
| `PPSA99996.zip` | The `<TITLEID>/` app folder, including `webui/`. This is the store artifact. |
| `nuvio-pro-ps5-<version>.zip` | The complete package: app, development helpers, UI source and receipts. |
| `SHA256SUMS` | Hashes for the release assets. |

`PPSA99996.zip` unpacks to a single `PPSA99996/` folder. Users copy that folder to
`/data/homebrew/` and open Nuvio after the current boot's jailbreak starts ShadowMount and the ELF loader. The complete package keeps
the source, the browser UI and the build helpers for a scripted install.

`make release` recreates `release/` and writes `release/ASSETS` with the exact
asset paths. The release workflow uploads those paths, so a stale local file
cannot reach a release.

The package script checks the native file hashes and the helper ELF hashes. It
accepts only the expected helper inventory. The receipt covers the native files
and the helpers. The archive manifest covers the packaged UI and source files.

## Store listing

The [PS5 Homebrew Store catalog](https://github.com/darkxex/ps5-homebrew-catalog)
lists native PS5 homebrew by title ID and pins release assets by SHA-256.
Its existing `apps/PPSA99997.json` belongs to Bilawal Riaz's upstream port, not this fork.
This fork selects `PPSA99996` locally. It has no submitted reservation or approved catalog listing.
Check availability again before requesting a reservation through a catalog pull request.
The catalog's derivative-app policy also requires substantial differences and a distinct name.

The catalog needs:

- A native title with `eboot.bin` and `sce_sys/param.json`, which this project
  builds.
- A public GitHub release with the `PPSA99996.zip` asset attached.
- An icon at a stable HTTPS URL, pinned to a tag. Use `assets/icon.png`.
- The SHA-256 of the release asset.

The daily catalog job follows new releases, so keep the asset name stable and
raise `contentVersion` each time. Submit an update only when the release changes
the listing fields.

## Startup helper

The single-install store artifact includes the promotion ELF inside eboot.bin.
The title sends it to the loopback loader and verifies its response before binding.
Development and recovery helpers stay in the complete source package.

## Distribution rules

1. Record the validation result for the exact candidate.
2. Keep complete corresponding sources for the GPL components you distribute.
   The source directory holds this integration, not every upstream archive.
3. Keep upstream notices and licences with the build.
4. Check the archive for account identifiers, signed URLs and private
   configuration.
5. Keep `/data/nuvio` in any upgrade procedure.

## Announce the release

Describe the tested build and its remaining limits. Credit Bilawal Riaz, NuvioMedia and the EVO contributors.
Use real console footage for hardware demonstrations, and keep QR codes, private settings and stream URLs out of public captures.
