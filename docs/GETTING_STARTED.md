# Getting started

Nuvio PS5 runs the Nuvio TV interface and plays video through EVO's native engine.
The single-install build includes the interface and its startup helper.

## Before you install

Run your jailbreak for the current boot. Do not update the firmware.
Console evidence covers firmware 12.70 and 13.60.
The current source delegates firmware support to SDK v0.43, which refuses versions it does not recognize.
Other SDK-recognized versions remain experimental. Older release assets can retain the 13.60 restriction.
Start ShadowMount and an ELF loader on port 9021 through your existing setup.
Start FTP and read the console's address and FTP port from that setup.

A jailbreak lets homebrew run until the console restarts.
ShadowMount adds the installed app folder to the PS5 home screen.
The ELF loader starts the permission helper bundled inside Nuvio.

## Install the app

1. Download the single-install `PPSA99997.zip` release asset.
2. Unpack it on your computer.
3. Open an FTP client and connect to the PS5's address and FTP port.
4. Copy the `PPSA99997` folder into `/data/homebrew/`.
5. Refresh ShadowMount's homebrew list.
6. Open the Nuvio tile after registration finishes.

Check the folder layout:

```text
/data/homebrew/PPSA99997/
  eboot.bin
  sce_module/
  sce_sys/
  webui/
```

Nuvio serves its interface from the PS5. You can disconnect your computer after installation.
Sign in through Nuvio's account screen and configure your addons.

## Use the controller

Use the D-pad to move focus and X to select.
During playback, use the player controls to pause or seek.
Press Circle to stop a Nuvio video and return to browsing.
Player settings opens EVO's native settings.

The experimental controller candidate adds these browsing controls:

- Options opens the focused item's existing action menu.
- On title details, Play options opens the same menu without a hold.
- Play manually remains inside the existing Play options menu.
- Triangle opens the controller menu, which contains Player settings.
- Settings > Playback > Player settings opens the native interface without a pointer.
- In a settings text dialog, Down moves from the field to Save.
- Up returns to the field. Cancel remains available in the action row.

The candidate requests a hidden pointer and uses Nuvio's visible focus instead.
Physical Options, Triangle, cursor hiding and console keyboard behavior still need PS5 validation.
Do not use long-press X as the test for opening menus.
See [Validation](VALIDATION.md#controller-navigation-candidate-2026-10-31) for the candidate checks and remaining gaps.

## After a reboot

Run your jailbreak again and start ShadowMount and the ELF loader.
Open Nuvio from its tile. The app loads its bundled helper automatically.

## Update Nuvio

Close Nuvio before replacing its files.
Copy the new release's `PPSA99997` folder over the old folder through FTP.
Keep `/data/nuvio/`, which stores your settings and browser state.
Open Nuvio after the copy finishes.

Release 0.1.0-alpha.2 needs the older `nuvio.elf` boot payload.
Use the single-install release notes to identify the new version.

## If something fails

- No tile: check the folder path and refresh ShadowMount.
- Opening Nuvio or a browser connection error: check the current boot's jailbreak and ELF loader on port 9021.
- Missing interface: check that the installed folder includes `webui/`.
- Missing catalog, thumbnails or login QR: check the console's network and DNS settings.

For a bug report, include your firmware, Nuvio version, loader, visible error,
and the action that caused it. Remove account details and stream URLs from logs.
See [Troubleshooting](TROUBLESHOOTING.md) for developer diagnostics.
