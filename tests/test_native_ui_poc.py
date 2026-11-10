"""Host checks for the Phase 1 native UI proof wiring."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native_ui_poc


class NativeUiPocSourceTests(unittest.TestCase):
    def test_theme_defaults_are_dark_nuvio_like(self):
        header = (ROOT / 'scripts/native_ui_poc/nuvio_poc_params.h').read_text()
        self.assertIn('0x0b0d10', header)
        self.assertIn('0x3dd6c6', header)
        self.assertIn('NUVIO_POC_MAX_ITEMS', header)

    def test_sample_catalog_is_small_json_array(self):
        catalog = json.loads((ROOT / 'scripts/native_ui_poc/poc_catalog.sample.json').read_text())
        self.assertIsInstance(catalog, list)
        self.assertGreaterEqual(len(catalog), 1)
        self.assertIn('title', catalog[0])
        self.assertIn('play_url', catalog[0])

    def test_preview_script_and_screen_sources_exist(self):
        for relative in (
            'scripts/native_ui_poc_preview.sh',
            'scripts/native_ui_poc/evo_hui_nuvio_poc.cpp',
            'scripts/native_ui_poc/NuvioPocScreen.cpp',
            'scripts/native_ui_poc/host_preview.cpp',
            'docs/NATIVE_UI_POC.md',
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)


class NativeUiPocPolishTests(unittest.TestCase):
    def test_install_sources_copies_kit_and_core_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / 'projects/evoplayer'
            evo = Path(tmp)
            (evo / 'tools/hui_preview').mkdir(parents=True)
            native_ui_poc.install_sources(app)
            self.assertTrue((app / 'ui_kit/src/evo_hui_nuvio_poc.cpp').is_file())
            self.assertTrue((app / 'core/src/screens/NuvioPocScreen.cpp').is_file())
            self.assertTrue((app / 'include/nuvio_poc_params.h').is_file())
            self.assertTrue((evo / 'tools/hui_preview/nuvio_poc_fixtures.inc').is_file())

    def test_screen_id_and_makefile_patches(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            common = app / 'core/include/evo/Common.hpp'
            makefile = app / 'Makefile'
            common.parent.mkdir(parents=True)
            common.write_text(
                '    SubtitleFile = 36          /* pick a subtitle file anywhere on the console */\n};\n')
            makefile.write_text(
                '                   ui_kit/src/evo_hui_provider.cpp \\\n'
                '                   ui_kit/src/evo_hui_complex.cpp\n'
                '    core/src/screens/LaunchScreen.cpp \\\n')
            native_ui_poc.patch_screen_id(app)
            native_ui_poc.patch_makefile(app)
            self.assertIn('NuvioPoc = 37', common.read_text())
            self.assertIn('evo_hui_nuvio_poc.cpp', makefile.read_text())
            self.assertIn('NuvioPocScreen.cpp', makefile.read_text())

    def test_application_excludes_poc_from_browser_loading_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            path = app / 'core/src/Application.cpp'
            path.parent.mkdir(parents=True)
            path.write_text(
                '#include "evo/screens/LaunchScreen.hpp"\n'
                '    m_screenManager->registerScreen(std::make_unique<LaunchScreen>());\n'
                '        bool nuvioShell = !isPlayer &&\n'
                '            !(m_playbackController && m_playbackController->isActive()) &&\n'
                '            !evo_webui_native_requested();\n')
            native_ui_poc.patch_application(app)
            text = path.read_text()
            self.assertIn('NuvioPocScreen.hpp', text)
            self.assertIn('ScreenId::NuvioPoc', text)
            self.assertIn('!onNuvioPoc', text)

    def test_boot_flag_keeps_browser_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            path = app / 'core/src/Application.cpp'
            path.parent.mkdir(parents=True)
            path.write_text(
                '#include "evo/Application.hpp"\n'
                '        /* Nuvio starts once its durable settings are reachable. Existing\n'
                '         * EVO code owns browser, playback handoff and shutdown lifetimes. */\n'
                '        static bool nuvio_opened = false;\n'
                '        if (!nuvio_opened && evo_jailbreak_is_open()) {\n'
                '            const evo_provider_t *nv = evo_provider_find("nuvio");\n'
                '            if (nv && nv->is_configured() &&\n'
                '                evo_webui_open_ex(nv->web_ui_url(), "/", "nuvio") == 0)\n'
                '                nuvio_opened = true;\n'
                '        }\n'
                '        evo_webui_pump();   /* #101: the system browser, when a web UI is open */\n')
            native_ui_poc.patch_boot_flag(app)
            text = path.read_text()
            self.assertIn('/data/nuvio/native_ui_poc', text)
            self.assertIn('evo_webui_open_ex(nv->web_ui_url(), "/", "nuvio")', text)
            self.assertIn('ScreenId::NuvioPoc', text)


class NativeUiPocVirtualizationTests(unittest.TestCase):
    def test_scroll_window_keeps_focus_visible(self):
        visible = 6
        focus = 0
        scroll = 0

        def move(delta, focus_index, scroll_index, count):
            focus_index = max(0, min(count - 1, focus_index + delta))
            if focus_index < scroll_index:
                scroll_index = focus_index
            if focus_index >= scroll_index + visible:
                scroll_index = focus_index - visible + 1
            return focus_index, scroll_index

        count = 8
        for _ in range(10):
            focus, scroll = move(1, focus, scroll, count)
            self.assertGreaterEqual(focus, scroll)
            self.assertLess(focus, scroll + visible)
        self.assertEqual(focus, 7)
        self.assertEqual(scroll, 2)


if __name__ == '__main__':
    unittest.main()
