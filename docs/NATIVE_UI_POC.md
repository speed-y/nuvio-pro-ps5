# Native UI proof of concept

This is Phase 1 from [Native UI feasibility](NATIVE_UI_FEASIBILITY.md).
It proves one Nuvio-like shelf on the existing `hui` and `sceAgc` path.
It does not replace the browser UI.

## What it adds

- One themed native shelf with a dark full-frame background and a hero block
- One horizontal virtualized poster row with a focus ring
- D-pad and stick movement along the row
- One detail card for the focused item
- A small metadata load that can fail without freezing the frame
- One Play action that starts the existing EVO player and returns to the same card
- UI sound off while the proof screen is open

The browser, `webui/`, and the current browser handoff stay in the title.

## Host preview

The host frame uses the same kit OpenGL path as EVO's `tools/hui_preview.sh`.
It does not establish console execution.

1. Install host Mesa EGL development packages.
2. From the repository root, run the preview script.
3. Open the PNG files under `output/uiview/`.

```sh
sudo apt-get install -y g++ libegl1-mesa-dev libgl1-mesa-dev libgl1-mesa-dri
bash scripts/native_ui_poc_preview.sh 1920 1080
```

The script fetches the pinned EVO and `ps5-homebrew-ui` trees, compiles the PoC
screen, and writes:

- `output/uiview/hui_nuvio_poc.png`
- `output/uiview/hui_nuvio_poc_detail.png`
- `output/uiview/hui_nuvio_poc_error.png`

Optional size arguments are width and height. The default is 1920 by 1080.

A full EVO `tools/hui_preview.sh` run also gains `nuvio_poc*` fixtures after a
normal title build unpacks and polishes the player tree. Set
`NUVIO_HUI_PREVIEW_LOCAL=1` to skip Docker when EGL is available on the host.

## Console opt-in

Default startup still opens the console-hosted browser UI.

To open the native proof instead:

1. Build and install the title as usual.
2. Create the empty flag file `/data/nuvio/native_ui_poc` on the console.
3. Optional: put a playable clip at `/data/nuvio/poc_sample.mp4` or
   `/data/nuvio/poc_sample.mkv`.
4. Optional: put `/data/nuvio/poc_catalog.json` for a small local catalogue.
5. Optional: create `/data/nuvio/poc_catalog.remote` to force the failed
   metadata path.
6. Open Nuvio Pro.

Controls on the proof screen:

| Input | Action |
|---|---|
| Left / Right or stick | Move along the poster row |
| Cross | Open the detail card, or Play when the detail card is open |
| Circle | Close the detail card |
| Options | Reload the small metadata fetch |
| Circle in the player | Stop and return to the same native card |

UI sounds stay off on this screen.

## Out of scope

- Accounts, profiles, addons, Trakt, and the full catalogue
- A new renderer or decoder
- Deleting `webui/` or the browser dialog
- Pixel-perfect parity with every Nuvio browser screen

## Pass gate

Pass needs the host frames, controller movement on console, a failed metadata
state that stays live, and Play that returns to the same card. Record console
results in [Validation](VALIDATION.md). If the proof fails the gate in the
feasibility report, keep the browser as the Nuvio UI.
