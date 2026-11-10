"""Transfer browser subtitle candidates to EVO's existing online picker."""
from pathlib import Path

HERE = Path(__file__).parent


def patch_online_source(source):
    from native_subtitles import _replace
    source = _replace(source, 'static int  g_fetch_busy;',
                      'static unsigned g_generation, g_fetch_generation;\nstatic int  g_fetch_busy;')
    source = _replace(source, '    g_count = 0;',
                      '    ++g_generation;\n    g_fetch_done = 0;\n    g_count = 0;')
    source = _replace(source, '    g_fetch_index = i;',
                      '    g_fetch_generation = g_generation;\n    g_fetch_index = i;')
    source = _replace(source, '    char url[EVO_OSUB_URL], path[512];',
                      '    char url[EVO_OSUB_URL], path[512];\n    unsigned generation;')
    source = _replace(source, '    snprintf(url, sizeof url, "%s", g_fetch_url);',
                      '    generation = g_fetch_generation;\n    snprintf(url, sizeof url, "%s", g_fetch_url);')
    source = _replace(source, '    g_fetch_done = rc == 0 ? 1 : -1;',
                      '    g_fetch_done = generation == g_generation ? (rc == 0 ? 1 : -1) : 0;')
    source = _replace(source, '            fclose(f);',
                      '            if (fclose(f) != 0) ok = 0;')
    return source + '''
void evo_osubs_cancel_fetch(void)
{
    pthread_mutex_lock(&g_mu);
    ++g_generation;
    g_fetch_done = 0;
    pthread_mutex_unlock(&g_mu);
}
'''


def patch_controller_source(source):
    from native_subtitles import _replace
    source = _replace(source,
        '    /* The same title again (audio switch, reopen): restore what was loaded. */',
        '    if (prospero_subtitle_requested_stream >= 0) return; /* explicit embedded choice */\n\n'
        '    /* The same title again (audio switch, reopen): restore what was loaded. */')
    return _replace(source,
        '    if (prospero_subtitle_count > 0)\n        return;                       /* a sidecar is already loaded */',
        '    if (m_source.provider == "web") return; /* candidates are picker-owned */\n'
        '    if (prospero_subtitle_count > 0)\n        return;                       /* a sidecar is already loaded */')


def patch_local_file_source(source):
    from native_subtitles import _replace
    source = _replace(source, '#include "evo_subtitle.h"',
                      '#include "evo_subtitle.h"\n#include "evo_online_subs.h"')
    return _replace(source, '    }\n    EVO_LOGI("subtitles", "picked %s: %d cues", r.path.c_str(), cues);',
                    '    }\n    /* A successful local choice supersedes online ownership and downloads.\n'
                    '     * Failed file selections above leave that ownership unchanged. */\n'
                    '    evo_osubs_cancel_fetch();\n'
                    '    evo_osubs_set_active(-1);\n'
                    '    EVO_LOGI("subtitles", "picked %s: %d cues", r.path.c_str(), cues);')


def patch_repository_source(source):
    from native_subtitles import _replace
    source = _replace(source, '        return this.supportsType(resource, normalizedType, normalizedId);',
                      '''        if (!globalThis.__NUVIO_PS5__)
          return this.supportsType(resource, normalizedType, normalizedId);
        return this.buildActualIdCandidates(normalizedType, idCandidates, videoId, {
          ...options, idPrefixes: addon?.idPrefixes
        }).some((candidate) => this.supportsType(resource, normalizedType, candidate));''')
    # Like streamRepository's onChunk option, publish successful request
    # chunks. Do not wait for all addons or later IDs within the same addon.
    source = _replace(source, '      subtitles.forEach((subtitle) => {',
                      '      const chunk = [];\n      subtitles.forEach((subtitle) => {')
    source = _replace(source, '        merged.push(subtitle);',
                      '        merged.push(subtitle);\n        chunk.push(subtitle);')
    return _replace(source, '      });\n    }\n\n    return merged;', '''      });
      if (globalThis.__NUVIO_PS5__ && chunk.length && typeof options?.onChunk === "function") {
        try {
          options.onChunk({ status: "success", data: chunk });
        } catch (_) {
          console.warn("Subtitle chunk callback failed");
        }
      }
    }

    return merged;''')


def patch_loader_source(source):
    from native_subtitles import _replace
    source = _replace(source, 'import * as internals from "./playerScreenContext.js";',
                      'import * as internals from "./playerScreenContext.js";\n'
                      'import { ProfileManager } from "../../../core/profile/profileManager.js";\n'
                      'import { Router } from "../../navigation/router.js";')
    source = _replace(source, '    async loadSubtitles() {', '''    loadSubtitles() {
      if (!globalThis.__NUVIO_PS5__) return this.ps5LoadSubtitles();
      // Initial mount starts playback BEFORE its own discovery call. The
      // native hook can already be awaiting discovery by then. Reuse that
      // request instead of invalidating its subtitleLoadToken with a second.
      const url = this.activePlaybackUrl;
      const params = this.params;
      const identity = JSON.stringify([params?.itemId, params?.contentId, params?.videoId,
        params?.itemType, params?.season, params?.episode, this.playerMountToken,
        ProfileManager.getActiveProfileId(), this.getCurrentStreamCandidate?.()?.id]);
      if (this.ps5SubtitleLoadPromise && this.ps5SubtitleLoadUrl === url &&
          this.ps5SubtitleLoadParams === params && this.ps5SubtitleLoadIdentity === identity) {
        return this.ps5SubtitleLoadPromise;
      }
      this.ps5SubtitleLoadUrl = url;
      this.ps5SubtitleLoadParams = params;
      this.ps5SubtitleLoadIdentity = identity;
      const promise = this.ps5LoadSubtitles();
      this.ps5SubtitleLoadPromise = promise;
      const clear = () => {
        if (this.ps5SubtitleLoadPromise === promise) this.ps5SubtitleLoadPromise = null;
      };
      promise.then(clear, clear);
      return promise;
    },
    async ps5LoadSubtitles() {''')
    source = _replace(source, '      const requestToken = (this.subtitleLoadToken || 0) + 1;',
                    '''      // Mount initialization resets subtitleLoadToken. Keep PS5 requests
      // monotonic so a previous mount cannot complete into this one's list.
      const requestToken = globalThis.__NUVIO_PS5__
        ? (this.ps5SubtitleRequestToken || 0) + 1 : (this.subtitleLoadToken || 0) + 1;
      if (globalThis.__NUVIO_PS5__) this.ps5SubtitleRequestToken = requestToken;''')
    # Share the actual preferred-language filter and merge for partial and
    # final publications, rather than maintaining a second filtering policy.
    start = '        const subtitleSettings = PlayerSettingsStore.get();\n'
    end = '        this.refreshTrackDialogs();\n      } catch (error) {'
    if source.count(start) != 1 or source.count(end) != 1:
        raise RuntimeError('Pinned subtitle publication region changed')
    publication = start + source.split(start, 1)[1].split(end, 1)[0] + '        this.refreshTrackDialogs();\n'
    source = _replace(source, publication, '        publishSubtitles(repositorySubtitles);\n')
    source = _replace(source, '      const subtitleLookup = this.buildSubtitleLookupContext();', '''      const subtitleLookup = this.buildSubtitleLookupContext();
      const ps5 = globalThis.__NUVIO_PS5__;
      const params = this.params, mount = this.playerMountToken;
      const routeParams = ps5 ? Router.currentParams : null;
      const profile = ps5 ? ProfileManager.getActiveProfileId() : null;
      const identity = () => JSON.stringify([params?.itemId, params?.contentId, params?.videoId,
        params?.itemType, params?.season, params?.episode]);
      const initialIdentity = identity();
      const selection = () => String(this.activePlaybackUrl || "") + "|" +
        String(this.getCurrentStreamCandidate?.()?.id || "");
      const selected = selection();
      const current = () => requestToken === this.subtitleLoadToken && (!ps5 ||
        (this.params === params && this.playerMountToken === mount && identity() === initialIdentity &&
         ProfileManager.getActiveProfileId() === profile && selection() === selected &&
         Router.current === "player" && Router.currentParams === routeParams && Router.getCurrentScreen() === this));
      let partialSubtitles = [];
      const publishSubtitles = (repositorySubtitles) => {
        if (!current()) return;
''' + publication + '''      };''')
    source = _replace(source, '                season: subtitleLookup.season,', '''                ...(ps5 ? { onChunk: (result) => {
                  if (!current() || result?.status !== "success" || !Array.isArray(result.data)) return;
                  partialSubtitles = this.mergeSubtitleCandidates(partialSubtitles, result.data);
                  publishSubtitles(partialSubtitles);
                } } : {}),
                season: subtitleLookup.season,''')
    source = _replace(source, '        if (requestToken !== this.subtitleLoadToken) {',
                      '        if (!current()) {')
    source = _replace(source, '        console.error("Subtitle attach failed", error);',
                      '        if (!current()) return;\n        console.error("Subtitle attach failed", error);')
    return _replace(source, '        if (requestToken === this.subtitleLoadToken) {',
                    '        if (current()) {')


def patch_frontend(nuvio):
    from polish import replace
    app = nuvio / 'js/app.js'
    replace(app, 'let hasSelectedProfileThisSession = false;',
            'let hasSelectedProfileThisSession = false;\n' + (HERE / 'ps5-subtitles.js').read_text())
    loader = nuvio / 'js/ui/screens/player/playerScreenMethods-68-load-subtitles.js'
    loader.write_text(patch_loader_source(loader.read_text()))
    repository = nuvio / 'js/data/repository/subtitleRepository.js'
    repository.write_text(patch_repository_source(repository.read_text()))


def patch_native(app):
    from polish import replace
    web = app / 'src/evo_webui.c'
    replace(web, 'static void serve_evo(int fd, const char *path)',
            (HERE / 'ps5-subtitles.c').read_text() + '\nstatic void serve_evo(int fd, const char *path)')
    replace(web, '        if (!strncmp(path, "/evo/speedtest/", 15))',
            '''        if (!strcmp(path, "/evo/subtitles"))
            serve_subtitles(fd, method, req, got, hl);
        else if (!strncmp(path, "/evo/speedtest/", 15))''')
    replace(web, '        presentation_handoff(s_h_progress_session);',
            '        presentation_handoff(s_h_progress_session);\n        subtitles_handoff(s_h_progress_session);')
    replace(web, '            s_play_presentation = s_h_presentation;',
            '            s_play_presentation = s_h_presentation;\n            s_play_subtitles = s_h_subtitles;')
    replace(web, "window.__nuvioPreparePresentation?window.__nuvioPreparePresentation():Promise.resolve(true)]",
            "window.__nuvioPreparePresentation?window.__nuvioPreparePresentation():Promise.resolve(true),"
            "window.__nuvioPrepareSubtitles?window.__nuvioPrepareSubtitles():Promise.resolve(true)]")
    replace(web, 'if(v[1]!==null)play(v[0]);', 'if(v[1]!==null&&v[2]!==null)play(v[0]);')
    replace(web, 'if(ok)launch();else done=0;',
            'if(ok&&window.__nuvioSendSubtitles){window.__nuvioSendSubtitles(session).then(function(sent){if(sent)launch();else done=0;});}'
            'else if(ok)launch();else done=0;')
    header = app / 'include/evo_webui.h'
    header.write_text(header.read_text() + '\n#ifdef __cplusplus\nextern "C"\n#endif\n'
                      'void evo_webui_import_subtitles(char *key, size_t cap);\n')
    replace(app / 'core/src/Application.cpp', '        g_web_src.provider = "web";',
            '''        g_web_src.provider = "web";
        char subtitleKey[80];
        evo_webui_import_subtitles(subtitleKey, sizeof subtitleKey);
        g_web_src.item_id = subtitleKey;
        prospero_subtitle_requested_stream = -2; /* new browser playback, not an audio reopen */''')
    # Offer browser candidates in the picker without inventing a browser track
    # choice or changing its off/embedded selection. Restore explicit online
    # picks on audio reopen through the existing remembered-track path.
    controller = app / 'core/src/services/PlaybackController.cpp'
    controller.write_text(patch_controller_source(controller.read_text()))
    online = app / 'addons/src/evo_online_subs.c'
    online.write_text(patch_online_source(online.read_text()))
    header = app / 'addons/include/evo_online_subs.h'
    replace(header, 'int  evo_osubs_fetching(void);',
            'int  evo_osubs_fetching(void);\nvoid evo_osubs_cancel_fetch(void);')
    replace(app / 'core/src/screens/SubtitlePickerScreen.cpp', '    if (trackId <= kOnlineBase) {',
            '    if (trackId > kOnlineBase) evo_osubs_cancel_fetch();\n'
            '    if (trackId <= kOnlineBase) {')
    replace(app / 'core/src/screens/SubtitlePickerScreen.cpp',
            '    // An embedded track toasts its own language and codec as it opens.',
            '    if (trackId > kOnlineBase) evo_osubs_set_active(-1);\n'
            '    // An embedded track toasts its own language and codec as it opens.')
    local = app / 'core/src/screens/SubtitleFileScreen.cpp'
    local.write_text(patch_local_file_source(local.read_text()))
    replace(app / 'core/src/screens/PlayerScreen.cpp',
            '    prospero_subtitle_use_external = 1;\n    prospero_subtitle_enabled = 1;',
            '    prospero_subtitle_select_primary(-1);')
    replace(app / 'core/include/evo/screens/SubtitlePickerScreen.hpp',
            '    static constexpr int kMaxOnlineRows = 24;',
            '    static constexpr int kMaxOnlineRows = 32;')
