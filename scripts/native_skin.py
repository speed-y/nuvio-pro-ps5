"""Presentation-only Nuvio TV 1.3.11 skin for EVO v0.13.5.

Call patch_native(app) AFTER polish.patch_playback_hui and native_general.
The source of the visual values is the pinned frontend's css/base.css and
components-31, -34, -35, -36 and -37.css, plus the player markup in
playerScreenMethods-15-apply-manifest-track-selection.js. In particular the
final ATV overrides, not the earlier 1x CSS, define the 1920x1080 layout.

Keep controller hints rather than pretending EVO has the web player's
focusable action buttons. No input, timing, selection, decoder or policy
code is patched. Caption sizing/colours remain user-owned.
"""
from pathlib import Path

HERE = Path(__file__).parent


def _replace(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError('Pinned native skin anchor changed: ' + old[:100])
    return source.replace(old, new)


def _section(source, start, end, transform):
    """Constrain repeated drawing expressions to one named renderer method."""
    if source.count(start) != 1 or source.count(end) != 1:
        raise RuntimeError('Pinned native skin section changed: ' + start)
    a, b = source.index(start), source.index(end)
    return source[:a] + transform(source[a:b]) + source[b:]


def patch_osd_source(source):
    source = _replace(source, 'constexpr float kMargin = 96.0f;',
                      'constexpr float kMargin = 64.0f;')
    # Only chrome uses these neutral values. Diagnostic graph and secondary
    # caption colours retain their distinct meanings.
    source = _replace(source, 'const Color kInk = Color::rgb(0x0b0d16);',
                      'const Color kInk = Color::rgb(0x111111);')
    source = _replace(source, 'namespace tween = ::hui::tween;',
                      'namespace tween = ::hui::tween;\n' +
                      (HERE / 'ps5-player-skin-palette.inc').read_text())
    source = source.replace('const Palette &p = ctx.palette;',
                            'const Palette p = nuvio_player_palette(ctx.palette);')
    source = source.replace('ctx.palette.accent', 'Color::rgb(0xf5f5f5)')
    source = _section(source, 'void OsdScreen::draw_top(',
                      'void OsdScreen::draw_centre(',
                      lambda _: (HERE / 'ps5-player-skin-osd.inc').read_text() + '\n')
    # Leave the subtitle renderer intact apart from clearing the taller chrome.
    source = _replace(source, '150.0f * chrome : 0.0f', '280.0f * chrome : 0.0f')
    source = _replace(source, 'r.y + r.h > 850.0f', 'r.y + r.h > 720.0f')
    source = _replace(source, 'r.y -= 150.0f * chrome;', 'r.y -= 280.0f * chrome;')
    source = _replace(source,
                      'ui::text(list, fonts.mono, nuvio_clock_, 1920 - kMargin, 175, 23, kWhite, Align::right);',
                      'ui::text(list, fonts.semibold, nuvio_clock_, 1920 - kMargin, 78, 26, kWhite, Align::right);')
    return source


def patch_modals_source(source):
    source = _replace(source, 'namespace tween = ::hui::tween;',
                      'namespace tween = ::hui::tween;\n' +
                      (HERE / 'ps5-player-skin-palette.inc').read_text())
    source = source.replace('const Palette &p = ctx.palette;',
                            'const Palette p = nuvio_player_palette(ctx.palette);')
    source = _replace(source, 'const Color kInk = Color::rgb(0x0b0d16);',
                      'const Color kInk = Color::rgb(0x111111);')
    # Keep EVO's one-column selection model and every row/action. The web
    # player's language/style rails have no equivalent native focus model.
    source = _replace(source, 'constexpr float kSheetX = 1120.0f;',
                      'constexpr float kSheetX = 104.0f;')
    source = _replace(source, 'constexpr float kSheetW = 1920.0f - kSheetX - 48.0f;',
                      'constexpr float kSheetW = 900.0f;')
    source = _section(source, 'void SubtitlePicker::draw(', 'bool SubtitlePicker::focus(',
                      _subtitle_draw)
    return source


def _subtitle_draw(source):
    source = _replace(source,
                      '    list.rounded_rect(sheet, page::kRadiusCard, p.bg_top.with_alpha(0.96f));',
                      '    list.rounded_rect(sheet, 16, kBlack.with_alpha(0.34f));')
    source = _replace(source,
                      '    list.rounded_rect(ring_.value(), page::kRadiusTile, kWhite);',
                      '    list.bordered_rect(ring_.value(), 10, kClear, 2, kWhite);')
    source = _replace(source, '        const Color ink = t.focused ? kInk : kWhite;',
                      '''        if (t.current)
            list.rounded_rect(r, 10, p.accent);
        if (t.focused)
            list.bordered_rect(r, 10, kClear, 2, kWhite);
        const Color ink = t.current ? kInk : kWhite;''')
    # Selected and focused are independent, as in components-37.css.
    source = source.replace('t.focused ? kInk', 't.current ? kInk')
    source = _replace(source, 'const float cx = kSheetX * 0.5f;',
                      'const float cx = 1460.0f;')
    source = source.replace('kSheetX - 120', '700.0f')
    source = source.replace('fonts.display', 'fonts.semibold')
    return source


def patch_list_source(source):
    """Skin non-rail picker lists only; library/storage lists keep their theme."""
    source = _replace(source, 'namespace tween = ::hui::tween;',
                      'namespace tween = ::hui::tween;\n' +
                      (HERE / 'ps5-player-skin-palette.inc').read_text())
    source = _replace(source, '    title_ = str(p.title);\n    subtitle_ = str(p.subtitle);',
                      '    player_skin_ = p.section < 0;\n    title_ = str(p.title);\n    subtitle_ = str(p.subtitle);')
    return _section(source, 'void ListScreen::draw(', 'bool ListScreen::focus(', _list_draw)


def _list_draw(source):
    source = _replace(source, '    const Palette &p = ctx.palette;\n    draw_backdrop(list, ctx);',
                      '''    const Palette p = player_skin_ ? nuvio_player_palette(ctx.palette) : ctx.palette;
    if (player_skin_)
        list.rounded_rect({0, 0, 1920, 1080}, 0, Color::rgb(0x000000, 0.88f));
    else
        draw_backdrop(list, ctx);''')
    source = _replace(source, '            list.glow(ring_.value(), 20, 18, p.accent.with_alpha(0.3f));',
                      '            if (!player_skin_) list.glow(ring_.value(), 20, 18, p.accent.with_alpha(0.3f));')
    # The page heading helper uses the context's display face. Use the same
    # layout but the regular UI family for native playback menus.
    source = _replace(source, '        draw_page_title(list, ctx, title_, subtitle_, kLeft, dy);',
                      '''        ui::Fonts skin_fonts = fonts;
        if (player_skin_) skin_fonts.display = fonts.semibold;
        const Context skin_ctx{skin_fonts, ctx.textures, p, ctx.time};
        draw_page_title(list, skin_ctx, title_, subtitle_, kLeft, dy);''')
    return source


def patch_rml_source(source):
    # Move the existing nodes; no new state or duplicate dynamic IDs.
    start = '        <div id="title-block">'
    end = '    </div>\n\n    <!-- On-video caption'
    if source.count(start) != 1 or source.count(end) != 1:
        raise RuntimeError('Pinned native skin RML header changed')
    a, b = source.index(start), source.index(end)
    metadata = source[a:b]
    source = source[:a] + source[b:]
    return _replace(source, '    <div id="bottom-scrim">',
                    '    <div id="bottom-scrim">\n' + metadata)


def patch_rml_app_source(source):
    # Inline theme properties override RCSS. Restrict this to playback chrome,
    # leaving settings themes, caption policy and state transitions untouched.
    def chrome(section):
        for old, new in (
            ('ink_on(m_theme.accent)', '"#111111"'),
            ('to_hex_rgb(m_theme.accent)', '"#f5f5f5"'),
            ('to_hex_rgb(m_theme.border_sel)', '"#ffffff47"'),
            ('to_hex_rgba(m_theme.surface)', '"#242424"'),
        ):
            section = section.replace(old, new)
        return section
    return _section(source, 'void EvoRmlApp::UpdatePlaybackState(',
                    'void EvoRmlApp::UpdatePerfHud(', chrome)


def patch_native(app):
    """Apply once to the already adapted EVO project directory (not its root)."""
    transforms = {
        'ui_kit/src/evo_hui_osd.cpp': patch_osd_source,
        'ui_kit/src/evo_hui_modals.cpp': patch_modals_source,
        'ui_kit/src/evo_hui_screens.cpp': patch_list_source,
        'assets/rml/playback.rml': patch_rml_source,
        'ui_rml/src/evo_rmlui_app.cpp': patch_rml_app_source,
    }
    # Validate all anchors before writing any file, so source drift fails closed.
    pending = {app / name: transform((app / name).read_text())
               for name, transform in transforms.items()}
    header = app / 'ui_kit/include/evo_hui_screens.hpp'
    pending[header] = _replace(header.read_text(), '    bool empty_ = false;',
                               '    bool player_skin_ = false;\n    bool empty_ = false;')
    css = app / 'assets/rml/playback.rcss'
    text = css.read_text()
    if 'Nuvio TV 1.3.11 native skin' in text:
        raise RuntimeError('Native skin already applied')
    pending[css] = text + '\n' + (HERE / 'ps5-player-skin.rcss').read_text()
    for path, text in pending.items():
        path.write_text(text)
