"""Pinned-source skin contracts; no generated-tree writes or console contact."""
from collections import Counter
from pathlib import Path
import re
import tempfile
import unittest

from scripts import native_general, native_skin, polish
from tests.test_native_subtitles import source_file


def region(source, start, end):
    return source.split(start, 1)[1].split(end, 1)[0]


class NativeSkinTests(unittest.TestCase):
    def prepared(self, app):
        for name in (
            'ui_kit/src/evo_hui_osd.cpp', 'ui_kit/include/evo_hui_osd.hpp',
            'ui_kit/src/evo_hui_modals.cpp', 'ui_kit/src/evo_hui_screens.cpp',
            'ui_kit/include/evo_hui_screens.hpp', 'ui_rml/src/evo_rmlui_app.cpp',
            'assets/rml/playback.rml', 'assets/rml/playback.rcss',
        ):
            path = app / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source_file(name))
        polish.patch_playback_hui(app)
        native_general.patch_hui(app)

    def test_native_skin_preserves_non_drawing_code_and_overlay_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            self.prepared(app)
            path = app / 'ui_kit/src/evo_hui_osd.cpp'
            before = path.read_text()
            native_skin.patch_native(app)
            after = path.read_text()
            # Exact update/set/caption eligibility code must not change.
            self.assertEqual(region(before, 'void OsdScreen::set(', 'void OsdScreen::draw_nuvio_prompts('),
                             region(after, 'void OsdScreen::set(', 'void OsdScreen::draw_nuvio_prompts('))
            for text in ('if (!raw_.nuvio_active) return;', 'if (skip_on_)',
                         'raw_.skip_countdown > 0 ? 1.0f : 0.5f',
                         'if (raw_.next_episode && !skip_on_)',
                         'if (!nuvio_clock_.empty() && !raw_.chrome_hidden)',
                         'if (raw_.nuvio_still_countdown > 0)',
                         'if (!skip_on_) hints[n++]', 'raw_.subtitle2_color, 0, 2',
                         'raw_.subtitle_style == 3', 'raw_.subtitle_image_canvas_w'):
                self.assertIn(text, after)
            self.assertIn('fit(fonts.semibold, title_, 48, 1160)', after)
            self.assertIn('1920 - 2 * kMargin, 12', after)
            self.assertNotIn('bar_.draw(canvas)', after)  # no EVO progress glow/finish flash

    def test_adapter_is_once_only_and_drift_fails_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            self.prepared(app)
            path = app / 'ui_kit/src/evo_hui_modals.cpp'
            path.write_text(path.read_text().replace('constexpr float kSheetX = 1120.0f;', 'changed'))
            before = {p: p.read_bytes() for p in app.rglob('*') if p.is_file()}
            with self.assertRaisesRegex(RuntimeError, 'Pinned native skin'):
                native_skin.patch_native(app)
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            self.prepared(app)
            native_skin.patch_native(app)
            before = {p: p.read_bytes() for p in app.rglob('*') if p.is_file()}
            with self.assertRaises(RuntimeError):
                native_skin.patch_native(app)
            self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_picker_focus_selection_and_native_library_isolation(self):
        original = source_file('ui_kit/src/evo_hui_modals.cpp')
        patched = native_skin.patch_modals_source(original)
        # Native focus targets and selection model are not changed by drawing.
        self.assertEqual(region(original, 'void SubtitlePicker::set(', 'void SubtitlePicker::draw('),
                         region(patched, 'void SubtitlePicker::set(', 'void SubtitlePicker::draw('))
        self.assertEqual(region(original, 'bool SubtitlePicker::focus(', 'void MediaInfoCard::set('),
                         region(patched, 'bool SubtitlePicker::focus(', 'void MediaInfoCard::set('))
        self.assertIn('const Color ink = t.current ? kInk : kWhite;', patched)
        self.assertIn('list.bordered_rect(r, 10, kClear, 2, kWhite)', patched)
        original = source_file('ui_kit/src/evo_hui_screens.cpp')
        patched = native_skin.patch_list_source(original)
        self.assertIn('player_skin_ = p.section < 0;', patched)
        self.assertIn('player_skin_ ? nuvio_player_palette(ctx.palette) : ctx.palette', patched)
        self.assertEqual(original.split('bool ListScreen::focus(', 1)[1],
                         patched.split('bool ListScreen::focus(', 1)[1])

    def test_rml_preserves_all_ids_and_dynamic_inline_colours_match(self):
        original = source_file('assets/rml/playback.rml')
        patched = native_skin.patch_rml_source(original)
        ids = lambda text: Counter(re.findall(r'id="([^"]+)"', text))
        self.assertEqual(ids(original), ids(patched))
        self.assertIn('<div id="bottom-scrim">\n        <div id="title-block">', patched)
        original = source_file('ui_rml/src/evo_rmlui_app.cpp')
        patched = native_skin.patch_rml_app_source(original)
        self.assertEqual(original.split('void EvoRmlApp::UpdatePlaybackState(', 1)[0],
                         patched.split('void EvoRmlApp::UpdatePlaybackState(', 1)[0])
        self.assertEqual(original.split('void EvoRmlApp::UpdatePerfHud(', 1)[1],
                         patched.split('void EvoRmlApp::UpdatePerfHud(', 1)[1])
        self.assertIn('el_fill->SetProperty("background-color", "#f5f5f5");', patched)
        self.assertIn('SetClass("raised", state.subtitle_raised)', patched)


if __name__ == '__main__':
    unittest.main()
