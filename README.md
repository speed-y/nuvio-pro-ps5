# Nuvio Pro

<img src="assets/logo.png" width="190" alt="Nuvio">

Nuvio for your PS5, built around the controller.

This is the standalone home for [Nuvio Pro](https://github.com/speed-y/nuvio-pro-ps5), my independently maintained PS5 fork.

Browse your library, pick a stream and watch through EVO Player's native playback engine.
The interface comes from Nuvio TV, with changes that make browsing, Search and playback return work more like a console app.
The goal is a familiar, nearly native-feeling experience without reaching for a pointer.

This is an independent community project for jailbroken consoles, not an official PlayStation app.

## Why this fork exists

I'm a developer, and I want to maintain and improve the version of Nuvio I use on my own PS5.
Keeping a fork lets me choose its direction, make changes and release them on my own schedule.
I don't want every decision to depend on an upstream project's priorities or approval.

The work here goes beyond repackaging: controller navigation, in-browser Search entry, playback handling and fixes for everyday browsing bugs.
I want it to feel at home on the PS5, while keeping the freedom to keep building on it myself.
Useful changes can still go upstream. Maintaining this fork and contributing back are compatible.

This builds on [Bilawal Riaz's PS5 port](https://github.com/bilawalriaz/nuvio-ps5-homebrew),
[Nuvio TV](https://github.com/NuvioMedia/NuvioTVSmart) and [EVO Player](https://github.com/sainsaji/EVO-PLAYER-PS5).
Their work made this possible. This fork preserves their history, credits and licences.

## What this fork changes

- **Controller-first browsing.** D-pad and analog navigation, focused X activation, and Square or Options for item and profile menus.
- **In-browser Search entry.** Triangle opens a controller-operated keyboard without closing the browser. Returning from a result preserves Search without reopening it.
- **Nuvio-style player controls.** Native EVO playback uses Nuvio's neutral palette, bottom title and timeline, with its existing controller shortcuts.
- **Better playback return.** Circle brings you back to browsing without automatically starting the same video again.
- **Resume and progress handling.** Pass saved positions to native playback and bring progress back to the correct profile, movie or episode.
  Native playback checkpoints changed progress every 30 seconds for recovery after a forced close or restart. PS5 validation remains pending.
- **Intro, recap and credits skipping.** Honor per-segment auto-skip settings, with native R1 prompts otherwise. This feature still needs PS5 validation.
- **Native next episode.** Show EVO's next-episode prompt, then let Nuvio select a fresh stream.
  Circle on the prompt returns to the series episodes or movie page. Movies and final episodes also have an end card.
  Connection retries keep their buffering indicator without warning popups. These changes still need PS5 validation.
- **Browsing fixes.** Correct collection filters, improve Back navigation, fix focus styling and make settings actions reachable with the controller.
- **Native download test.** Settings > Playback > Speed test measures one connection to TorBox's nearest test CDN. PS5 validation remains pending.
- **PS5 presentation.** Custom home-screen artwork and selection music, plus PS5 naming during QR login.
- **A self-contained install.** The PS5 serves its own browser UI and loads the bundled helper.
  The title dynamically finds `webui/` beside `eboot.bin` on internal storage, an M.2 SSD or USB drives.
  No computer needs to host the interface.

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

The single-install build includes its permission helper and browser UI.
Open Nuvio Pro from its home-screen tile. The app loads the helper automatically.
After a reboot, run your jailbreak again before opening Nuvio Pro.

1. Download `PPSA99996.zip` when the new fork build is available, then unpack it.
2. Start FTP on the PS5 and note its address and port.
3. Connect with an FTP client, then copy `PPSA99996` to your chosen storage location.
   On internal storage, copy `PPSA99996` into `/data/homebrew/`.
   On an M.2 SSD, place `PPSA99996` in `/mnt/ext0/app/` or `/mnt/ext0/homebrew/`.
   On a USB drive, place `PPSA99996` in `/mnt/usb0/` or `/mnt/usb0/homebrew/`.
4. Refresh ShadowMount's homebrew list and wait for the Nuvio Pro tile.
5. Open Nuvio Pro. Sign in or configure your addons, then choose something to watch.

Place `webui/` and `sce_sys/` directly beside `eboot.bin`. Avoid an extra nested `PPSA99996` folder.
The app resolves its web UI path dynamically from its binary location.
Settings, logs and profile data stay on internal storage under `/data/nuvio/`.
Disconnecting or swapping external storage does not remove your settings.

To update, close the app and replace only its matching app folder. Keep `/data/nuvio/` for settings and browser state.
Nuvio Pro keeps `PPSA99996` and the same data path as this fork's previous builds. The rename does not require another title migration.
It does not update the upstream `PPSA99997` title in place. Keep the old title until the new one works.
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
- Triangle opens Search and its in-browser keyboard. D-pad selects keys, X types, and Circle cancels without changing the query.
  Select Search to submit. Space, Delete, Clear and Shift are available. Other text fields retain their existing keyboard behavior.
  Within this keyboard, Triangle inserts Space, Square deletes, L1 moves left and R1 moves right. L2 toggles Shift and R2 submits Search. These use observed browser events F5-F8. Action keys show their button icons.
  L1 moves the text caret left and R1 moves it right. Typing inserts at the caret, and Delete removes the preceding character.
  The owner reports that physical shoulder shortcuts fail on build `1110-1708`. X activation works. Investigation and L3 console validation remain pending.
  Triangle does not reopen Search while this keyboard is open.
  Suggestions combine recent searches with matching addon titles. Move Up from the number row, then press X to complete the query.
  Completion does not submit. Press R2 or select Search when ready. Live title suggestions need two characters and available searchable addons.
- The fallback Controller menu includes Display diagnostics. It reports browser dimensions without changing scaling or verifying the HDMI output resolution.
- Play options on title details opens the existing menu without a long press.
- Circle stops playback that started from Nuvio and returns to browsing.
- There is no dedicated Change stream button or player menu. Return to browsing to select another stream.
- During native playback, Down opens the subtitle picker. Up toggles subtitles, and R2 opens the audio-track picker.
- During a native Skip intro, Skip recap or Skip credits prompt, press R1 to skip.
- Otherwise, R1 starts the next episode when its prompt appears. Without either prompt, R1 keeps its chapter action.
- During the next-episode prompt, L1 selects Keep watching and cancels that episode's automatic transition.
- Skipping requires Settings > Playback > Skip Intro and available IntroDB timestamps.
- Native playback honors the individual Auto-skip intro, recap, outro and movie-credits settings. Disabled types keep manual prompts.
- Player settings opens the native EVO interface. Playback started there keeps
  EVO's own stop confirmation.
- Settings > Playback > Player settings opens that interface without a pointer.
- In settings text dialogs, Down moves to Save and Up returns to the field.

The title requests a hidden pointer, but system pointer suppression remains unresolved.
Do not rely on long-press X for item actions. Use Square, Options or Play options.

In Player settings, open Settings > Audio and enable Audio Passthrough.
Start a new stream to apply it. Your HDMI soundbar or receiver decodes the audio.

Automatic and manual credit skips preserve known post-credit scenes. Timestamp coverage and accuracy depend on the title and its cut.
The pinned movie mapping supports credits and post-credit scenes, not movie intros. Series mapping supports intros, recaps and outros.
Missing timestamps leave playback unchanged. Lookup can add up to four seconds before native playback starts.
Auto-skip acts when playback enters an enabled segment. Pause, buffering and scrubbing defer automatic skips until playback becomes ready.
Otherwise, each prompt stays fully visible for ten seconds, then dims to 50% opacity. R1 remains available until the segment ends.
The "Dims in" countdown pauses with playback. It never starts a skip automatically.
Settings apply when starting a native playback session. Turning off Skip Intro disables both automatic skips and manual prompts.

Native next episode uses Nuvio's playback threshold, autoplay, countdown and still-watching settings.
With autoplay enabled, the default countdown lasts three seconds. Pausing or buffering freezes it.
With autoplay disabled, the prompt requires R1 instead.
End suggestions appear only with playback controls and disappear after ten seconds. Hiding and reopening controls permits another ten-second display.
This display limit does not cancel autoplay. The still-watching confirmation remains separate.
At the still-watching limit, playback pauses with a 60-second prompt. X starts the next episode, while Circle or timeout returns to details.
The browser returns briefly to resolve the next aired episode through the existing stream-selection policy.
Manual source selection or a failed automatic selection opens the next episode's stream picker.
Recovery after a forced close restores progress without starting another episode automatically.

Playback > General also controls native loading status, the delayed pause synopsis, parental warnings and the OSD clock.
Post-play recommendations offer up to three related titles near the configured movie threshold or series ending.
R1 opens the selected title's details, Triangle changes the pick, and L1 dismisses recommendations. An active skip prompt keeps R1 priority.
These native cards do not play recommendation trailers or start another title automatically.
Metadata preparation shares the four-second skip-lookup window. Missing or late metadata leaves the corresponding card absent.
Known post-credit scenes delay recommendations. Settings apply when starting playback and still need console validation for this candidate.
Remembered sources save after native playback produces a ready frame, not merely after selecting a stream.
Source reuse matches fresh addon results instead of storing signed stream URLs. Unsupported plugin-only choices stay hidden on PS5.

## Home-screen tile and app ID

This fork uses `PPSA99996`, separate from the upstream port's `PPSA99997`.
It's a locally chosen homebrew ID, not a Sony assignment or a reserved community ID. Global uniqueness is not guaranteed.
Local homebrew installation does not require Sony registration. See [Release](docs/RELEASE.md#store-listing) for community catalog requirements.

Nuvio Pro appears under Games so the home-screen selection music can play.
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
| Install, start or update Nuvio Pro | [Operations](docs/OPERATIONS.md) |
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

For experimental testing, open [Releases](https://github.com/speed-y/nuvio-pro-ps5/releases) and select the prerelease for your PR and tested commit.
Download `PPSA99996-pr-test.zip` and `SHA256SUMS`. It unpacks to the same `PPSA99996` folder.
The complete `nuvio-pro-ps5` package contains source and build receipts.
Same-repository PRs publish these test candidates after Host checks and native compilation pass.
They are not console-validated or marked latest. See [Release](docs/RELEASE.md) for details.
Documentation-only updates skip publication when they can reuse a successful native build or contain no application changes.
The **Actions** tab also provides `nuvio-Linux-X64-<commit>` packages, which expire after 14 days.
Manual Release workflow runs provide downloads too, with an optional macOS compatibility build.
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
