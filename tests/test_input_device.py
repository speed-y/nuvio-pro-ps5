"""The web hint set follows the last real button and ignores a quick opposite press."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InputDeviceTests(unittest.TestCase):
    def test_switch_and_debounce(self):
        script = r'''
import { createInputDevice, noteInputDevice, remoteGlyphName, remoteGlyphSvg } from "../scripts/input-device.js";
const state = createInputDevice(0);
if (state.device !== "controller") throw new Error("default");
noteInputDevice(state, "remote", 1000);
if (state.device !== "remote") throw new Error("switch");
noteInputDevice(state, "controller", 1100);
if (state.device !== "remote") throw new Error("debounce");
noteInputDevice(state, "controller", 1200);
if (state.device !== "controller") throw new Error("later");
if (remoteGlyphName("Cross") !== "ok" || remoteGlyphName("Circle") !== "back") throw new Error("map");
if (remoteGlyphName("Triangle") !== "yellow" || remoteGlyphName("R2") !== "red") throw new Error("colour");
const svg = remoteGlyphSvg("red");
if (!svg.includes("#d64545") || !svg.includes("<svg")) throw new Error("svg");
console.log("ok");
'''
        path = ROOT / 'tests' / '_input_device_check.mjs'
        path.write_text(script)
        try:
            result = subprocess.run(['node', str(path)], cwd=ROOT, capture_output=True, text=True, timeout=20)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ok', result.stdout)
