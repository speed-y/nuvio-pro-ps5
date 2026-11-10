#!/usr/bin/env bash
# Build host frames for the Nuvio native UI proof on the EVO hui OpenGL path.
# Does not install anything on a console.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="${NUVIO_POC_WORKDIR:-$ROOT/build/native_ui_poc_preview}"
OUT="${NUVIO_POC_OUT:-$ROOT/output/uiview}"
EVO_PIN="f6e43e6561796630673f1e20eb1eb67d6428514c"
HUI_PIN="47f4b9868c33264716b2e92922b0d2c9d0f2ab0f"
WIDTH="${1:-1920}"
HEIGHT="${2:-1080}"

mkdir -p "$WORKDIR/obj" "$OUT"
EVO="$WORKDIR/evo"
HUI="$WORKDIR/hui"

fetch_tree() {
  local url="$1" dest="$2" tgz="$3"
  if [[ -d "$dest" ]]; then
    return 0
  fi
  curl -fsSL -o "$tgz" "$url"
  mkdir -p "$dest"
  tar -xzf "$tgz" -C "$dest" --strip-components=1
}

fetch_tree "https://codeload.github.com/sainsaji/EVO-PLAYER-PS5/tar.gz/$EVO_PIN" "$EVO" "$WORKDIR/evo.tgz"
fetch_tree "https://codeload.github.com/sainsaji/ps5-homebrew-ui/tar.gz/$HUI_PIN" "$HUI" "$WORKDIR/hui.tgz"
rm -rf "$EVO/third_party/ps5-homebrew-ui"
mkdir -p "$EVO/third_party"
cp -a "$HUI" "$EVO/third_party/ps5-homebrew-ui"

# Install PoC draw sources into the unpacked EVO tree for includes/linking.
python3 - <<PY
from pathlib import Path
import shutil
import sys
sys.path.insert(0, r"$ROOT/scripts")
import native_ui_poc
evo = Path(r"$EVO")
app = evo / "projects/evoplayer"
native_ui_poc.install_sources(app)
# Standalone preview also needs the screen under the include path used below.
shutil.copyfile(Path(r"$ROOT") / "scripts/native_ui_poc/host_preview.cpp",
                evo / "tools/hui_preview/nuvio_poc_host_preview.cpp")
print("installed PoC sources")
PY

KIT="$EVO/third_party/ps5-homebrew-ui"
EVOP="$EVO/projects/evoplayer"
CXX="$(command -v g++ || command -v clang++)"
FLAGS=(-std=c++20 -O2 -w -DGL_GLEXT_PROTOTYPES=1
       -I"$KIT/src" -I"$KIT" -I"$KIT/host"
       -I"$EVOP" -I"$EVOP/ui_kit/include" -I"$EVOP/ui_rml/include" -I"$EVOP/include"
       -I"$ROOT/scripts/native_ui_poc")

SOURCES=(
  "$ROOT/scripts/native_ui_poc/host_preview.cpp"
  "$EVOP/ui_kit/src/evo_hui_nuvio_poc.cpp"
  "$EVOP/ui_kit/src/evo_hui_screens.cpp"
  "$KIT/host/platform_host.cpp"
)
while IFS= read -r -d '' f; do SOURCES+=("$f"); done < <(
  find "$KIT/src/gfx" "$KIT/src/ui" "$KIT/src/core" -name '*.cpp' -print0 | sort -z)

OBJS=()
for src in "${SOURCES[@]}"; do
  rel="${src#"$ROOT/"}"
  rel="${rel#"$EVO/"}"
  obj="$WORKDIR/obj/${rel//\//_}.o"
  OBJS+=("$obj")
  if [[ ! -f "$obj" || "$src" -nt "$obj" ]]; then
    mkdir -p "$(dirname "$obj")"
    echo "compile $rel"
    "$CXX" "${FLAGS[@]}" -c "$src" -o "$obj"
  fi
done

BIN="$WORKDIR/nuvio_poc_host_preview"
"$CXX" "${OBJS[@]}" -lEGL -lGL -lm -o "$BIN"

ART_DIR="${NUVIO_POC_ART:-$WORKDIR/art}"
if [[ -d "$ART_DIR" && -f "$ART_DIR/hero_0.jpg" ]]; then
  echo "using Home scrape art from $ART_DIR"
  "$BIN" "$EVO" "$OUT" "$WIDTH" "$HEIGHT" "$ART_DIR"
else
  echo "no art dir at $ART_DIR; using synthetic posters"
  "$BIN" "$EVO" "$OUT" "$WIDTH" "$HEIGHT"
fi
ls -la "$OUT"/hui_nuvio_poc*.png
