# Nuvio PS5

<img src="assets/logo.png" width="190" alt="Nuvio">

Nuvio on your PS5, built around the controller.

Browse your library, pick a stream and watch through EVO Player's native playback engine.
The interface comes from Nuvio TV, with changes that make browsing, Search and playback return work more like a console app.
The goal is a familiar, nearly native-feeling experience without reaching for a pointer.

This is an independent community project for jailbroken consoles, not an official PlayStation app.

## Why this fork exists

I'm a developer, and I want to maintain and improve the version of Nuvio I use on my own PS5.
Keeping a fork lets me choose its direction, make changes and release them on my own schedule.
I don't want every decision to depend on an upstream project's priorities or approval.

The work here goes beyond repackaging: controller navigation, native keyboard integration, playback handling and fixes for everyday browsing bugs.
I want it to feel at home on the PS5, while keeping the freedom to keep building on it myself.
Useful changes can still go upstream. Maintaining this fork and contributing back are compatible.

This builds on [Bilawal Riaz's PS5 port](https://github.com/bilawalriaz/nuvio-ps5-homebrew),
[Nuvio TV](https://github.com/NuvioMedia/NuvioTVSmart) and [EVO Player](https://github.com/sainsaji/EVO-PLAYER-PS5).
Their work made this possible. This fork preserves their history, credits and licences.

## What this fork changes

- **Controller-first browsing.** D-pad and analog navigation, focused X activation, and Square or Options for item and profile menus.
- **Native Search entry.** Triangle opens Search with the PS5 keyboard, without losing your place when you return from a result.
- **Better playback return.** Circle brings you back to browsing without automatically starting the same video again.
- **Resume and progress handling.** Pass saved positions to native playback and bring progress back to the correct profile, movie or episode.
- **Browsing fixes.** Correct collection filters, improve Back navigation, fix focus styling and make settings actions reachable with the controller.
- **PS5 presentation.** Custom home-screen artwork and selection music, plus PS5 naming during QR login.
- **A self-contained install.** The PS5 serves its own browser UI and loads the bundled helper. No computer needs to host the interface.

The interface still uses the PS5 system browser. Playback uses native EVO code with hardware video decoding and audio output.
Controller support is the focus, but system-pointer suppression remains unresolved and the latest combined build still needs console testing.
See [Validation](docs/VALIDATION.md) for tested builds, known failures and pending checks.

## Start here

You need a PS5 jailbroken for the current boot, with ShadowMount and an ELF loader
listening on port **9021**. Do not update the firmware.

This fork extends firmware support through SDK v0.43, rather than keeping the older 13.60-only restriction.
The SDK checks firmware support and rejects unknown versions.
I've personally tested only **12.70**. Other SDK-recognized versions remain experimental, not confirmed compatible.
If you try another version, feedback is welcome. Please share your firmware, build version and what works or fails.
Older releases can retain the 13.60 restriction. Do not update your firmware to test this app.

The new single-install build includes its permission helper and browser UI.
Open Nuvio from its home-screen tile. The app loads the helper automatically.
After a reboot, run your jailbreak again before opening Nuvio.

1. Download `PPSA99996.zip` when the new fork build is available, then unpack it.
2. Start FTP on the PS5 and note its address and port.
3. Connect with an FTP client, then copy `PPSA99996` into `/data/homebrew/`.
4. Refresh ShadowMount's homebrew list and wait for the Nuvio tile.
5. Open Nuvio. Sign in or configure your addons, then choose something to watch.

The final path must be `/data/homebrew/PPSA99996/eboot.bin`, with `webui/`
and `sce_sys/` beside it. Avoid an extra nested `PPSA99996` folder.

To update, close Nuvio and replace only its matching app folder. Keep `/data/nuvio/` for settings and browser state.
The new ID does not update the old `PPSA99997` title in place. Keep the old title until the new one works.
Do not run both titles together because they share those settings.

If the tile is missing, check the folder layout and refresh ShadowMount.
For browser connection errors, check the current boot's jailbreak and ELF loader on port 9021.
For missing catalogues or login QR codes, check the console's network and DNS settings.
See [Troubleshooting](docs/TROUBLESHOOTING.md) for developer diagnostics.

Older `0.1.0-alpha.2` builds need a separate `nuvio.elf` startup payload. Current builds include the helper.

## Build from source

```sh
make check   # host tests and documentation checks, no console
make build   # browser UI, native title and helpers
make release # local archive from the generated artifacts
```

`make build` needs the host tools in [Build](docs/BUILD.md). It writes the title
to `build/EVO-PLAYER-PS5-*/output/app/PPSA99996/` and the helpers to
`build/*.elf`.

## Controls

- D-pad moves focus. X activates the focused item.
- Either analog stick also moves browsing focus.
- Square or Options opens the focused item's actions, including profile management.
- Triangle opens Search and its native keyboard. Returning from a result restores Search without reopening the keyboard.
- Play options on title details opens the existing menu without a long press.
- Circle stops playback that started from Nuvio and returns to browsing.
- Player settings opens the native EVO interface. Playback started there keeps
  EVO's own stop confirmation.
- Settings > Playback > Player settings opens that interface without a pointer.
- In settings text dialogs, Down moves to Save and Up returns to the field.

The title requests a hidden pointer, but system pointer suppression remains unresolved.
Do not rely on long-press X for item actions. Use Square, Options or Play options.

In Player settings, open Settings > Audio and enable Audio Passthrough.
Start a new stream to apply it. Your HDMI soundbar or receiver decodes the audio.

## Home-screen tile and app ID

This fork uses `PPSA99996`, separate from the upstream port's `PPSA99997`.
It's a locally chosen homebrew ID, not a Sony assignment or a reserved community ID. Global uniqueness is not guaranteed.
Local homebrew installation does not require Sony registration. See [Release](docs/RELEASE.md#store-listing) for community catalog requirements.

Nuvio appears under Games so the home-screen selection music can play.
On my 12.70 console, the Games tile played it but the Media tile stayed silent with the same audio.
It's still a media player. The classification is a workaround for that home-screen behavior.

## Requirements and codec support

- Firmware recognized by SDK v0.43, ShadowMount and the current boot's ELF loader on port 9021.
- Personally tested on **12.70** only. Other SDK-recognized firmware versions need community testing. See [Validation](docs/VALIDATION.md) for build-specific evidence.
- Use FTP for manual installation and updates.
- Software AV1 through dav1d is not included.
- Build from source on Linux or macOS. See [Build](docs/BUILD.md) for the host tools.

## Documentation

| Task | Guide |
|---|---|
| Install, start or update Nuvio | [Operations](docs/OPERATIONS.md) |
| Build the port | [Build](docs/BUILD.md) |
| Understand the browser and native player | [Architecture](docs/ARCHITECTURE.md) |
| Check what the console tests establish | [Validation](docs/VALIDATION.md) |
| Cut a release | [Release](docs/RELEASE.md) |
| Diagnose a failure or restore files | [Troubleshooting](docs/TROUBLESHOOTING.md) |
| Change code or documentation | [Contributing](docs/CONTRIBUTING.md) |
| Find a term or source | [Glossary](docs/GLOSSARY.md), [Sources](docs/SOURCES.md) |

## Contribute

Fresh-boot testing, playback return checks, subtitles and longer playback
sessions all help. Send the firmware, the artifact hashes and the expected and
observed behavior. Remove account details and private stream URLs from reports.
See [Contributing](docs/CONTRIBUTING.md).

For experimental testing, open the fork's **Releases** page and select the prerelease for your PR and tested commit.
Download `PPSA99996.zip` and `SHA256SUMS`. The complete `nuvio-ps5` package contains source and build receipts.
Same-repository PRs publish these test candidates after Host checks and native compilation pass.
They are not console-validated or marked latest. See [Release](docs/RELEASE.md) for details.
The **Actions** tab also provides `nuvio-experimental-<commit>` packages, which expire after 14 days.
Report the commit, firmware, loader and HEN versions, startup, playback and return behavior.
Do not update firmware to participate.

## AI usage disclosure

I use Amp extensively on this project, not just for autocomplete or proofreading.
AI agents helped research source and SDK interfaces, write and revise code, patches, tests, build scripts, packaging and documentation.
They also ran builds, host tests, browser previews and debugging tools, and prepared packages.
With my permission, an agent on my Mac installed console builds and verified the uploaded files through full readback.

I set the direction, choose features and assets, authorize console operations and test behavior on my PS5.
That does not mean every line has independent human review or a security audit.
Passing builds, tests and installation hashes do not prove that everything works on a console.
[Validation](docs/VALIDATION.md) separates those checks from actual hardware results.

The background came from Gemini after AI-assisted prompt iteration. I supplied the music WAV as a ChatGPT-created track.
Amp resized and converted the artwork, adjusted the audio level and converted the music to looped ATRAC9.
Exact generation models, backends and complete inputs remain unverified. I don't have a reliable percentage of AI-written code.
AI generation does not establish originality, ownership or clearance of third-party rights.

I'm responsible for what this fork distributes, including its code, assets, security, privacy and compatibility claims.
AI assistance does not replace upstream credit or licence obligations.
Private snapshots, credentials, addon URLs, console addresses, private logs and console dumps do not belong in this repository.
Agent tools process supplied context. This disclosure is not an audit of provider retention or a guarantee about everything supplied during development.

## Licences

Project code and patches use GPL-3.0-or-later. See [LICENSE](LICENSE) and
[Sources](docs/SOURCES.md). The build creates its runtime from independently
authored source in EVO and does not extract Sony modules from the console. Keep
account state, addon URLs and console logs outside source control.
