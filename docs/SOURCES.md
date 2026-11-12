# Sources

## Pinned build inputs

`deps.lock` records download URLs, archive hashes, retrieval dates and license
notes. The builder checks each hash before it extracts the archive. The hashes
identify locally recorded downloads and are not maintainer signatures.

| Input | Fixed identity | Use |
|---|---|---|
| [Nuvio TV](https://github.com/NuvioMedia/NuvioTVSmart/tree/ec5e15c050c7ac98ede4e201a97bc4f93b96420e) | `ec5e15c050c7ac98ede4e201a97bc4f93b96420e`, version 1.4.0 | Browser UI and official branding |
| [EVO Player](https://github.com/sainsaji/EVO-PLAYER-PS5/tree/f6e43e6561796630673f1e20eb1eb67d6428514c) | `f6e43e6561796630673f1e20eb1eb67d6428514c`, v0.13.5 | Native title, bridge, decoder and runtime source |
| [Unofficial Stremio PS5 port](https://github.com/Sp9nky/unofficial-stremio-ps5-port/tree/a4b12fb515a3044f073f4befba0dd90d8244eddd) | `a4b12fb515a3044f073f4befba0dd90d8244eddd` | Read-only comparison of sandbox networking changes |
| [PS5 payload SDK](https://github.com/ps5-payload-dev/sdk/releases/tag/v0.43) | v0.43 | Headers, wrappers and payload link inputs |
| [pacbrew target libraries](https://github.com/ps5-payload-dev/pacbrew-repo/releases/tag/v0.39) | v0.39 | Target libraries only |
| [FFmpeg](https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz) | 7.1.1 | Target libav* libraries. The build compiles this source and installs it over the sysroot copy |
| [ps5-homebrew-ui](https://github.com/sainsaji/ps5-homebrew-ui/tree/47f4b9868c33264716b2e92922b0d2c9d0f2ab0f) | `47f4b9868c33264716b2e92922b0d2c9d0f2ab0f` | EVO v0.13.5's UI submodule. The build installs this pinned tree into `third_party/` |
| [Official Nuvio TV package](https://github.com/NuvioMedia/NuvioTVSmart/releases/tag/1.4.0) | Tizen 1.4.0 | Selected public browser login configuration |
| [klogsrv](https://github.com/ps5-payload-dev/klogsrv/releases/tag/v0.9) | v0.9 | Optional diagnostics used in the console session |

The native build takes the SDK from v0.43 and does not use the older host
toolchain from pacbrew. The pacbrew selection supplies only the target homebrew
library prefix. The dav1d archive is absent from that selection, and the adapter
omits the unused link input. The build compiles the FFmpeg 7.1.1 source with
EVO's minimal configuration and installs it over the sysroot copy, replacing
the pacbrew libav* libraries. The build omits libdav1d, so software AV1
remains unsupported. The GPL-3.0 `ps5-homebrew-ui` kit unpacks under
`third_party/` from its own pinned archive during the build.

### SDK firmware checks

[SOURCE-VERIFIED] SDK v0.43's source tag resolves to `d9c9519116944a7f1c22d262012c53b80b3520b7`.
These files explain firmware initialization in the unchanged, checksum-pinned SDK input:

| Reference | Locally recorded SHA-256 |
|---|---|
| [`crt/kernel.c`](https://github.com/ps5-payload-dev/sdk/blob/d9c9519116944a7f1c22d262012c53b80b3520b7/crt/kernel.c) | `16ca32ffc36309f2caa768d2f4e565f8d31186d7f8625de83bf3f1869e0c81c0` |
| [`crt/crt.c`](https://github.com/ps5-payload-dev/sdk/blob/d9c9519116944a7f1c22d262012c53b80b3520b7/crt/crt.c) | `f0c9e81e740b6beeda3dd4a62e22751603b310b258b7bb7c0875a4cbdcaa212e` |

Inspection date: 2026-10-30. These are reference files, not new build inputs.
`__kernel_init` switches on recognized firmware and returns `-ENOSYS` for an unknown version.
`__crt_start` requires successful initialization before it calls the payload's `main`.
Nuvio delegates firmware selection to that runtime instead of copying its version table or adding offsets.
SDK recognition does not establish console compatibility of Nuvio, the browser or the resident support stack.

The original BlackBearReloaded UI repository returned HTTP404 on 2026-10-30.
Earlier builds used the Phononenom mirror at `4bd942579dd981b3df9c740438489ca6a614ddc0`, with the original archive checksum.
The v0.13.5 migration uses EVO's newer recorded submodule revision from sainsaji's fork.
`deps.lock` records both new archive checksums. Attribution and license requirements remain unchanged.

## Source attribution

Project code and patches use GPL-3.0-or-later unless a file states otherwise.
NuvioMedia owns the upstream Nuvio code and branding. The EVO contributors own
their native implementation and boilerplate. The SDK FreeBSD headers and target
libraries carry their own license terms. Keep those terms when you distribute a
build.

`vendor/control.c` comes from the development workspace's Aurora control helper.
Its header credits the launch ABI source and the ShadowMount API references. The
builder changes its title and labels to Nuvio before it compiles the file. The
retained SHA-256 sources keep their original notices. The runtime comes from
independently authored source inside the pinned EVO input.

The writing checks copy the MIT-licensed STE linter at the revision below. Its
license stays in `vendor/ste-lint/LICENSE`.

The Stremio source pin is a comparison reference. Nuvio does not copy its
`console_curl.c` or `posix_fixes.c` code.

| Writing reference | Revision |
|---|---|
| [ASD-STE100 skill](https://github.com/danyuchn/asd-ste100-skill/tree/7d4a135a199a5d7447c4886bcd7ffe742a627bc9) | `7d4a135a199a5d7447c4886bcd7ffe742a627bc9` |
| [Humanizer](https://github.com/blader/humanizer/tree/225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8) | `225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8` |

Writing reference retrieval date: 2026-10-01. See [Writing](WRITING.md) for their
scope and limits.

## Distribution

The [PS5 Homebrew Store catalog](https://github.com/blackbearreloaded/ps5-homebrew-catalog)
pins one release asset per title. [Release](RELEASE.md) describes the store
record.

## Signing implementation reference

[SOURCE-VERIFIED] Retrieved on 2026-10-09:
[kstuff FSELF authentication handling](https://github.com/EchoStretch/kstuff/blob/d44a25400ecfab7e31afe9eb2c7c7c99770e8f56/ps5-kstuff/uelf/fself.c).
`is_header_fself` reads the embedded 136-byte authentication record.
`try_handle_fself_trap` uses it when present, otherwise selecting a default profile.
This is an inspected reference revision, not the console's resident build identity.

The experimental signing profile comes from `samples/install_app/Makefile` in
the checksum-pinned SDK v0.43 archive. The port uses no kstuff source code.

## Hardware source

[Validation](VALIDATION.md) records the portable console evidence. The original
session record stays in the private development workspace. Raw console logs and
private settings are not publication inputs. Use filtered excerpts with exact
artifact identities.

## Home-screen media

The owner supplied the cinema-ribbon background generated with Gemini and the
40-second `nuvio_warm_glass_cinematic_v6.wav` generated with ChatGPT.
These are owner-supplied media, not extracted game assets or runtime code.
AI generation does not establish third-party rights clearance.
Public redistribution remains subject to the applicable generation terms and input rights.

`assets/launch.png` holds the resized 3840x2160 background.
`assets/launch.dds` holds its BC7 DX10 conversion without mipmaps.
The build copies each image to both selection and launch filenames.
`assets/snd0.at9` holds the quieter 48 kHz stereo ATRAC9 conversion with loop metadata.
The build does not download or execute an audio encoder.

Microsoft DirectXTex `texconv`, release `may2026`, converts the background under Wine.
The one-time audio conversion uses the proprietary encoder bundled with
[AT9 and AT3 Converter 2.7](https://github.com/BMK-Studio/AT9-AT3_Converter/releases/tag/2.7).
The owner's approval covers this local conversion, not redistribution of the encoder.
The encoder's redistribution permission remains unverified.
No encoder executable or DLL belongs in source or title packages.
See [Validation](VALIDATION.md#home-screen-background-and-music-2026-10-31) for commands, checksums and test limits.

## Native TV-remote contract

The native remote adapter uses [the PS5 SDL port](https://github.com/ps5-payload-dev/SDL/tree/ee4c47dc0d617b3bc8f35108f9956baf228a1322), revision `ee4c47dc0d617b3bc8f35108f9956baf228a1322`.
These independently authored declarations establish the system-user remote handle, typed pad layout and remote-key mappings.
They are community implementation source, not public Sony SDK documentation or proof of firmware 12.70 behavior.
SDK v0.43 supplies the existing `scePadOpen`, `scePadGetHandle`, `scePadReadState` and `scePadClose` link stubs.

| Source file | Locally recorded SHA-256 |
|---|---|
| `src/joystick/ps5/SDL_ps5joystick.h` | `16436774be2082a3fa4fd6ca4e9792ce45bbfcac64de676d5a56a7b0e6f1a706` |
| `src/video/ps5/SDL_ps5remote.c` | `d0aac6bf7abc4a970b9199265b86e40d940502f6b10d179f9fc3a9c93bc1d85a` |

`scripts/native_remote.py` retains SDL's zlib license notice, source attribution and an explicit altered-source notice in the generated adapter.
This adaptation changes handle ownership, browser suspension, retry behavior and native action translation. It does not add SDL as a build dependency.
