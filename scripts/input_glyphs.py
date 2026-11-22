"""Switch HUD and RmlUi button hints when the TV remote was used last."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / 'assets' / 'remote-glyphs'


def _replace(path, old, new, label):
    text = path.read_text()
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError('Input glyph anchor changed: ' + label)
    path.write_text(text.replace(old, new, 1))


def patch_hud_glyphs(kit):
    """Draw generic remote keys from the existing hint buttons when asked."""
    header = kit / 'src/ui/glyphs.hpp'
    source = kit / 'src/ui/glyphs.cpp'
    _replace(header,
             'float draw_hints(gfx::DrawList &list, const Fonts &fonts, const GlyphStyle &style,\n'
             '                 const Hint *hints, int count, float x, bool right_align,\n'
             '                 const HintLayout &layout = {});\n',
             'float draw_hints(gfx::DrawList &list, const Fonts &fonts, const GlyphStyle &style,\n'
             '                 const Hint *hints, int count, float x, bool right_align,\n'
             '                 const HintLayout &layout = {});\n'
             'void set_remote_glyphs(bool on);\n'
             'bool remote_glyphs();\n',
             'glyph header')
    inc = (ROOT / 'scripts/remote_glyph_draw.inc').read_text()
    _replace(source, 'float button_width(Button button, float size)\n{',
             inc + '\nfloat button_width(Button button, float size)\n{',
             'glyph source')
    _replace(source,
             'float button_width(Button button, float size)\n{\n    switch (button)\n    {\n    case Button::l1:',
             'float button_width(Button button, float size)\n{\n'
             '    if (remote_glyphs()) {\n'
             '        return button == Button::none ? 0.0f : size;\n'
             '    }\n'
             '    switch (button)\n    {\n    case Button::l1:',
             'glyph width')
    _replace(source,
             '    const float w = button_width(button, size);\n    const float cx = x + w * 0.5f;\n',
             '    if (remote_glyphs() && draw_remote_button(list, fonts, style, button, x, cy, size))\n'
             '        return;\n'
             '    const float w = button_width(button, size);\n    const float cx = x + w * 0.5f;\n',
             'glyph draw')


def patch_rml_glyphs(app):
    """Point the playback and subtitle documents at the active icon set."""
    header = app / 'ui_rml/include/evo_rmlui_app.h'
    source = app / 'ui_rml/src/evo_rmlui_app.cpp'
    playback = app / 'assets/rml/playback.rml'
    subtitles = app / 'assets/rml/subtitles.rml'
    _replace(header, 'Rml::ElementDocument* m_playback_doc = nullptr;\n',
             'Rml::ElementDocument* m_playback_doc = nullptr;\n'
             '    bool m_nuvio_remote_glyphs = false;\n',
             'rml member')
    helper = r'''
#include <string>
namespace hui { namespace ui { bool remote_glyphs(); } }
static void nuvio_glyph_src(Rml::ElementDocument *doc, const char *id, const char *prefix,
                             const char *controller, const char *remote, bool use_remote)
{
    if (!doc) return;
    if (auto *el = doc->GetElementById(id))
        el->SetAttribute("src", std::string(prefix) + (use_remote ? remote : controller));
}
static void nuvio_glyph_text(Rml::ElementDocument *doc, const char *id, const char *controller,
                              const char *remote, bool use_remote)
{
    if (!doc) return;
    if (auto *el = doc->GetElementById(id))
        el->SetInnerRML(use_remote ? remote : controller);
}
static void nuvio_apply_input_glyphs(Rml::ElementDocument *playback, Rml::ElementDocument *subtitles,
                                      bool use_remote)
{
    nuvio_glyph_src(playback, "glyph-play", "icons/", "btn_cross.png", "btn_remote_ok.png", use_remote);
    nuvio_glyph_src(playback, "glyph-seek", "icons/", "btn_dpad.png", "btn_remote_arrows.png", use_remote);
    nuvio_glyph_src(playback, "glyph-info", "icons/", "btn_square.png", "btn_remote_info.png", use_remote);
    nuvio_glyph_src(playback, "glyph-aspect", "icons/", "btn_triangle.png", "btn_remote_yellow.png", use_remote);
    nuvio_glyph_src(playback, "glyph-back", "icons/", "btn_circle.png", "btn_remote_back.png", use_remote);
    nuvio_glyph_text(playback, "tag-chapter", "L1 / R1", "CH- / CH+", use_remote);
    nuvio_glyph_text(playback, "tag-audio", "R2", "Red", use_remote);
    nuvio_glyph_text(playback, "tag-subs", "UP / DN", "Green", use_remote);
    nuvio_glyph_text(playback, "tag-sync", "TRACKPAD &lt; &gt;", "- / +", use_remote);
    nuvio_glyph_src(subtitles, "glyph-square", "../icons/", "btn_square.png", "btn_remote_info.png", use_remote);
    nuvio_glyph_src(subtitles, "glyph-triangle", "../icons/", "btn_triangle.png", "btn_remote_yellow.png", use_remote);
    nuvio_glyph_src(subtitles, "glyph-back", "../icons/", "btn_circle.png", "btn_remote_back.png", use_remote);
    nuvio_glyph_text(subtitles, "tag-sync", "&lt; &gt;", "- / +", use_remote);
    nuvio_glyph_text(subtitles, "tag-second", "L1 R1", "CH- CH+", use_remote);
}

'''
    _replace(source, '#include "evo_rmlui_app.h"\n',
             '#include "evo_rmlui_app.h"\n' + helper, 'rml helper')
    _replace(source, '    if (state == m_last_state && m_theme_generation == m_theme_gen_playback) return;\n',
             '    if (state == m_last_state && m_theme_generation == m_theme_gen_playback &&\n'
             '        hui::ui::remote_glyphs() == m_nuvio_remote_glyphs) return;\n'
             '    m_nuvio_remote_glyphs = hui::ui::remote_glyphs();\n'
             '    nuvio_apply_input_glyphs(m_playback_doc, m_subtitles_doc, m_nuvio_remote_glyphs);\n',
             'rml refresh')
    pairs = (
        (playback, '<img src="icons/btn_cross.png" class="glyph-badge-img"/>',
         '<img id="glyph-play" src="icons/btn_cross.png" class="glyph-badge-img"/>'),
        (playback, '<img src="icons/btn_dpad.png" class="glyph-badge-img"/>',
         '<img id="glyph-seek" src="icons/btn_dpad.png" class="glyph-badge-img"/>'),
        (playback, '<img src="icons/btn_square.png" class="glyph-badge-img"/>',
         '<img id="glyph-info" src="icons/btn_square.png" class="glyph-badge-img"/>'),
        (playback, '<img src="icons/btn_triangle.png" class="glyph-badge-img"/>',
         '<img id="glyph-aspect" src="icons/btn_triangle.png" class="glyph-badge-img"/>'),
        (playback, '<img src="icons/btn_circle.png" class="glyph-badge-img"/>',
         '<img id="glyph-back" src="icons/btn_circle.png" class="glyph-badge-img"/>'),
        (playback, '<span class="btn-tag">L1 / R1</span>',
         '<span id="tag-chapter" class="btn-tag">L1 / R1</span>'),
        (playback, '<span class="btn-tag">R2</span>',
         '<span id="tag-audio" class="btn-tag">R2</span>'),
        (playback, '<span class="btn-tag">UP / DN</span>',
         '<span id="tag-subs" class="btn-tag">UP / DN</span>'),
        (playback, '<span class="btn-tag">TRACKPAD &lt; &gt;</span>',
         '<span id="tag-sync" class="btn-tag">TRACKPAD &lt; &gt;</span>'),
        (subtitles, '<img src="../icons/btn_square.png" class="glyph-badge-img"/>',
         '<img id="glyph-square" src="../icons/btn_square.png" class="glyph-badge-img"/>'),
        (subtitles, '<div class="glyph-badge"><img src="../icons/btn_triangle.png" class="glyph-badge-img"/></div>',
         '<div class="glyph-badge"><img id="glyph-triangle" src="../icons/btn_triangle.png" class="glyph-badge-img"/></div>'),
        (subtitles, '<img src="../icons/btn_circle.png" class="glyph-badge-img"/>',
         '<img id="glyph-back" src="../icons/btn_circle.png" class="glyph-badge-img"/>'),
        (subtitles, '<span class="btn-tag">&lt; &gt;</span>',
         '<span id="tag-sync" class="btn-tag">&lt; &gt;</span>'),
        (subtitles, '<span class="btn-tag">L1 R1</span>',
         '<span id="tag-second" class="btn-tag">L1 R1</span>'),
    )
    for path, old, new in pairs:
        _replace(path, old, new, old[:40])


def install(evo):
    """Copy remote icons and teach the HUD and RmlUi to switch."""
    kit = evo / 'third_party/ps5-homebrew-ui'
    app = evo / 'projects/evoplayer'
    icons = app / 'assets/icons'
    if not icons.is_dir():
        raise RuntimeError('EVO is missing assets/icons')
    for icon in ICONS.glob('btn_remote_*.png'):
        shutil.copyfile(icon, icons / icon.name)
    patch_hud_glyphs(kit)
    patch_rml_glyphs(app)
