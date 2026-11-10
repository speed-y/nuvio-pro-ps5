"""Native policy, controller and renderer adapters for Playback > General."""
from pathlib import Path
import shutil

HERE = Path(__file__).parent
TEXT_FIELDS = ('pause_text', 'parental', 'recommendation', 'clock', 'loading_status')


def patch_native(app):
    from polish import replace
    shutil.copyfile(HERE/'ps5-general.h', app/'include/nuvio_presentation.h')
    web = app/'src/evo_webui.c'
    replace(web, 'static void serve_evo(int fd, const char *path)',
        (HERE/'ps5-general.c').read_text() + '\nstatic void serve_evo(int fd, const char *path)')
    replace(web, '        if (!strncmp(path, "/evo/storage", 12))',
        '''        if (!strcmp(path, "/evo/presentation"))
            serve_presentation(fd, method, req, got, hl);
        else if (!strncmp(path, "/evo/storage", 12))''')
    replace(web, '        query_param(path, "session", s_h_progress_session, sizeof s_h_progress_session);',
        '''        query_param(path, "session", s_h_progress_session, sizeof s_h_progress_session);
        presentation_handoff(s_h_progress_session);''')
    replace(web, '            s_play_next = s_h_next;',
        '            s_play_next = s_h_next;\n            s_play_presentation = s_h_presentation;')
    replace(web, '    evo_webui_skip_countdown(0.0, 0, 0);\n    playback_next_begin();',
        '    evo_webui_skip_countdown(0.0, 0, 0);\n    playback_next_begin();\n    presentation_begin();')
    replace(web, '    s_progress_return_detail = 0;',
        '    s_progress_return_detail = 0;\n    s_progress_played = s_progress_recommendation = 0;')
    replace(web, '    memset(s_skip, 0, sizeof s_skip);',
        '    memset(s_skip, 0, sizeof s_skip);\n    memset(&s_presentation, 0, sizeof s_presentation);')
    player = app/'core/src/screens/PlayerScreen.cpp'
    header = app/'core/include/evo/screens/PlayerScreen.hpp'
    replace(header, '#include "evo/screens/StatefulScreen.hpp"',
        '#include "evo/screens/StatefulScreen.hpp"\n#include "evo_rmlui_bridge.h"\n#include "nuvio_presentation.h"')
    replace(header, '    void initPlayerStateMachine();', '''    void updateNuvioPresentation(uint64_t now);
    void fillNuvioPresentation(evo_playback_osd_params_t &p);
    nuvio_presentation_view_t m_nuvioView{};
    char m_nuvioClock[64]{};
    std::string m_nuvioRecommendation;
    uint64_t m_nuvioEndSuggestionSince = 0;
    uint64_t m_nuvioWaitSince = 0;
    int m_nuvioWaitReports = 0;
    void initPlayerStateMachine();''')
    replace(player, 'extern volatile int pb_prebuffer_hold;',
        '''extern volatile int pb_prebuffer_hold;
extern volatile int pb_scrub_hold;
extern volatile int video_decode_hold;
extern int screen;''')
    replace(player, '    if (pressed & PadButtons::Cross) {', '''    if (m_nextEpisodeState >= 1000) {
        if (pressed & (PadButtons::Cross | PadButtons::R1 | PadButtons::Circle | PadButtons::L1)) {
            nextEpisode((pressed & (PadButtons::Cross | PadButtons::R1)) ? 1 : 2);
            playback->stopPlayback();
            if (screenMgr) screenMgr->returnFromPlayback();
        }
        return true;
    }
    if (pressed & PadButtons::Cross) {''')
    replace(player, '    if (pressed & PadButtons::Triangle) {', '''    if (pressed & PadButtons::Triangle) {
        if (m_nuvioView.recommendation) {
            evo_webui_presentation_action(1);
            updateNuvioPresentation(NowMs());
            return true;
        }''')
    replace(player, '        playback->jumpChapter(-1);', '''        if (m_nuvioView.recommendation) {
            evo_webui_presentation_action(2);
            updateNuvioPresentation(NowMs());
            return true;
        }
        playback->jumpChapter(-1);''')
    replace(player, '        evo_boot_log("skip R1: action=chapter position=%.3f", playback->getPositionSeconds());',
        '''        if (m_nuvioView.recommendation) {
            evo_webui_recommendation_selected(m_nuvioView.recommendation);
            playback->stopPlayback();
            if (screenMgr) screenMgr->returnFromPlayback();
            return true;
        }
        evo_boot_log("skip R1: action=chapter position=%.3f", playback->getPositionSeconds());''')
    replace(player, 'if (m_nextEpisodeState || m_playbackEnded) evo_webui_return_to_nuvio();',
        'if (m_nextEpisodeState || m_playbackEnded || m_nuvioView.recommendation) evo_webui_return_to_nuvio();')
    replace(player, '    if (m_nextEpisodeState == -2) {',
        '    if (m_nextEpisodeState == -2 || m_nextEpisodeState == -3) {')
    replace(player, '    m_nextEpisodeState = nextEpisode();', '''    m_nextEpisodeState = nextEpisode();
    if (m_nextEpisodeState >= 1000) playback->setPaused(true);
    updateNuvioPresentation(now);''')
    replace(player, '    if (m_nextEpisodeState || m_playbackEnded) return true;',
        '''    if (m_nextEpisodeState || m_playbackEnded || m_nuvioView.pause ||
        m_nuvioView.parental || m_nuvioView.recommendation) return true;''')
    replace(player, '    } else if ((m_nextEpisodeState || m_playbackEnded || skipType ||',
        '    } else if ((m_nuvioView.pause || m_nuvioView.parental || m_nuvioView.recommendation || m_nextEpisodeState || m_playbackEnded || skipType ||')
    source = player.read_text()
    anchor = '        evo_rmlui_update_playback_params(&p);'
    if source.count(anchor) != 2: raise RuntimeError('Pinned General OSD branches changed')
    player.write_text(source.replace(anchor, '        fillNuvioPresentation(p);\n'+anchor))
    replace(player, '    m_playbackEnded = false;\n    StatefulScreen::onExit();',
        '''    m_playbackEnded = false;
    m_nuvioView = {};
    m_nuvioClock[0] = 0;
    m_nuvioRecommendation.clear();
    m_nuvioEndSuggestionSince = 0;
    m_nuvioWaitSince = 0;
    m_nuvioWaitReports = 0;
    StatefulScreen::onExit();''')
    # Append inside PlayerScreen's existing namespace, after all static helpers.
    replace(player, '} // namespace evo', (HERE/'ps5-general-player.cpp').read_text() + '\n} // namespace evo')
    bridge_header = app/'ui_rml/include/evo_rmlui_bridge.h'
    replace(bridge_header, '    int chrome_hidden;',
        ''.join('    const char *nuvio_'+name+';\n' for name in TEXT_FIELDS) +
        '    int nuvio_active;\n    int nuvio_still_countdown;\n    int chrome_hidden;')
    patch_hui(app)
    patch_rml(app)
    application = app/'core/src/Application.cpp'
    replace(application, '#include "evo_webui.h"', '#include "evo_webui.h"\n#include "nuvio_presentation.h"')
    replace(application, '                        g_nuvio_preparing ? "Preparing playback" : "Opening Nuvio Pro");',
        '''                        !g_nuvio_preparing ? "Opening Nuvio Pro" :
                        evo_webui_presentation()->active && !evo_webui_presentation()->loading ? "" :
                        evo_webui_presentation()->active && !evo_webui_presentation()->loading_detail ? " " :
                        "Preparing playback");''')
    replace(app/'ui_rml/src/evo_rmlui_app.cpp', '    ShowOnlyScreen(m_nuvio_doc);',
        '''    ShowOnlyScreen(m_nuvio_doc);
    m_nuvio_doc->SetProperty("opacity", message && !*message ? "0" : "1");
    m_frame_dirty = true;''')


def patch_hui(app):
    from polish import replace
    header = app/'ui_kit/include/evo_hui_osd.hpp'
    source = app/'ui_kit/src/evo_hui_osd.cpp'
    replace(header, '    void draw_nuvio_prompts(',
        '    void draw_nuvio_general(hui::gfx::DrawList &list, const Context &ctx) const;\n    void draw_nuvio_prompts(')
    replace(header, '    std::string title_, meta_;',
        '    std::string title_, meta_;\n' +
        ''.join('    std::string nuvio_'+name+'_;\n' for name in TEXT_FIELDS).rstrip())
    replace(source, '    raw_.skip_label = nullptr;', '    raw_.skip_label = nullptr;\n' +
        '\n'.join('    nuvio_'+name+'_ = str(p.nuvio_'+name+');\n    raw_.nuvio_'+name+' = nullptr;' for name in TEXT_FIELDS))
    replace(source, '        draw_nuvio_prompts(list, ctx);',
        '        draw_nuvio_prompts(list, ctx);\n        draw_nuvio_general(list, ctx);')
    replace(source, '    if (paused_.value > 0.01f)',
        '    if (paused_.value > 0.01f && nuvio_pause_text_.empty() && !raw_.nuvio_still_countdown)')
    replace(source, '        ui::text(list, fonts.semibold, "LOADING", 960, 630, 18, kWhite.with_alpha(0.85f), Align::center, 3.0f);',
        '''        if (!raw_.nuvio_active || !nuvio_loading_status_.empty())
            ui::text(list, fonts.semibold, raw_.nuvio_active ? nuvio_loading_status_ : "LOADING",
                960, 630, 18, kWhite.with_alpha(0.85f), Align::center, 3.0f);''')
    replace(source, '    return chrome_.value > 0.01f || raw_.scrub_active || raw_.paused ||',
        '''    return !nuvio_parental_.empty() || !nuvio_pause_text_.empty() ||
        !nuvio_recommendation_.empty() || raw_.nuvio_still_countdown ||
        chrome_.value > 0.01f || raw_.scrub_active || raw_.paused ||''')
    replace(source, '    /* The title is not checked:',
        '''    for (const auto &line : split_lines(nuvio_parental_.c_str()))
        if (!font_covers(*fonts.semibold.font, line)) return false;
    for (const std::string *text : {&nuvio_pause_text_, &nuvio_recommendation_})
        for (const auto &line : split_lines(text->c_str()))
            if (!font_covers(*fonts.regular.font, line)) return false;
    /* The title is not checked:''')
    replace(source, '} // namespace evo::kit', (HERE/'ps5-general-hui.cpp').read_text() + '\n} // namespace evo::kit')


def patch_rml(app):
    from polish import replace
    state = app/'ui_rml/include/evo_rmlui_app.h'
    replace(state, 'struct EvoPlaybackState {', 'struct EvoPlaybackState {\n' +
        ''.join('    std::string nuvio_'+name+';\n' for name in TEXT_FIELDS) +
        '    int nuvio_active = 0, nuvio_still_countdown = 0;')
    replace(state, '        return playback_ended == o.playback_ended',
        '        return nuvio_active == o.nuvio_active && nuvio_still_countdown == o.nuvio_still_countdown &&\n' +
        ''.join('               nuvio_'+name+' == o.nuvio_'+name+' &&\n' for name in TEXT_FIELDS) +
        '               playback_ended == o.playback_ended')
    replace(app/'ui_rml/src/evo_rmlui_bridge.cpp', '    state.chrome_hidden = (p->chrome_hidden != 0);',
        '    state.chrome_hidden = (p->chrome_hidden != 0);\n' +
        ''.join('    state.nuvio_'+name+' = p->nuvio_'+name+' ? p->nuvio_'+name+' : "";\n' for name in TEXT_FIELDS) +
        '    state.nuvio_active = p->nuvio_active;\n    state.nuvio_still_countdown = p->nuvio_still_countdown;')
    replace(app/'ui_rml/src/evo_rmlui_app.cpp', '    m_last_state = state;',
        (HERE/'ps5-general-rml.cpp').read_text() + '\n    m_last_state = state;')
    replace(app/'ui_rml/src/evo_rmlui_app.cpp',
        '        if (state.paused && !state.scrub_active && !state.loading) {',
        '''        if (state.paused && !state.scrub_active && !state.loading &&
            state.nuvio_pause_text.empty() && !state.nuvio_still_countdown) {''')
    replace(app/'assets/rml/playback.rml', '    <!-- Bottom Netflix Controller Bar -->',
        '''    <div id="nuvio-clock"></div>
    <div id="nuvio-parental"></div>
    <div id="nuvio-pause" class="nuvio-general-card"></div>
    <div id="nuvio-recommendation" class="nuvio-general-card"></div>
    <div id="nuvio-still" class="nuvio-general-card"></div>
    <!-- Bottom Netflix Controller Bar -->''')
    css = app/'assets/rml/playback.rcss'
    css.write_text(css.read_text() + (HERE/'ps5-general.rcss').read_text())
