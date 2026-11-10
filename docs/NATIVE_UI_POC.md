# Native UI proof of concept

This is Phase 1 from [Native UI feasibility](NATIVE_UI_FEASIBILITY.md).
It proves one Nuvio-like shelf on the existing `hui` and `sceAgc` path.
It does not replace the browser UI.

## Side-by-side identity on this branch

This feature branch builds a **separate** console title so the installed product
Nuvio stays untouched:

| | Product (main / installed) | This PoC branch |
|---|---|---|
| Title ID | `PPSA99996` | `PPSA99995` |
| Home tile name | Nuvio Pro | Nuvio Native PoC |
| Install folder | `/data/homebrew/PPSA99996` | `/data/homebrew/PPSA99995` |
| Persistent data | `/data/nuvio` | `/data/nuvio-poc` |

Do not merge this identity onto `main` without an explicit decision. Product
builds keep `PPSA99996` and `/data/nuvio`.

## What it adds

- One Home-like native shelf with measured dark tokens (`#0d0d0d`), a left rail, hero, and overview
- One horizontal virtualized poster row (~221x339) with a white focus ring
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
If `build/native_ui_poc_preview/art/` holds a Home scrape (`hero_0.jpg`, posters,
`catalog.json`), the host preview loads that art. Set `NUVIO_POC_ART` to override
the art directory. Without art, the preview uses synthetic posters.

A full EVO `tools/hui_preview.sh` run also gains `nuvio_poc*` fixtures after a
normal title build unpacks and polishes the player tree. Set
`NUVIO_HUI_PREVIEW_LOCAL=1` to skip Docker when EGL is available on the host.

## Console install (safe beside product Nuvio)

1. Build this branch and install only into `/data/homebrew/PPSA99995`.
2. Leave `/data/homebrew/PPSA99996` and `/data/nuvio` alone.
3. Optional: put a playable clip at `/data/nuvio-poc/poc_sample.mp4` or
   `/data/nuvio-poc/poc_sample.mkv`.
4. Optional: put `/data/nuvio-poc/poc_catalog.json` for a small local catalogue.
5. Optional: create `/data/nuvio-poc/poc_catalog.remote` to force the failed
   metadata path.
6. Open the **Nuvio Native PoC** tile. It opens the native shelf by default.
7. To compare the packaged browser UI on the same PoC title, create the empty
   flag `/data/nuvio-poc/use_browser` and relaunch.

Controls on the proof screen:

| Input | Action |
|---|---|
| Left / Right or stick | Move along the poster row |
| Cross | Open the detail card, or Play when the detail card is open |
| Circle | Close the detail card |
| Options | Reload the small metadata fetch |
| Circle in the player | Stop and return to the same native card |

UI sounds stay off on this screen.

## Parity: what to judge now

Phase 1 is an **identity gate**, not pixel parity with the browser Home.

You are not looking too early for that gate. You *are* looking too early if the
goal is “looks identical to current Nuvio.”

### Check now (host PNG or console PoC tile)

- Dark full-bleed background near browser Home `#0d0d0d` (not EVO blue chrome)
- Left rail with Home active, content starting near 168px
- Brand mark **Nuvio**, hero title, short overview, and one Popular - Movie row
- Focus ring moves with Left/Right
- Accent reads purple (`#7b62ff`), matching the browser loading accent
- Poster cells near 221x339 with a white focus ring

### Do not fail Phase 1 for these yet

- Missing Continue Watching, profiles, addons, Trakt, settings
- Synthetic posters when no Home scrape art is present
- Exact CSS spacing, radii, or font metrics versus every browser breakpoint
- Missing search chrome or extra category rows

Full multi-row Home parity belongs to later phases.

### Useful side-by-side check on the console

1. Open installed **Nuvio Pro** (`PPSA99996`) → browser Home (unchanged).
2. Open **Nuvio Native PoC** (`PPSA99995`) → native shelf.
3. Ask only: same dark media-app identity, or still “another homebrew shell”?

## Out of scope

- Accounts, profiles, addons, Trakt, and the full catalogue
- A new renderer or decoder
- Deleting `webui/` or the browser dialog
- Pixel-perfect parity with every Nuvio browser screen

## Pass gate

Host preview frames compile and render. On console, the PoC title opens the
native shelf, moves focus, opens detail, starts Play on a local sample when
present, returns to the same card, and survives a failed metadata path without
freezing. Product Nuvio under `PPSA99996` remains usable afterward.
