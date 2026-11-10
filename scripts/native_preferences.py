"""Apply AFTER native_subtitles and subtitle_handoff, on the pinned sources.

No independent endpoint, profile ID, settings write, URL cache, second media
reader, or browser track-index mapping. Each import replaces the entire policy.
"""
from pathlib import Path

HERE = Path(__file__).parent


def _replace(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError('Pinned native profile preference anchor changed: ' + old[:90])
    return source.replace(old, new)


def patch_frontend_source(source):
    source = _replace(source, 'let ps5NativeSubtitles = null;',
                      (HERE / 'ps5-preferences.js').read_text() + '\nlet ps5NativeSubtitles = null;')
    source = _replace(source, '  const initialIdentity = identity();',
                      '  const initialIdentity = identity();\n'
                      '  let preferences = null, preferenceIdentity = null;')
    source = _replace(source, 'selection() === selected && identity() === initialIdentity;',
                      'selection() === selected && identity() === initialIdentity &&\n'
                      '    (preferenceIdentity === null ||\n'
                      '      JSON.stringify(ps5CaptureNativePreferences(screen)) === preferenceIdentity);')
    source = _replace(source, '  const entries = [];',
                      '  // Resolve after bounded discovery: original-language metadata may\n'
                      '  // arrive while discovery is pending. Profile/source guards still\n'
                      '  // cover that wait; the resolved policy is frozen for prepare/send.\n'
                      '  preferences = ps5CaptureNativePreferences(screen);\n'
                      '  preferenceIdentity = JSON.stringify(preferences);\n'
                      '  const entries = [];')
    source = _replace(source, 'source: ps5GeneralText(item.addonName || "Addon", 63) });',
                      'source: ps5GeneralText(item.addonName || "Addon", 63),\n'
                      '      forced: ps5NativeSubtitleForced(screen, item) });')
    source = _replace(source, 'ps5NativeSubtitles = { current, entries };',
                      'ps5NativeSubtitles = { current, entries, preferences };')
    return _replace(source, 'JSON.stringify({ session, subtitles: prepared.entries })',
                    'JSON.stringify({ session, subtitles: prepared.entries,\n'
                    '    ...(prepared.preferences ? { preferences: prepared.preferences } : {}) })')


def patch_web_source(source):
    source = _replace(source, '#include "evo_online_subs.h"',
                      '#include "evo_online_subs.h"\n#include "ps5-preferences.h"')
    source = _replace(source, '    evo_osub_t entries[EVO_OSUB_MAX];',
                      '    evo_osub_t entries[EVO_OSUB_MAX];\n'
                      '    nuvio_preferences_t preferences;\n    int forced[EVO_OSUB_MAX];')
    source = _replace(source, '    if (ok) ok = p->session[0]',
                      '    if (ok) ok = nuvio_preferences_decode(\n'
                      '        cJSON_GetObjectItemCaseSensitive(root, "preferences"), &p->preferences);\n'
                      '    if (ok) ok = p->session[0]')
    source = _replace(source, '        if (ok) ++p->count;',
                      '        const cJSON *forced = cJSON_GetObjectItemCaseSensitive(item, "forced");\n'
                      '        if (forced && !cJSON_IsBool(forced)) ok = 0;\n'
                      '        /* Cache insertion deduplicates URLs; reject duplicates here so\n'
                      '         * candidate classification cannot shift to another cache row. */\n'
                      '        for (int j = 0; ok && j < p->count; ++j)\n'
                      '            if (!strcmp(p->entries[j].url, s->url)) ok = 0;\n'
                      '        if (ok) { p->forced[p->count] = cJSON_IsTrue(forced); ++p->count; }')
    return _replace(source, '    memset(&s_play_subtitles, 0, sizeof s_play_subtitles);',
                    '    nuvio_preferences_import(s_play_subtitles.session, &s_play_subtitles.preferences,\n'
                    '                             s_play_subtitles.forced, s_play_subtitles.count);\n'
                    '    memset(&s_play_subtitles, 0, sizeof s_play_subtitles);')


def patch_subtitle_source(source):
    source = _replace(source, '#include "evo_subtitle.h"',
                      '#include "evo_subtitle.h"\n#include "ps5-preferences.h"\n#include "evo_online_subs.h"')
    return source + '''
/* Capture before stopPlayback/clear; stack lifetime, no extra private storage. */
void nuvio_preferences_capture(nuvio_preferences_snapshot *out, int audio)
{
    memset(out, 0, sizeof *out);
    out->valid = 1;
    out->audio = audio;
    out->enabled = prospero_subtitle_enabled;
    out->external = prospero_subtitle_use_external;
    out->subtitle = prospero_embedded_subtitle_stream_index;
    snprintf(out->path, sizeof out->path, "%s", prospero_subtitle_path);
    snprintf(out->label, sizeof out->label, "%s", prospero_subtitle_external_label);
    /* Picker scratch files can be overwritten by a later failed download.
     * The cache already owns a stable copy of the successfully loaded online
     * choice. Never use it to replace a later explicit embedded selection. */
    if (out->external && evo_osubs_active() >= 0)
        evo_osubs_remembered(out->path, sizeof out->path, out->label, sizeof out->label);
}
'''


def patch_controller_source(source):
    source = _replace(source, '#include "evo_langpref.h"',
                      '#include "evo_langpref.h"\n#include "ps5-preferences.h"')
    source = _replace(source, '''    const std::string rawUrl = source.url;
    if (rawUrl.empty()) {
        return false;
    }

    stopPlayback();''', '''    const std::string rawUrl = source.url;
    if (rawUrl.empty()) {
        return false;
    }

    const bool profilePolicy = nuvio_preferences_active(source.provider.c_str(), source.item_id.c_str());
    nuvio_preferences_snapshot profileReopen{};
    if (profilePolicy && !m_currentFilePath.empty() && m_source.provider == source.provider &&
        m_source.item_id == source.item_id && m_source.url == rawUrl)
        nuvio_preferences_capture(&profileReopen, audio_stream_index);
    stopPlayback();''')
    source = _replace(source, 'if (chosen_program < 0 && evo_langpref_audio()[0]) {',
                      'if (!profilePolicy && chosen_program < 0 && evo_langpref_audio()[0]) {')
    source = _replace(source, '    if (m_requestedAudioStream >= 0 &&',
                      '    if (profilePolicy)\n'
                      '        audio_stream_index = nuvio_preferences_audio(play_fmt, audio_stream_index,\n'
                      '                                                       chosen_program, &profileReopen);\n'
                      '    if (m_requestedAudioStream >= 0 &&')
    start = '    // Subtitle setup\n'
    end = '    applyOnlineSubtitles();'
    if source.count(start) != 1 or source.count(end) != 1:
        raise RuntimeError('Pinned profile subtitle setup region changed')
    before, setup = source.split(start, 1)
    setup, after = setup.split(end, 1)
    return before + start + '''    if (profilePolicy) {
        nuvio_preferences_subtitles(play_fmt, audio_stream_index, &profileReopen);
        prospero_secondary_subtitle_open(play_fmt);
    } else {
''' + setup + end + '\n    }' + after


def patch_frontend(nuvio):
    path = nuvio / 'js/app.js'
    path.write_text(patch_frontend_source(path.read_text()))


def patch_native(app):
    # Validate every transformation before writing anything, including files
    # introduced by this adapter. Repeat application and source drift fail shut.
    changes = {}
    makefile = app / 'Makefile'
    changes[makefile] = _replace(makefile.read_text(), '    src/evo_webui.c \\\n',
                                '    src/evo_webui.c \\\n    src/ps5-preferences.c \\\n')
    for relative, patch in (
        ('src/evo_webui.c', patch_web_source),
        ('media/src/evo_subtitle.c', patch_subtitle_source),
        ('core/src/services/PlaybackController.cpp', patch_controller_source),
    ):
        path = app / relative
        changes[path] = patch(path.read_text())
    for name, directory in (('ps5-preferences.h', 'include'), ('ps5-preferences.c', 'src')):
        changes[app / directory / name] = (HERE / name).read_text()
    for path, source in changes.items():
        path.write_text(source)
