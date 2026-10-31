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

Successful pull requests within the same repository publish an experimental GitHub prerelease after both Host checks jobs pass.
External fork pull requests cannot publish releases.
Find the download in the repository's Releases page or the publishing job's summary.

The fixed tag is `pr-<number>-<tested-merge-commit-prefix>`.
The release records the PR head and tested merge commit.
It attaches the existing CI packages without rebuilding them, verifies their checksums, and does not replace earlier release assets on reruns.
These releases are not marked latest.
They retain the app's content version and are test candidates, not store updates.
The release notes explicitly state that console validation remains pending.

Download `PPSA99996.zip` and `SHA256SUMS` for installation.
Download `nuvio-ps5-<version>.zip` for source and build receipts.
CI artifacts remain available for 14 days. GitHub Release assets do not use that expiration.
Asset URLs use the current repository, not the upstream repository.

## Cut a release

1. Raise `VERSION` and the `contentVersion` in the build template.
2. Run `make check`.
3. Build the candidate with `make build` if native code changed.
4. Test the candidate on the console and record the result in
   [Validation](VALIDATION.md).
5. Commit the source and the documentation.
6. Push the commit.

The release workflow builds on macOS when you push a version tag. It runs the
host checks, builds the native title and helpers, packages the artifacts, and
creates a draft GitHub release with the assets below.
Download the draft assets and test those exact files on the console.
Publish the draft after recording their hashes and results in Validation.

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
| `nuvio-ps5-<version>.zip` | The complete package: app, development helpers, UI source and receipts. |
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
