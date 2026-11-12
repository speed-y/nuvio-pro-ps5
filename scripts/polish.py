"""Native Nuvio shell around the existing browser/native playback lifetimes."""
from pathlib import Path
import os
import shutil


def replace(path,old,new):
    source=path.read_text()
    if source.count(old)!=1:raise RuntimeError('Pinned polish anchor changed: '+str(path))
    path.write_text(source.replace(old,new))


def apply(evo,nuvio):
    app=evo/'projects/evoplayer'
    web=app/'src/evo_webui.c'
    # WebBrowserDialogParam carries an undocumented `animation` field that
    # upstream never sets. The 2026-10-03 investigation tries values here to
    # find out whether it softens the dialog's white first frame; 0 is upstream.
    animation=os.environ.get('NUVIO_WEBUI_ANIMATION','0')
    if not animation.isdigit():
        raise RuntimeError('NUVIO_WEBUI_ANIMATION must be a number')
    replace(web,'    LOG("Open url=%s ...", url);',
            '    s_param.animation = '+animation+';\n    LOG("Open url=%s ...", url);')
    replace(web,'static char s_hook_profile[16];','static int s_native_requested;\nstatic char s_hook_profile[16];')
    replace(web,'        s_close_req = 1;','        s_close_req = 1;\n        s_native_requested = 1;')
    replace(web,'    s_hook_seen = 0;', '    s_hook_seen = 0;\n    s_native_requested = 0;')
    web.write_text(web.read_text()+"\nint evo_webui_native_requested(void) {\n    pthread_mutex_lock(&s_mx);\n    int result = s_native_requested;\n    pthread_mutex_unlock(&s_mx);\n    return result;\n}\n")
    h=app/'include/evo_webui.h';h.write_text(h.read_text()+'\n#ifdef __cplusplus\nextern "C"\n#endif\nint evo_webui_native_requested(void);\n')
    replace(web,"b.textContent='Back to EVO'", "b.textContent='Player settings'")
    replace(web,'font:24px sans-serif;', 'font-size:24px;font-family:inherit;')
    web.write_text(fix_playback_handoff(web.read_text()))
    patch_playback_start(app)
    patch_playback_restart_diagnostics(app)
    patch_playback_read_diagnostics(app)
    patch_playback_progress(app)
    patch_playback_skip(app)
    patch_next_episode(app)
    patch_playback_hui(app)
    web.write_text(patch_controller_hook(web.read_text()))
    web.write_text(patch_storage_hook(web.read_text()))
    header=app/'ui_rml/include/evo_rmlui_app.h'
    replace(header,'    void RenderLaunch(uint32_t* framebuffer, int width, int height);','    void RenderLaunch(uint32_t* framebuffer, int width, int height);\n    void RenderNuvio(uint32_t* framebuffer, int width, int height, const char* message);')
    replace(header,'    Rml::ElementDocument* m_launch_doc = nullptr;','    Rml::ElementDocument* m_nuvio_doc = nullptr;\n    Rml::ElementDocument* m_launch_doc = nullptr;')
    cpp=app/'ui_rml/src/evo_rmlui_app.cpp'
    replace(cpp,'        m_closed_doc,','        m_closed_doc, m_nuvio_doc,')
    replace(cpp,'        if (!m_launch_doc) {','        if (!m_nuvio_doc) {\n            m_nuvio_doc = m_context->LoadDocument(p + "nuvio.rml");\n            if (m_nuvio_doc) m_nuvio_doc->Hide();\n        }\n        if (!m_launch_doc) {')
    cpp.write_text(cpp.read_text()+r'''
void EvoRmlApp::RenderNuvio(uint32_t* framebuffer, int width, int height, const char* message) {
    if (!m_context || !m_nuvio_doc) return;
    ShowOnlyScreen(m_nuvio_doc);
    if (m_nav_doc) m_nav_doc->Hide();
    Rml::Element* status = m_nuvio_doc->GetElementById("nuvio-status");
    if (status && status->GetInnerRML() != (message ? message : "Opening Nuvio Pro"))
        status->SetInnerRML(message ? message : "Opening Nuvio Pro");
    m_context->Update();
    RenderCachedScreen(30, framebuffer, width, height);
}
''')
    bridge=app/'ui_rml/src/evo_rmlui_bridge.cpp'
    bridge.write_text(bridge.read_text()+'\nextern "C" void evo_rmlui_render_nuvio(uint32_t* framebuffer,int width,int height,const char* message) {\n    EvoRmlApp::Instance().RenderNuvio(framebuffer,width,height,message);\n}\n')
    h=app/'ui_rml/include/evo_rmlui_bridge.h'
    # This bridge header already scopes all declarations as extern C.
    replace(h,'void evo_rmlui_render_launch(uint32_t* framebuffer, int width, int height);','void evo_rmlui_render_launch(uint32_t* framebuffer, int width, int height);\nvoid evo_rmlui_render_nuvio(uint32_t* framebuffer, int width, int height, const char* message);')
    player=app/'core/src/screens/PlayerScreen.cpp'
    player.write_text(fix_player_back(player.read_text()))
    patch_playback_end(app)
    application=app/'core/src/Application.cpp'
    replace(application, 'if ((seen_active && !active) || (!seen_active && ++frames > 600)) {', 'if ((seen_active && !active) || (!seen_active && ++frames > 300)) {')
    # Browser L3 belongs to Search. Preserve the native screenshot shortcut
    # everywhere else; its original handler runs before our browser bridge.
    replace(application,
        '            if ((pressed & PadButtons::L3) || ((pressed & PadButtons::R3) && !r3IsChapters && !r3ToKeyboard)) {',
        '            if (((pressed & PadButtons::L3) && !evo_webui_active()) || ((pressed & PadButtons::R3) && !r3IsChapters && !r3ToKeyboard)) {')
    replace(application, '''            if (evo_webui_active()) {
                /* #101: the system browser is up and owns the controller. */''', '''            if (evo_webui_active()) {
                /* Keep physical D-pad/X/Circle with the browser. Either stick
                 * supplies one dominant direction through the native bridge. */
                int x = static_cast<int>(padData.leftStick.x) - 128;
                int y = static_cast<int>(padData.leftStick.y) - 128;
                if (std::abs(x) <= 70 && std::abs(y) <= 70) {
                    x = static_cast<int>(padData.rightStick.x) - 128;
                    y = static_cast<int>(padData.rightStick.y) - 128;
                }
                uint32_t stick = 0;
                if (std::abs(x) > 70 || std::abs(y) > 70) {
                    if (std::abs(x) >= std::abs(y))
                        stick = x < 0 ? PadButtons::Left : PadButtons::Right;
                    else
                        stick = y < 0 ? PadButtons::Up : PadButtons::Down;
                }
                static evo_input browserSticks;
                evo_input_update(&browserSticks, stick, static_cast<uint64_t>(now_ms()));
                int direction = evo_input_fired(&browserSticks, EVO_ACT_UP) ? 1 :
                    evo_input_fired(&browserSticks, EVO_ACT_RIGHT) ? 2 :
                    evo_input_fired(&browserSticks, EVO_ACT_DOWN) ? 3 :
                    evo_input_fired(&browserSticks, EVO_ACT_LEFT) ? 4 : 0;
                evo_webui_controller(pressed & PadButtons::Options,
                                     pressed & PadButtons::Triangle, direction,
                                     pressed & PadButtons::R2 ? 2 : (pressed & PadButtons::L3 ? 1 :
                                     (pressed & PadButtons::L1 ? 3 : (pressed & PadButtons::R1 ? 4 : 0))));''')
    h=app/'include/evo_webui.h'
    h.write_text(h.read_text()+'\n#ifdef __cplusplus\nextern "C"\n#endif\nvoid evo_webui_controller(int options, int menu, int direction, int shortcut);\n')
    replace(application,'std::atomic<bool> g_web_done{false};','std::atomic<bool> g_web_done{false};\nbool g_nuvio_preparing = false;')
    replace(application,'        g_web_src = PlaybackSource();','        g_nuvio_preparing = true;\n        g_web_src = PlaybackSource();')
    replace(application,'        pthread_join(g_web_thread, nullptr);','        pthread_join(g_web_thread, nullptr);\n        g_nuvio_preparing = false;')
    replace(application,'        bool isSurround = (m_screenManager->getCurrentScreenId() == ScreenId::SurroundTest);','        bool nuvioShell = !isPlayer &&\n            !(m_playbackController && m_playbackController->isActive()) &&\n            !evo_webui_native_requested();\n        bool isSurround = (m_screenManager->getCurrentScreenId() == ScreenId::SurroundTest);')
    replace(application,'int uiActive = (frame < 10) || isPlayer || isSurround || hasInput || hasAnim ||','int uiActive = nuvioShell || evo_webui_active() || (frame < 10) || isPlayer || isSurround || hasInput || hasAnim ||')
    source=application.read_text();anchor='                m_screenManager->render(m_uiScratch, DisplayWidth, DisplayHeight);'
    if source.count(anchor)!=2:raise RuntimeError('Pinned render branches changed')
    before,after=source.rsplit(anchor,1)
    application.write_text(before+'''                if (nuvioShell)
                    evo_rmlui_render_nuvio(m_uiScratch, DisplayWidth, DisplayHeight,
                        g_nuvio_preparing ? "Preparing playback" : "Opening Nuvio Pro");
                else
                    m_screenManager->render(m_uiScratch, DisplayWidth, DisplayHeight);'''+after)
    asset=Path(__file__).resolve().parent.parent/'assets'
    shutil.copyfile(asset/'nuvio.rml',app/'assets/rml/nuvio.rml')
    shutil.copyfile(nuvio/'assets/brand/app_logo_wordmark.png',app/'assets/icons/nuvio-wordmark.png')
    # Fixed-size repository artwork: the title icon and the launch screens.
    shutil.copyfile(asset/'icon.png',app/'sce_sys/icon0.png')
    for name in ('pic0.png','pic1.png'):
        shutil.copyfile(asset/'launch.png',app/'sce_sys'/name)
    import native_general
    native_general.patch_native(app)
    patch_speedtest(app)
    import native_playback
    import native_subtitles
    native_playback.patch_native(app)
    native_subtitles.patch_native(app)
    import subtitle_handoff
    subtitle_handoff.patch_native(app)
    import native_preferences
    native_preferences.patch_native(app)
    import native_skin
    native_skin.patch_native(app)


def patch_speedtest(app):
    web = app/'src/evo_webui.c'
    replace(web, 'static void serve_evo(int fd, const char *path)',
        (Path(__file__).parent/'ps5-speedtest.c').read_text() +
        '\nstatic void serve_evo(int fd, const char *path)')
    replace(web, '        if (!strcmp(path, "/evo/presentation"))',
        '''        if (!strncmp(path, "/evo/speedtest/", 15))
            serve_speedtest(fd, method, path);
        else if (!strcmp(path, "/evo/progress") || !strncmp(path, "/evo/progress?", 14)) {
            tlog("progress route");
            playback_progress_serve(fd, path);
        }
        else if (!strcmp(path, "/evo/presentation"))''')
    replace(web, '    s_srv_stop = 1;', '    speedtest_suspend();\n    s_srv_stop = 1;')
    replace(web, '    s_state = P_RUN;\n    s_frames = 0;',
        '    speedtest_resume();\n    s_state = P_RUN;\n    s_frames = 0;')
    replace(web, '        tlog("close requested by the page");',
        '        speedtest_suspend();\n        tlog("close requested by the page");')
    replace(web, '        s_handoff_ready = url[0] != 0;',
        '        if (url[0]) speedtest_suspend();\n        s_handoff_ready = url[0] != 0;')
    replace(web, '    if (!s_play_pending) return 0;',
        '    if (!s_play_pending || !speedtest_quiet()) return 0;')


def patch_storage_hook(source):
    old=r'''"var lastSnap='';"
"function snap(){var o={};try{for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i),v=localStorage.getItem(k);"
" if(v!==null&&v.length<=524288)o[k]=v;}}catch(e){}return JSON.stringify(o);}"
"try{if(!sessionStorage.getItem('__evoRestored')){var sx=new XMLHttpRequest();sx.open('GET','/evo/storage',false);sx.send(null);"
" if(sx.status===200){var so=JSON.parse(sx.responseText||'{}');localStorage.clear();"
"  for(var sk in so){if(Object.prototype.hasOwnProperty.call(so,sk))localStorage.setItem(sk,so[sk]);}"
"  sessionStorage.setItem('__evoRestored','1');}}}catch(e){}"
"lastSnap=snap();"
"function saveNow(kind){try{var sv=snap();if(sv===lastSnap)return;lastSnap=sv;"
" if(kind===2&&navigator.sendBeacon){navigator.sendBeacon('/evo/storage',sv);return;}"
" var x=new XMLHttpRequest();x.open('POST','/evo/storage',kind!==1);x.setRequestHeader('Content-Type','application/json');x.send(sv);}catch(e){}}"'''
    if source.count(old)!=1:
        raise RuntimeError('Pinned storage hook changed')
    # Missing keys are safe only after the frontend's explicit removeItem/clear.
    # SessionStore and accountLocalDataReset use those APIs for sign-out; tracking
    # successful mutations avoids mistaking an empty teardown read for a reset.
    # Fail closed for this document if restore or mutation tracking fails.
    # Serialize acknowledged loopback writes, including lifecycle attempts. A
    # beacon's true result is only queue acceptance, not a write acknowledgement;
    # mixing it with POST permits an older request to overwrite a newer snapshot.
    # Browsers that reject sync XHR during teardown retain the prior disk state
    # and retry on the next timer/explicit save if the document survives.
    new=r'''/* Storage reads must be complete; an unavailable store is not an empty store.
 * Explicit Storage mutations authorize deletions, including sign-out/reset.
 * Only an acknowledged, serialized loopback POST advances lastSnap. */
"var lastSnap=null,storeReady=false,ls=null,known=Object.create(null);"
"function snap(){try{var o=Object.create(null),seen=Object.create(null),n=ls.length;"
" for(var i=0;i<n;i++){var k=ls.key(i);if(k===null||seen[k])return null;var v=ls.getItem(k);"
"  if(v===null)return null;seen[k]=true;if(v.length<=524288)o[k]=v;}"
" if(ls.length!==n)return null;for(var k in known){if(!seen[k])return null;}"
" known=seen;return JSON.stringify(o);}catch(e){return null;}}"
"try{ls=localStorage;if(!sessionStorage.getItem('__evoRestored')){"
" var sx=new XMLHttpRequest();sx.open('GET','/evo/storage',false);sx.send(null);"
" if(sx.status!==200)throw Error('Storage restore unavailable');var so=JSON.parse(sx.responseText);"
" if(!so||typeof so!=='object'||Array.isArray(so))throw Error('Invalid saved storage');"
" for(var sk in so){if(typeof so[sk]!=='string')throw Error('Invalid saved value');known[sk]=true;}"
" ls.clear();for(var sk in so){ls.setItem(sk,so[sk]);}"
" for(var sk in so){if(ls.getItem(sk)!==so[sk])throw Error('Incomplete storage restore');}"
" sessionStorage.setItem('__evoRestored','1');}"
" lastSnap=snap();if(lastSnap===null)throw Error('Storage snapshot unavailable');"
" var sp=Storage.prototype;['setItem','removeItem','clear'].forEach(function(method){var original=sp[method];"
"  var wrapped=function(){var result=original.apply(this,arguments);if(this===ls){"
"   if(method==='clear')known=Object.create(null);else if(method==='removeItem')delete known[String(arguments[0])];"
"   else known[String(arguments[0])]=true;}return result;};sp[method]=wrapped;"
"  if(sp[method]!==wrapped)throw Error('Storage mutation tracking unavailable');});storeReady=true;"
"}catch(e){storeReady=false;}"
"function saveNow(kind){if(!storeReady)return;try{var sv=snap();if(sv===null||sv===lastSnap)return;"
" var x=new XMLHttpRequest();x.open('POST','/evo/storage',false);x.setRequestHeader('Content-Type','application/json');"
" x.send(sv);if(x.status===204)lastSnap=sv;}catch(e){}}"
"window.__nuvioFlushStorage=function(){saveNow(1);};"'''
    return source.replace(old,new)


def patch_resume_router(text):
    # Reuse Nuvio's route-resume semantics without enabling webOS services.
    guard='if (!Platform.isWebOS()) {'
    if text.count(guard)!=2:raise RuntimeError('Pinned route resume guards changed')
    text=text.replace(guard,'if (!Platform.isWebOS() && !globalThis.__NUVIO_PS5__) {')
    old='      if (!this.isWebOsResumeRouteRestorable(route)) {\n        LocalStore.remove(WEBOS_RESUME_ROUTE_KEY);'
    if text.count(old)!=1:raise RuntimeError('Pinned route exclusion changed')
    text=text.replace(old, '      if (!this.isWebOsResumeRouteRestorable(route)) {\n        if (globalThis.__NUVIO_PS5__) return;\n        LocalStore.remove(WEBOS_RESUME_ROUTE_KEY);')
    if text.count('!WEBOS_NON_RESTORABLE_ROUTES.has(route)') != 1:
        raise RuntimeError('Pinned restorable route predicate changed')
    text=text.replace('!WEBOS_NON_RESTORABLE_ROUTES.has(route)',
        '(!WEBOS_NON_RESTORABLE_ROUTES.has(route) || (globalThis.__NUVIO_PS5__ && ["detail", "stream"].includes(route)))')
    return text


def patch_home_dom(text):
    old='''  if (canUpdate) {
    updateChildren(container, source, focusedNode);'''
    if text.count(old) != 1:
        raise RuntimeError('Pinned Home DOM update anchor changed')
    return text.replace(old, '''  if (canUpdate) {
    // Focus changes and measured truncation replace these children outside
    // the renderer. Adopt them before diffing, rather than preserving them
    // as runtime-owned media and appending a second title/metadata block.
    // Leave logos, transition ghosts and trailer layers with their owners.
    registerHomeDomNodes(container.querySelectorAll(
      ".home-hero-title-text, .home-hero-copy > :not(.home-hero-brand), .home-hero-indicators"
    ));
    updateChildren(container, source, focusedNode);''')


def patch_detail_back(text):
    old='if (this.params?.returnHomeOnBack) {'
    search='if (this.params?.returnToSearchOnBack) {'
    if text.count(old)!=1 or text.count(search)!=1:
        raise RuntimeError('Pinned detail Back target changed')
    # Pop the existing Search entry instead of replacing Detail with another
    # Search page. The pending return handler runs before popstate suppression.
    text=text.replace(search, search+'''
        if (globalThis.__NUVIO_PS5__ && Router.popToExistingRoute?.("search", {})) return true;''')
    # A recreated browser can have no history predecessor. Reuse the existing
    # Home replacement without bypassing overlays or explicit Search returns.
    return text.replace(old,
        'if (this.params?.returnHomeOnBack || (globalThis.__NUVIO_PS5__ && Router.stack.length === 0)) {')


def patch_search_back(text):
    old='      return this.closePosterOptionsMenu();'
    if text.count(old)!=1:
        raise RuntimeError('Pinned Search Back target changed')
    return text.replace(old, '''      if (this.closePosterOptionsMenu()) return true;
      if (globalThis.__NUVIO_PS5__ && Router.stack.length === 0) {
        void Router.navigate("home", {}, { replaceHistory: true, skipStackPush: true });
        return true;
      }
      return false;''')


def patch_pin_shared_keys(text):
    old = '  if (\n    isEditableTarget(target) &&\n'
    new = '  if (\n    (isEditableTarget(target) || target?.closest?.("[data-overlay-root=\'pin\']")) &&\n'
    if text.count(old) != 1:
        raise RuntimeError('Pinned sharedKeys Backspace anchor changed')
    return text.replace(old, new)


def patch_pin_render_overlay(text):
    imp_old = 'import * as internals from "./profileSelectionScreen.js";'
    imp_new = (
        'import * as internals from "./profileSelectionScreen.js";\n'
        'import { ps5GlyphSvg } from "../../ui/navigation/ps5-text-input.js";'
    )
    hint_old = '<div class="profile-pin-back-hint">${escapeHtml(PROFILE_PIN_TEXT.back)}</div>'
    hint_new = '''<div class="profile-pin-back-hint">${globalThis.__NUVIO_PS5__
                  ? `<div class="ps5-pin-controls">${[["Dpad", "Navigate"], ["Cross", "Select"], ["Square", "Backspace"], ["Circle", "Cancel"]]
                      .map(([glyph, label]) => `<span class="ps5-control-hint"><span class="ps5-control-glyph" aria-hidden="true">${ps5GlyphSvg(glyph)}</span><span>${label}</span></span>`)
                      .join("")}</div>`
                  : escapeHtml(PROFILE_PIN_TEXT.back)}</div>'''
    if text.count(imp_old) != 1 or text.count(hint_old) != 1:
        raise RuntimeError('Pinned PIN render anchor changed')
    return text.replace(imp_old, imp_new).replace(hint_old, hint_new)


def patch_pin_submit_keydown(text):
    old = '''      if (code === 8 || code === 46 || key === "Backspace" || key === "Delete") {
        event?.preventDefault?.();
        if (!this.isPinOperationInProgress && this.pinValue) {
          this.pinValue = this.pinValue.slice(0, -1);
          this.pinOverlayError = "";
          this.render();
        }
        return true;
      }'''
    new = '''      if (code === 8 || code === 46 || key === "Backspace" || key === "Delete" ||
          (globalThis.__NUVIO_PS5__ && (code === 113 || key === "F2"))) {
        event?.preventDefault?.();
        if (event?.repeat && (code === 113 || key === "F2")) {
          return true;
        }
        if (!this.isPinOperationInProgress && this.pinValue) {
          this.pinValue = this.pinValue.slice(0, -1);
          this.pinOverlayError = "";
          this.pendingFocusKey = this.focusKey || this.getDefaultFocusKey();
          this.render();
        }
        return true;
      }'''
    if text.count(old) != 1:
        raise RuntimeError('Pinned PIN keydown anchor changed')
    return text.replace(old, new)


def patch_nuvio(nuvio):
    patch_stream_selection(nuvio)
    home_dom = nuvio/'js/ui/screens/home/homeDomUpdate.js'
    home_dom.write_text(patch_home_dom(home_dom.read_text()))
    replace(nuvio/'js/platform/adapters/browserAdapter.js',
        '    return "Web Browser";',
        '    return globalThis.__NUVIO_PS5__ ? "PS5" : "Web Browser";')
    replace(nuvio/'js/core/auth/deviceSessionRegistration.js',
        '  const platformName = normalizedText(platform.getName?.()).toLowerCase();',
        '''  if (runtime.__NUVIO_PS5__) {
    return { clientName: "Nuvio Pro", deviceName: "PS5", platform: "PS5" };
  }
  const platformName = normalizedText(platform.getName?.()).toLowerCase();''')
    replace(nuvio/'js/core/profile/profileSelectionScreenMethods-01-mount.js',
        't("profile_selection_hint", {}, "Hold to manage profile")',
        '(globalThis.__NUVIO_PS5__ ? "Press Square or Options to manage profile" : '
        't("profile_selection_hint", {}, "Hold to manage profile"))')
    for rel, fn in (
        ('js/platform/sharedKeys.js', patch_pin_shared_keys),
        ('js/core/profile/profileSelectionScreenMethods-03-render-pin-overlay.js', patch_pin_render_overlay),
        ('js/core/profile/profileSelectionScreenMethods-06-submit-completed-pin.js', patch_pin_submit_keydown),
    ):
        target = nuvio/rel
        target.write_text(fn(target.read_text()))
    # Form controls otherwise retain the browser's font instead of the theme.
    replace(nuvio/'css/base.css', '\n* {\n',
        '\nbutton,\ninput,\ntextarea,\nselect {\n  font-family: inherit;\n}\n\n* {\n')
    # These cards paint focus on their artwork. The constrained-mode group
    # must not add a second perimeter around the artwork and its text.
    for mode in ('performance-constrained', 'legacy-tizen'):
        artwork = ''.join(f'.{mode} .{card}.focused,\n' for card in
            ('series-episode-card', 'detail-morelike-card', 'movie-cast-card', 'series-cast-card'))
        tail = f'.{mode} .detail-company-card.focused,\n.{mode} .detail-comment-card.focused,'
        replace(nuvio/'css/components-60.css', artwork + tail, tail)
    replace(nuvio/'css/components-21.css', '.settings-account-signout-button {\n  min-height:',
        '''.settings-account-signout-button {
  width: auto;
  max-width: 100%;
  align-self: flex-start;
  min-height:''')
    for file, image in (('components-40.css', 'movie-cast-avatar-image'),
                        ('components-43.css', 'detail-morelike-poster-image')):
        replace(nuvio/'css'/file, f'.{image} {{',
            f'.{image}[hidden] {{\n  display: none;\n}}\n\n.{image} {{')
    navigation=nuvio/'js/ui/navigation'
    shutil.copyfile(Path(__file__).parent/'ps5-navigation.js', navigation/'ps5-navigation.js')
    shutil.copyfile(Path(__file__).parent/'ps5-text-input.js', navigation/'ps5-text-input.js')
    shutil.copyfile(Path(__file__).parent/'ps5-tv-remote.js', navigation/'ps5-tv-remote.js')
    with (nuvio/'css/components-60.css').open('a') as css:
        css.write('\n'+(Path(__file__).parent/'ps5-search-keyboard.css').read_text()+"""
.series-primary-btn,
.series-secondary-btn {
  box-sizing: border-box;
  height: auto;
  min-height: 4.2vw;
  padding: 1.1vw 2vw;
  border-radius: 999px;
  line-height: 1;
}
.series-primary-btn .series-btn-svg,
.series-primary-btn .series-btn-icon svg {
  width: 1.5vw;
  height: 1.5vw;
}
.series-primary-btn { overflow: visible; }
/* Give the top/left focus ring and scale on Detail hero buttons room inside
 * .detail-hero-body's overflow: hidden while keeping left alignment intact. */
.series-detail-actions {
  padding: 8px 6px 4px;
  margin-left: -6px;
}
/* Upstream PIN styles target <= 760px height or oversize px for 1080p.
 * Scale proportions smoothly across 720p/1080p and fit controller hints below. */
.profile-pin-overlay {
  padding: 28px 24px;
}
.profile-pin-heading {
  font-size: clamp(26px, 2.2vw, 40px);
  line-height: 1.2;
  margin: 0;
}
.profile-pin-box-row {
  gap: clamp(14px, 1.3vw, 22px);
  margin: clamp(22px, 2.5vh, 34px) 0 0;
}
.profile-pin-box {
  width: clamp(80px, 5.8vw, 108px);
  height: clamp(80px, 5.8vw, 108px);
  border-radius: clamp(14px, 1vw, 18px);
}
.profile-pin-dot {
  width: clamp(15px, 1.15vw, 20px);
  height: clamp(15px, 1.15vw, 20px);
}
.profile-pin-cursor {
  height: clamp(32px, 2.4vw, 44px);
}
.profile-pin-support {
  font-size: clamp(16px, 1.05vw, 20px);
  min-height: clamp(22px, 1.6vw, 28px);
  margin: clamp(16px, 1.8vh, 24px) 0 0;
}
.profile-pin-keypad {
  width: clamp(256px, 18vw, 324px);
  gap: clamp(8px, 0.6vw, 11px) clamp(10px, 0.7vw, 13px);
  margin: clamp(16px, 1.8vh, 24px) 0 0;
}
.profile-pin-key {
  width: clamp(74px, 5.2vw, 94px);
  height: clamp(48px, 3.3vw, 62px);
  font-size: clamp(22px, 1.5vw, 28px);
  border-radius: 10px;
}
.profile-pin-delete-icon {
  width: clamp(22px, 1.4vw, 26px);
  height: clamp(22px, 1.4vw, 26px);
}
.profile-pin-forgot {
  font-size: clamp(14px, 0.9vw, 17px);
  margin: clamp(16px, 2vh, 24px) 0 0;
}
.profile-pin-back-hint {
  margin: clamp(14px, 1.6vh, 20px) 0 0;
  font-size: clamp(15px, 0.95vw, 18px);
}
.ps5-pin-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 10px 26px;
}
.ps5-control-hint {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  color: rgba(255, 255, 255, 0.86);
  font-weight: 500;
}
.ps5-control-glyph {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: clamp(22px, 1.45vw, 28px);
  height: clamp(22px, 1.45vw, 28px);
}
.ps5-control-glyph svg {
  display: block;
  width: 100%;
  height: 100%;
}
.stream-route-shell { zoom: .72; }

""")
    search_actions=nuvio/'js/ui/screens/search/searchScreenMethods-06-activate-action-node.js'
    search_actions.write_text(patch_search_back(search_actions.read_text()))
    replace(navigation/'focusEngine.js',
        'import { Router } from "./routerState.js";',
        'import { Router } from "./routerState.js";\nimport { initPs5Navigation } from "./ps5-navigation.js";')
    replace(navigation/'focusEngine.js', '  init() {', '  init() {\n    initPs5Navigation();')
    # FocusEngine already forwards keys to these screens. Their extra document
    # listeners otherwise advance two onboarding steps on one PS5 activation.
    for name in ('experienceModeSelectionScreen.js', 'essentialAddonSetupScreen.js'):
        replace(nuvio/'js/ui/screens/onboarding'/name,
            '    document.addEventListener("keydown", this.onKeyDownBound);',
            '    if (!globalThis.__NUVIO_PS5__) document.addEventListener("keydown", this.onKeyDownBound);')
    replace(nuvio/'js/ui/screens/onboarding/experienceModeSelectionScreen.js',
        '  async onKeyDown(event) {', '''  consumeBackRequest() {
    if (!globalThis.__NUVIO_PS5__ || this.step !== "layout") return false;
    this.step = "mode";
    this.render();
    ScreenUtils.setInitialFocus(this.container);
    return true;
  },

  async onKeyDown(event) {''')
    search=nuvio/'js/ui/screens/search/searchScreenMethods-01-get-route-state-key.js'
    replace(search, '/* eslint-disable no-unused-vars */',
        '/* eslint-disable no-unused-vars */\nimport { requestPs5SearchKeyboard } from "../../navigation/ps5-text-input.js";')
    replace(search, '      this.render();\n\n      void sidebarProfilePromise.then',
        '      this.render();\n      void requestPs5SearchKeyboard(navigationContext);\n\n      void sidebarProfilePromise.then')
    replace(search,
        '''      try {
        this.sidebarProfile = await getSidebarProfileState({ cacheOnly: true });
      } catch (err) {
        console.warn("Search cached sidebar profile failed to load", err);
        this.sidebarProfile = null;
      }''',
        '''      // PS5 Search paints before the local keyboard opens.
      // The existing background profile request still refreshes the avatar.
      if (!globalThis.__NUVIO_PS5__) {
        try {
          this.sidebarProfile = await getSidebarProfileState({ cacheOnly: true });
        } catch (err) {
          console.warn("Search cached sidebar profile failed to load", err);
          this.sidebarProfile = null;
        }
      }''')
    replace(search,
        '''      this.renderFrame = requestAnimationFrame(() => {
        this.renderFrame = null;
        if (!this.container || Router.getCurrent() !== "search") {
          return;
        }
        this.render();
      });''',
        '''      this.renderFrame = requestAnimationFrame(() => {
        this.renderFrame = null;
        if (!this.container || Router.getCurrent() !== "search") {
          return;
        }
        if (globalThis.__NUVIO_PS5__ && this.shouldPatchResultsWithoutReplacingInput()) {
          this.renderResultsOnly();
          return;
        }
        this.render();
      });''')
    search_render=nuvio/'js/ui/screens/search/searchScreenMethods-03-render-recent-searches.js'
    replace(search_render, '                  id="searchInput"',
        '''                  id="searchInput"
                  ${globalThis.__NUVIO_PS5__ ? 'readonly inputmode="none"' : ''}''')
    replace(search_render,
        '<span class="search-action-icon material-icons" aria-hidden="true">explore</span>',
        '''${globalThis.__NUVIO_PS5__ ? '<svg class="search-action-icon" width="54" height="54" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m16 8-2.5 5.5L8 16l2.5-5.5Z"/></svg>' : '<span class="search-action-icon material-icons" aria-hidden="true">explore</span>'}''')
    replace(search_render,
        '<button class="search-discover-btn focusable" data-action="openDiscover">',
        '<button class="search-discover-btn focusable" data-action="openDiscover" aria-label="${escapeHtml(t("discover_title", {}, "Discover"))}">')
    replace(search_render,
        '<span class="material-icons" aria-hidden="true">close</span>',
        '''${globalThis.__NUVIO_PS5__ ? '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m6 6 12 12M6 18 18 6"/></svg>' : '<span class="material-icons" aria-hidden="true">close</span>'}''')
    empty=nuvio/'js/ui/screens/search/searchScreenMethods-02-load-discover-rows.js'
    old='<span class="search-empty-icon material-icons" aria-hidden="true">search</span>'
    text=empty.read_text()
    if text.count(old)!=2:
        raise RuntimeError('Pinned Search empty icons changed')
    empty.write_text(text.replace(old,
        '''${globalThis.__NUVIO_PS5__ ? '<svg class="search-empty-icon" width="136" height="136" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/></svg>' : '<span class="search-empty-icon material-icons" aria-hidden="true">search</span>'}'''))
    # Upstream 1.3.11 normalizes nullable collection ratings without Number(null).
    # Request the artwork consumed by mapTraktEntity, as library lists do.
    replace(nuvio/'js/ui/screens/collection/folderDetailScreenHelpers-04-map-trakt-entity.js',
        '  url.searchParams.set("page", String(page));',
        '  url.searchParams.set("extended", "full,images");\n  url.searchParams.set("page", String(page));')
    # Observe existing response parsing without changing its success/error policy.
    replace(nuvio/'js/ui/screens/collection/folderDetailScreenHelpers-02-build-fallback-streaming-sources.js',
        '  const payload = await response.json().catch(() => null);',
        '''  let jsonState = 1;
  const payload = await response.json().catch(() => { jsonState = 0; return null; });
  globalThis.__nuvioPs5TmdbResponse?.(response, payload, jsonState);''')
    replace(nuvio/'js/core/tmdb/tmdbMetadataServiceMethods-02-fetch-episode-enrichment.js',
        '''      const url = `${TMDB_BASE_URL}/collection/${encodeURIComponent(String(collectionId))}?api_key=${encodeURIComponent(apiKey)}&language=${encodeURIComponent(lang)}`;
      const response = await fetch(url);
      if (!response.ok) {
        return [];
      }
      const data = await response.json();''',
        '''      const url = `${TMDB_BASE_URL}/collection/${encodeURIComponent(String(collectionId))}?api_key=${encodeURIComponent(apiKey)}&language=${encodeURIComponent(lang)}`;
      const response = await fetch(url);
      if (!response.ok) {
        globalThis.__nuvioPs5TmdbResponse?.(response, null, -1);
        return [];
      }
      const data = await response.json().catch(error => {
        globalThis.__nuvioPs5TmdbResponse?.(response, null, 0);
        throw error;
      });
      globalThis.__nuvioPs5TmdbResponse?.(response, data, 1);''')
    catalog_order=nuvio/'js/ui/screens/plugin/catalogOrderScreen.js'
    # Keep reorder actions legible and compact without a remote icon font.
    for direction in ('up', 'down'):
        replace(catalog_order,
            f'              <span class="material-icons" aria-hidden="true">arrow_{direction}ward</span>',
            f'''              ${{globalThis.__NUVIO_PS5__ ? "Move {direction}" : '<span class="material-icons" aria-hidden="true">arrow_{direction}ward</span>'}}''')
        replace(catalog_order,
            f'                    class="catalog-order-action ${{item.canMove{direction.capitalize()} ? "catalog-order-focusable" : "is-disabled"}}"',
            f'                    aria-label="Move {direction}"\n'+
            f'                    class="catalog-order-action ${{item.canMove{direction.capitalize()} ? "catalog-order-focusable" : "is-disabled"}}"')
    detail=nuvio/'js/ui/screens/detail'
    back=detail/'metaDetailsScreenMethods-05-resolve-initial-selected-season.js'
    back.write_text(patch_detail_back(back.read_text()))
    replace(detail/'metaDetailsScreenMethods-07-merge-stream-items.js',
        '                ${this.getActiveResumeProgress() ? `<button',
        '''                ${globalThis.__NUVIO_PS5__ ? '<button class="series-secondary-btn focusable" data-action="ps5PlayOptions">Play options</button>' : ""}
                ${this.getActiveResumeProgress() ? `<button''')
    replace(detail/'metaDetailsScreenMethods-08-render-external-ratings-row.js',
        '            <div class="card focusable" data-action="toggleLibrary">',
        '''            ${globalThis.__NUVIO_PS5__ ? '<div class="card focusable" data-action="ps5PlayOptions">Play options</div>' : ""}
            <div class="card focusable" data-action="toggleLibrary">''')
    replace(detail/'metaDetailsScreenMethods-26-on-key-down.js',
        '      if (action === "playDefault") {',
        '''      if (globalThis.__NUVIO_PS5__ && action === "ps5PlayOptions") {
        this.openHeroPlayMenu();
        return;
      }

      if (action === "playDefault") {''')
    home=nuvio/'js/ui/screens/home/homeScreenMethods-06-get-hero-source-from-focus-state.js'
    replace(home, 'if (!isCloud && this.showContinueWatchingManualPlayOption) {',
        'if (!isCloud && (globalThis.__NUVIO_PS5__ || this.showContinueWatchingManualPlayOption)) {')
    # Upstream now also honors manualSelection before progress-based resume.
    settings=nuvio/'js/ui/screens/settings/settingsScreenMethods-14-activate-focused.js'
    replace(settings,
        'if ((code === 38 || code === 40) && !(activeField && this.textDialog.multiline)) {',
        'if ((code === 38 || code === 40) && (globalThis.__NUVIO_PS5__ || !(activeField && this.textDialog.multiline))) {')
    replace(nuvio/'js/ui/screens/settings/settingsScreenMethods-10-render-playback-section.js',
        '      registerPlaybackActionsPart02.call(this, model);',
        '''      registerPlaybackActionsPart02.call(this, model);
      if (globalThis.__NUVIO_PS5__) {
        this.actionMap.set("playback:ps5-native", () => document.getElementById("__evoClose")?.click());
        this.actionMap.set("playback:ps5-speedtest", () => showPs5Speedtest());
      }''')
    settings_playback = nuvio/'js/ui/screens/settings/settingsScreenMethods-10-render-playback-section.js'
    settings_playback.write_text('import { showPs5Speedtest } from "../../navigation/ps5-speedtest.js";\n' + settings_playback.read_text())
    shutil.copyfile(Path(__file__).parent/'ps5-speedtest.js', navigation/'ps5-speedtest.js')
    replace(nuvio/'js/ui/screens/settings/settingsScreenPlaybackMarkup-06-section.js',
        '          ${this.renderSectionHeader(SECTION_META.find((item) => item.id === "playback"))}',
        '''          ${this.renderSectionHeader(SECTION_META.find((item) => item.id === "playback"))}
          ${globalThis.__NUVIO_PS5__ ? this.renderActionRow({ focusKey: "playback:ps5-native", title: "Player settings", subtitle: "Open the native PS5 player settings" }) : ""}
          ${globalThis.__NUVIO_PS5__ ? this.renderActionRow({ focusKey: "playback:ps5-speedtest", title: "Speed test", subtitle: "Test native download speed to TorBox" }) : ""}''')
    router=nuvio/'js/ui/navigation/routerMethods-02-complete-route-return-back-guard.js'
    router.write_text(patch_resume_router(router.read_text()))
    # 1.3.11 published a local Nuvio Sync snapshot while the cold pull was still
    # running, so Home kept the cached Continue Watching row. 1.2.3 held that
    # snapshot as provisional until the pull merged.
    replace(nuvio/'js/ui/screens/home/homeContinueWatchingLoad.js',
        """      // Publish usable local progress while the cold pull runs, like Android.
      // Only an empty local result needs to wait for the authoritative pull.
      const shouldWaitForStartupSync = Boolean(
        initialContinueWatchingPending &&
        !shouldShowLoading &&
        (startupSyncPullPromise || startupSyncCompletedDuringLoad) &&
        !progressErrors.all &&
        !progressErrors.recent
      );""",
        """      // A local Nuvio Sync snapshot is provisional while the cold pull is
      // active. Do not publish it as the first row, because the pull can
      // replace it with additional remote entries moments later.
      const shouldWaitForStartupSync = Boolean(
        initialContinueWatchingPending &&
        (startupSyncPullPromise || startupSyncCompletedDuringLoad) &&
        !progressErrors.all &&
        !progressErrors.recent
      );""")
    replace(nuvio/'js/ui/screens/home/homeContinueWatchingLoad.js',
        "      if (startupSyncPullPromise || startupSyncCompletedDuringLoad) {",
        "      if (shouldWaitForStartupSync) {")
    replace(nuvio/'js/ui/screens/home/homeContinueWatchingLoad.js',
        """        }
      }
      if (shouldWaitForStartupSync) {
        this.continueWatchingLoading = true;""",
        """        }
        this.continueWatchingLoading = true;""")
    # 1.3.11 returned before flushing live playback. A restored progressSession
    # can also carry completedKeys as a plain object after LocalStore JSON.
    replace(nuvio/'js/core/player/playerControllerMethods-20-flush-progress.js',
        """      if (this.currentPlaybackIsLive === true) {
        return false;
      }
      const active = context || this.createProgressContext();""",
        "      const active = context || this.createProgressContext();")
    replace(nuvio/'js/core/player/playerControllerMethods-19-pause.js',
        """      if (this.currentPlaybackIsLive === true) {
        return false;
      }
      const context = this.createProgressContext();""",
        "      const context = this.createProgressContext();")
    replace(nuvio/'js/core/player/playerControllerMethods-20-flush-progress.js',
        """      const session = active.progressSession || (this.watchProgressSession ||= { completedKeys: new Set() });
      const progressKey = this.buildProgressSnapshotKey(active);
      if (!clear && session.completedKeys.has(progressKey)) return false;""",
        """      const session = active.progressSession || (this.watchProgressSession ||= { completedKeys: new Set() });
      const progressKey = this.buildProgressSnapshotKey(active);
      const completedKeys = session.completedKeys instanceof Set ? session.completedKeys : (session.completedKeys = new Set());
      if (!clear && completedKeys.has(progressKey)) return false;""")
    replace(nuvio/'js/core/player/playerControllerMethods-20-flush-progress.js',
        "        session.completedKeys.add(progressKey);",
        "        completedKeys.add(progressKey);")
    # A saved PREFERRED_ONLY startup mode must still limit subtitles when the
    # newer preferred-language flag is off.
    replace(nuvio/'js/ui/screens/player/playerScreenMethods-68-load-subtitles.js',
        "        const preferredOnly = Boolean(subtitleSettings.subtitleStyle?.showOnlyPreferredLanguages);",
        """        const preferredOnly =
          subtitleSettings.addonSubtitleStartupMode === \"PREFERRED_ONLY\" ||
          (subtitleSettings.addonSubtitleStartupMode === \"ALL_SUBTITLES\" && subtitleSettings.subtitleStyle?.showOnlyPreferredLanguages);""")
    # Hide a Home catalog only when search is required, not when any extra is.
    replace(nuvio/'js/core/addons/homeCatalogs.js',
        """export function catalogShouldShowOnHome(catalog = {}) {
  // A required extra (search, genre, ...) makes the catalog unusable as a
  // parameterless Home row; AIOStreams/AIOMetadata also mark those catalogs
  // showInHome=false, but not every addon does.
  if (catalogRequiresExtras(catalog)) {
    return false;
  }
  return catalog?.hasExplicitShowInHome !== true || catalog?.showInHome === true;
}""",
        """export function catalogShouldShowOnHome(catalog = {}) {
  const isSearchOnly =
    Array.isArray(catalog?.extra) &&
    catalog.extra.some(
      (entry) =>
        String(entry?.name || entry || \"\")
          .trim()
          .toLowerCase() === \"search\" && Boolean(entry?.isRequired)
    );
  if (isSearchOnly) {
    return false;
  }
  return catalog?.hasExplicitShowInHome !== true || catalog?.showInHome === true;
}""")
    # A watched mark must push the existing progress row as completed. A 100 ms
    # placeholder is dropped by isSyncableProgressItem, so the server keeps the
    # half-played row and the next pull restores it. watch_sync supplies the
    # shared markStoredProgressWatched implementation.
    for path, old in (
        (nuvio/'js/ui/screens/home/homeScreenMethods-09-toggle-continue-watching-watched.js',
         """      await watchProgressRepository.saveProgress({
        contentId: normalized.contentId,
        imdbId: normalized.imdbId || null,
        tmdbId: normalized.tmdbId || null,
        traktId: normalized.traktId || null,
        contentType: normalized.type || \"movie\",
        videoId: normalized.videoId || null,
        season: normalized.season,
        episode: normalized.episode,
        positionMs: 100,
        durationMs: 100,
        updatedAt: Date.now()
      });"""),
        (nuvio/'js/ui/screens/home/homeScreenMethods-09-toggle-continue-watching-watched.js',
         """      await watchProgressRepository.saveProgress({
        contentId: item.id,
        imdbId: item.imdbId || null,
        tmdbId: item.tmdbId || null,
        traktId: item.traktId || null,
        contentType: item.type || \"movie\",
        videoId: null,
        season: null,
        episode: null,
        positionMs: 100,
        durationMs: 100,
        updatedAt: Date.now()
      });"""),
        (nuvio/'js/ui/components/posterOptionsMenu.js',
         """    await watchProgressRepository.saveProgress({
      contentId: item.id,
      imdbId: item.imdbId || null,
      tmdbId: item.tmdbId || null,
      traktId: item.traktId || null,
      contentType: item.type || \"movie\",
      videoId: null,
      positionMs: 100,
      durationMs: 100,
      updatedAt: Date.now()
    });"""),
        (nuvio/'js/ui/screens/detail/metaDetailsScreenMethods-26-on-key-down.js',
         """          await watchProgressRepository.saveProgress({
            contentId: this.params?.itemId,
            ...providerIds,
            contentType: this.params?.itemType || \"movie\",
            videoId: null,
            positionMs: 100,
            durationMs: 100,
            updatedAt: Date.now()
          });"""),
    ):
        replace(path, old, "      await watchProgressRepository.markStoredProgressWatched(" + (
            "normalized.contentId, normalized.videoId || null" if "normalized.contentId" in old else
            "this.params?.itemId" if "this.params" in old else "item.id"
        ) + ");")
    replace(nuvio/'js/data/repository/watchedSeriesReconciliationService.js',
        """  const progressItems = episodes.map((episode) => ({
    contentId,
    contentType,
    imdbId: identityOptions.imdbId,
    tmdbId: identityOptions.tmdbId,
    traktId: identityOptions.traktId,
    videoId: episode.id,
    season: episode.season,
    episode: episode.episode,
    title: meta?.name || null,
    episodeTitle: episode.title || null,
    positionMs: 100,
    durationMs: 100,
    updatedAt: watchedAt
  }));
  const outcome = await watchedItemsRepository.markBatch(watchedItems, { skipTrackingWrite });""",
        """  const outcome = await watchedItemsRepository.markBatch(watchedItems, { skipTrackingWrite });""")
    replace(nuvio/'js/data/repository/watchedSeriesReconciliationService.js',
        """  await watchProgressRepository.saveProgressBatch(
    progressItems.filter((item) =>
      outcome.succeeded.some((entry) => entry.videoId === item.videoId)
    )
  );""",
        """  await Promise.all(episodes.filter((episode) =>
    outcome.succeeded.some((entry) => entry.videoId === episode.id)
  ).map((episode) => watchProgressRepository.markStoredProgressWatched(contentId, episode.id)));""")
    replace(nuvio/'js/ui/screens/detail/metaDetailsScreenMethods-15-refresh-episode-playback-state.js',
        """        await watchProgressRepository.saveProgress({
          contentId: this.params?.itemId,
          ...providerIds,
          contentType: \"series\",
          videoId: episode.id,
          season: episode.season,
          episode: episode.episode,
          positionMs: 100,
          durationMs: 100,
          updatedAt: Date.now()
        });""",
        """        await watchProgressRepository.markStoredProgressWatched(this.params?.itemId, episode.id);""")
    replace(nuvio/'js/ui/screens/detail/metaDetailsScreenMethods-14-move-episode-focus.js',
        """        await watchProgressRepository.saveProgressBatch(
          targets
            .filter((episode) => outcome.succeeded.some((item) => item.videoId === episode.id))
            .map((episode) => ({
              contentId: this.params?.itemId,
              ...providerIds,
              contentType: \"series\",
              videoId: episode.id,
              season: episode.season,
              episode: episode.episode,
              title: this.meta?.name || this.params?.fallbackTitle || null,
              episodeTitle: episode.title || null,
              positionMs: 100,
              durationMs: 100,
              updatedAt: watchedAt
            }))
        );""",
        """        await Promise.all(targets
          .filter((episode) => outcome.succeeded.some((item) => item.videoId === episode.id))
          .map((episode) => watchProgressRepository.markStoredProgressWatched(this.params?.itemId, episode.id)));""")
    replace(nuvio/'js/ui/screens/stream/streamScreenMethods-03-mount.js',
        '    async mount(params = {}, navigationContext = {}) {',
        '''    async mount(params = {}, navigationContext = {}) {
      await globalThis.__nuvioRestorePlaybackProgress?.();''')
    replace(nuvio/'js/ui/screens/home/homeScreenMethods-20-mount.js',
        '      this.continueWatchingDisplay = readContinueWatchingDisplaySnapshot(watchProgressRepository.getContinueWatchingSourceKey());\n      this.continueWatchingHydratedFromSnapshot = Boolean(this.continueWatchingDisplay.length);',
        '''      if (globalThis.__nuvioProgressHomeDirty) {
        this.continueWatchingDisplay = [];
        this.continueWatchingHydratedFromSnapshot = false;
        globalThis.__nuvioProgressHomeDirty = false;
      } else {
        this.continueWatchingDisplay = readContinueWatchingDisplaySnapshot(watchProgressRepository.getContinueWatchingSourceKey());
        this.continueWatchingHydratedFromSnapshot = Boolean(this.continueWatchingDisplay.length);
      }''')
    replace(nuvio/'js/data/repository/skipIntroRepository.js',
        '    const response = await fetch(url, {',
        '''    // IntroDB does not allow the console's loopback browser origin.
    // Keep its existing mapping/cache and fetch only this service natively.
    const endpoint = new URL(url);
    const target = globalThis.__NUVIO_PS5__ && endpoint.origin === "https://api.introdb.app" && endpoint.pathname === "/segments"
      ? "/evo/skip-metadata" + endpoint.search : url;
    const response = await fetch(target, {''')
    app=nuvio/'js/app.js'
    replace(app, 'let hasSelectedProfileThisSession = false;',
        'let hasSelectedProfileThisSession = false;\n' +
        (Path(__file__).parent/'ps5-resume.js').read_text() + '\n' +
        (Path(__file__).parent/'ps5-playback-progress.js').read_text() + '\n' +
        (Path(__file__).parent/'ps5-skip.js').read_text() + '\n' +
        (Path(__file__).parent/'ps5-next.js').read_text())
    replace(app, 'import { PlayerController } from "./core/player/playerController.js";',
        '''import { PlayerController } from "./core/player/playerController.js";
import { PlayerSettingsStore } from "./data/local/playerSettingsStore.js";
import { skipIntroRepository } from "./data/repository/skipIntroRepository.js";
import { getSkipIntervalTargetSeconds } from "./core/player/skipIntervalRules.js";
import { normalizeNextEpisodeThresholdMode, normalizeThresholdMinutesBeforeEnd,
  normalizeThresholdPercent, shouldEnterStillWatchingPrompt } from "./ui/screens/player/playerNextEpisodeRules.js";''')
    replace(app, '''  runAfterFirstHomePaint(() => {
    void StartupSyncService.requestSyncNow({
      notifyPullCompleted: ["home", "plugins"].includes(experienceRoute)
    }).catch((error) => {
      console.warn("Profile background sync failed", error);
    });
  });
  const storedResumeRoute =''',
        '''  await StartupSyncService.requestSyncNow({
    notifyPullCompleted: ["home", "plugins"].includes(experienceRoute)
  }).catch((error) => {
    console.warn("Profile background sync failed", error);
  });
  await restorePs5PlaybackProgress();
  const storedResumeRoute =''')
    replace(app, '  const storedResumeRoute =\n    restoreWebOsRoute',
        '''  const recommendation = experienceRoute === "home" && globalThis.__nuvioTakePresentationRoute?.();
  if (recommendation) {
    await Router.navigate("detail", recommendation, { replaceHistory: true, skipStackPush: true });
    return;
  }
  const nativeDetail = experienceRoute === "home" && globalThis.__nuvioTakePlaybackDetailRoute?.();
  if (nativeDetail) {
    await Router.navigate("detail", nativeDetail, { replaceHistory: true, skipStackPush: true });
    return;
  }
  const nativeNext = experienceRoute === "home" && globalThis.__nuvioTakeNextEpisodeRoute?.();
  if (nativeNext) {
    await Router.navigate("player", nativeNext, { replaceHistory: true, skipStackPush: true });
    return;
  }
  const storedResumeRoute =
    restoreWebOsRoute''')
    replace(detail/'metaDetailsScreenMethods-03-load-detail.js', '      this.render(meta);',
        '''      this.render(meta, globalThis.__NUVIO_PS5__ && this.params?.ps5ReturnEpisodeVideoId
        ? this.getEpisodeFocusDescriptor(this.params.ps5ReturnEpisodeVideoId) : undefined);''')
    mount = nuvio/'js/ui/screens/player/playerScreenMethods-01-mount.js'
    replace(mount, '    PlayerController,', '    PlayerController,\n    Router,')
    replace(mount, '      this.params = params;',
        '      this.ps5NativeNextEpisode = false;\n      this.params = params;')
    replace(mount, '      this.bindPlayerExitCleanup();', '''      this.bindPlayerExitCleanup();
      if (globalThis.__NUVIO_PS5__ && params.ps5NextEpisodeSession) {
        if (!globalThis.__nuvioConsumeNextEpisode?.(params)) {
          await Router.navigate("stream", { ...this.buildStreamRouteParamsFromPlayer(), manualSelection: true });
          return;
        }
        this.ps5NativeNextEpisode = true;
        await this.playNextEpisode({ userInitiated: Boolean(params.ps5NextEpisodeUserInitiated) });
        return;
      }''')
    replace(nuvio/'js/ui/screens/player/playerScreenMethods-22-should-show-next-episode-card.js',
        '    async runNextEpisodeCountdown(token, selectedStream) {',
        '''    async runNextEpisodeCountdown(token, selectedStream) {
      if (this.ps5NativeNextEpisode) return this.isNextEpisodeLaunchActive(token);''')
    replace(nuvio/'js/ui/screens/player/playerScreenMethods-23-maybe-autoplay-next-episode.js',
        '    getCurrentStreamBingeGroup() {', '''    getCurrentStreamBingeGroup() {
      if (this.ps5NativeNextEpisode) return String(this.params?.ps5NativeBingeGroup || "");''')
    replace(nuvio/'js/core/profile/profileSelectionScreenMethods-07-activate-focused-node.js',
        '        await ProfileManager.setActiveProfile(profileId);',
        '''        await ProfileManager.setActiveProfile(profileId);
        await globalThis.__nuvioRestorePlaybackProgress?.();''')
    replace(app, '  if (hasSelectedProfileThisSession) {',
        '  if (hasSelectedProfileThisSession || canResumePs5Playback()) {')
    replace(app, 'async function shouldShowProfileSelection() {',
        '''async function shouldShowProfileSelection() {
  // Restore account profiles before getProfiles can create a local default.
  // Playback returns already have a verified profile and must not wait here.
  if (globalThis.__NUVIO_PS5__ && !canResumePs5Playback()) {
    await ProfileSyncService.pull();
  }''')
    replace(app, '          ProfileManager.isRememberLastProfileEnabled() &&\n          ProfileManager.hasEverSelectedProfile()',
        '          canResumePs5Playback() || (\n'
        '            ProfileManager.isRememberLastProfileEnabled() &&\n'
        '            ProfileManager.hasEverSelectedProfile()\n'
        '          )')
    experience=nuvio/'js/core/profile/experienceModeRouting.js'
    replace(experience, 'export function resolveExperienceRoute(profileId) {',
        '''import { AuthManager } from "../auth/authManager.js";
import { ProfileSettingsSyncService } from "./profileSettingsSyncService.js";

export async function resolveExperienceRoute(profileId) {
  // A cold account has no local mode yet. Pull before offering setup, not
  // after routing there. Existing choices and guest onboarding stay local.
  if (globalThis.__NUVIO_PS5__ && AuthManager.isAuthenticated &&
      !ExperienceModeStore.getForProfile(profileId).mode &&
      !LayoutPreferences.getForProfile(profileId).hasChosenLayout) {
    await ProfileSettingsSyncService.pull(profileId);
  }''')
    import playback_general
    playback_general.patch_frontend(nuvio)
    import subtitle_handoff
    subtitle_handoff.patch_frontend(nuvio)
    import native_preferences
    native_preferences.patch_frontend(nuvio)
    import watch_sync
    watch_sync.patch_frontend(nuvio)


def patch_controller_hook(source):
    # The upstream click adapter fabricates a 60 ms hold for a small subset of
    # cards. The frontend adapter now sends one Enter cycle for every X click.
    comment_start="/* Nuvio's hold-able buttons"
    comment_end="\"var nvTitle='';function nvNoteTitle()"
    if source.count(comment_start)!=1 or source.count(comment_end)!=1:
        raise RuntimeError('Pinned native click comment changed')
    begin=source.index(comment_start)
    finish=source.index(comment_end, begin)
    source=source[:begin]+'''/* The PS5 frontend adapter owns focused activation and item menus.
 * Preserve title capture for the native stream handoff. */
'''+source[finish:]
    start='"if(NUVIO){document.addEventListener(\'click\',function(e){nvNoteTitle();"'
    end='''" k('keydown');setTimeout(function(){k('keyup');},60);},true);}"'''
    if source.count(start)!=1 or source.count(end)!=1:
        raise RuntimeError('Pinned native click adapter changed')
    begin=source.index(start)
    finish=source.index(end, begin)+len(end)
    source=source[:begin]+'''"if(NUVIO){document.addEventListener('click',nvNoteTitle,true);}"
'''+source[finish:]
    anchor='static char s_hook_profile[16];'
    if source.count(anchor)!=1:
        raise RuntimeError('Pinned controller state anchor changed')
    source=source.replace(anchor, anchor+'\nstatic uint32_t s_controller_options, s_controller_menu, s_controller_navigation, s_controller_keyboard;\nstatic int s_controller_direction, s_controller_shortcut;')
    anchor='    } else if (!strncmp(path, "/evo/close", 10)) {'
    if source.count(anchor)!=1:
        raise RuntimeError('Pinned controller endpoint anchor changed')
    source=source.replace(anchor, '''    } else if (!strcmp(path, "/evo/controller")) {
        char body[160];
        pthread_mutex_lock(&s_mx);
        int n = snprintf(body, sizeof body, "{\\"options\\":%u,\\"menu\\":%u,\\"navigation\\":%u,\\"direction\\":%d,\\"keyboard\\":%u,\\"shortcut\\":%d}",
                         (unsigned)s_controller_options, (unsigned)s_controller_menu,
                         (unsigned)s_controller_navigation, s_controller_direction,
                         (unsigned)s_controller_keyboard, s_controller_shortcut);
        pthread_mutex_unlock(&s_mx);
        respond(fd, "200 OK", "application/json", body, (size_t)n);
'''+anchor)
    return source+'''
void evo_webui_controller(int options, int menu, int direction, int shortcut) {
    pthread_mutex_lock(&s_mx);
    if (options) ++s_controller_options;
    if (menu) ++s_controller_menu;
    if (direction >= 1 && direction <= 4) {
        ++s_controller_navigation;
        s_controller_direction = direction;
    }
    if (shortcut >= 1 && shortcut <= 4) {
        ++s_controller_keyboard;
        s_controller_shortcut = shortcut;
    }
    pthread_mutex_unlock(&s_mx);
    if (options) tlog("controller: Options");
    if (menu) tlog("controller: Triangle");
}
'''


def fix_player_back(source):
    include='#include "evo/screens/PlayerScreen.hpp"'
    old='        // Stop playback confirmation prompt\n        if (screenMgr) {'
    if source.count(include)!=1 or source.count(old)!=1:raise RuntimeError('Pinned player Back anchors changed')
    source=source.replace(include,include+'\n#include "evo_webui.h"')
    return source.replace(old,'''        // Nuvio Back stops the native session; the existing bridge reopens it.
        // Native-only playback retains confirmation and the other overlays.
        if (!evo_webui_native_requested()) {
            playback->stopPlayback();
            if (screenMgr) screenMgr->returnFromPlayback();
            return true;
        }
        // Stop playback confirmation prompt
        if (screenMgr) {''')


def fix_playback_handoff(source):
    # Save synchronously before EVO closes the browser. Mark only its return URL.
    old = '" function go(t){if(done)return;done=1;saveNow(1);"'
    end = "encodeURIComponent(good));}"
    if source.count(old) != 1 or source.count(end) != 1:
        raise RuntimeError('Pinned playback handoff anchors changed')
    new = ('" function go(t){if(done)return;done=1;function play(skip){if(skip===null)return;var back=good,start=0,session=\'\',next=\'\';"\n'
           '" if(NUVIO){if(window.__nuvioSavePlaybackReturn)session=window.__nuvioSavePlaybackReturn()||\'\';"\n'
           '" if(window.__nuvioPlaybackNextPolicy)next=window.__nuvioPlaybackNextPolicy(session);"\n'
           '" if(window.__nuvioPlaybackStartSeconds)start=window.__nuvioPlaybackStartSeconds();"\n'
           '" var ret=new URL(good,location.href);ret.searchParams.set(\\"nuvioPlaybackReturn\\",\\"1\\");back=ret.href;}saveNow(1);function launch(){"')
    return source.replace(old, new).replace(end,
        "encodeURIComponent(back)+'&start='+encodeURIComponent(start)+'&session='+encodeURIComponent(session)+'&skip='+encodeURIComponent(skip||'')+'&next='+encodeURIComponent(next));}"
        "if(NUVIO&&window.__nuvioSendPresentation){window.__nuvioSendPresentation(session).then(function(ok){if(ok)launch();else done=0;},function(){done=0;});}else launch();}"
        "if(NUVIO){Promise.all([window.__nuvioPlaybackSkipSegments?window.__nuvioPlaybackSkipSegments():Promise.resolve(''),"
        "window.__nuvioPreparePresentation?window.__nuvioPreparePresentation():Promise.resolve(true)]).then(function(v){if(v[1]!==null)play(v[0]);},function(){done=0;});}else play('');}")


def patch_playback_start(app):
    """Carry a per-handoff offset into EVO's existing startup seek, in seconds."""
    web = app/'src/evo_webui.c'
    replace(web, '#include <errno.h>', '#include <errno.h>\n#include <math.h>')
    replace(web, 'static char s_h_return[2048];',
        'static char s_h_return[2048];\nstatic double s_h_start;')
    replace(web, 'static char s_play_title[256];',
        'static char s_play_title[256];\nstatic double s_play_start;')
    replace(web, '        to_upstream(raw, url, sizeof url);', '''        char start[64], *end;
        query_param(path, "start", start, sizeof start);
        errno = 0;
        double seconds = strtod(start, &end);
        if (errno || end == start || *end || !isfinite(seconds) || seconds < 0.0)
            seconds = 0.0;
        to_upstream(raw, url, sizeof url);''')
    replace(web, '        snprintf(s_h_return, sizeof s_h_return, "%s", ret);',
        '        snprintf(s_h_return, sizeof s_h_return, "%s", ret);\n        s_h_start = seconds;')
    replace(web, '            snprintf(s_play_title, sizeof s_play_title, "%s", s_h_title);',
        '            snprintf(s_play_title, sizeof s_play_title, "%s", s_h_title);\n            s_play_start = s_h_start;')
    replace(web, 'int evo_webui_take_play(char *url, size_t url_cap, char *title, size_t title_cap)',
        'int evo_webui_take_play(char *url, size_t url_cap, char *title, size_t title_cap, double *start)')
    replace(web, '    snprintf(title, title_cap, "%s", s_play_title);',
        '    snprintf(title, title_cap, "%s", s_play_title);\n    *start = s_play_start;')
    header = app/'include/evo_webui.h'
    replace(header, 'int  evo_webui_take_play(char *url, size_t url_cap, char *title, size_t title_cap);',
        '/* start receives the requested initial position in seconds. */\n'
        'int  evo_webui_take_play(char *url, size_t url_cap, char *title, size_t title_cap, double *start);')
    replace(header, 'static inline int  evo_webui_take_play(char *u, size_t uc, char *t, size_t tc)\n{ (void)u; (void)uc; (void)t; (void)tc; return 0; }',
        'static inline int  evo_webui_take_play(char *u, size_t uc, char *t, size_t tc, double *s)\n'
        '{ (void)u; (void)uc; (void)t; (void)tc; (void)s; return 0; }')
    application = app/'core/src/Application.cpp'
    replace(application, 'PlaybackSource g_web_src;',
        'PlaybackSource g_web_src;\ndouble g_web_start = 0.0;')
    replace(application, 'pb->startPlaybackSource(g_web_src, 0.0)',
        'pb->startPlaybackSource(g_web_src, g_web_start)')
    replace(application, 'evo_webui_take_play(url, sizeof url, title, sizeof title)',
        'evo_webui_take_play(url, sizeof url, title, sizeof title, &g_web_start)')


def patch_stream_selection(nuvio):
    """Keep the selected stream across incremental source ordering and completion."""
    stream = nuvio/'js/ui/screens/stream'
    render = stream/'streamScreenMethods-09-render.js'
    # PS5 keeps the focused source even when it is the first result. Upstream
    # follows newly arriving sources until the user moves on other platforms.
    replace(render, 'const holdFirstResult = this.focusState?.zone === "card"',
        'const holdFirstResult = !globalThis.__NUVIO_PS5__ && this.focusState?.zone === "card"')
    replace(render, '''      const previousFocusedKey =
        previousVirtualModel &&''', '''      const previousStreams = this.renderedStreamListStreams || [];
      const previousKeys = previousVirtualModel?.keys || this.getStreamVirtualKeys(
        this.addonFilter === "all" ? previousStreams : previousStreams.filter((s) => s.addonName === this.addonFilter)
      );
      const previousFocusedKey =
        this.focusState?.zone === "card" &&''')
    replace(render, '''        previousFocusedIndex < previousVirtualModel.keys.length
          ? previousVirtualModel.keys[previousFocusedIndex]''', '''        previousFocusedIndex < previousKeys.length
          ? previousKeys[previousFocusedIndex]''')
    replace(render, '      if (virtualizedStreamList && previousFocusedKey && !holdFirstResult && !this.streamVirtualFocusReset) {',
        '      if (previousFocusedKey && !holdFirstResult && !this.streamVirtualFocusReset) {')
    load = stream/'streamScreenMethods-04-load-streams.js'
    # Upstream now reads row before index. Do not replace the user's selection
    # with preferredStreamId at aggregate completion.
    replace(load, '          if (preferred) {',
        '          if (preferred && this.focusState?.zone !== "card") {')


def patch_playback_restart_diagnostics(app):
    """Record numeric restart state without changing pause or retry policy."""
    controller = app/'core/src/services/PlaybackController.cpp'
    replace(controller, '''    double resumeAt = getPositionSeconds();
    bool wasPaused = isPaused();''', '''    double resumeAt = getPositionSeconds();
    bool wasPaused = isPaused();
    evo_boot_log("audio switch begin: from=%d to=%d position=%.3f paused=%d engine_paused=%d",
                 audio_stream_index, streamIndex, resumeAt, wasPaused, evo_pb_is_paused());''')
    replace(controller, '    if (!startPlaybackSource(savedSource, resumeAt)) {',
        '''    if (!startPlaybackSource(savedSource, resumeAt)) {
        evo_boot_log("audio switch end: requested=%d opened=0", streamIndex);''')
    replace(controller, '''    if (wasPaused) setPaused(true);
    return true;
}

std::vector<PlaybackController::VideoVariantInfo>''',
        '''    if (wasPaused) setPaused(true);
    evo_boot_log("audio switch end: requested=%d selected=%d opened=1 paused=%d engine_paused=%d",
                 streamIndex, audio_stream_index, isPaused(), evo_pb_is_paused());
    return true;
}

std::vector<PlaybackController::VideoVariantInfo>''')
    replace(controller, '    evo_thread_create(&demux_thread, demux_thread_func, nullptr);',
        '''    const int demux_rc = evo_thread_create(&demux_thread, demux_thread_func, nullptr);
    evo_boot_log("playback worker start: kind=demux rc=%d", demux_rc);''')
    for thread, function in (('video', 'video_decode_thread_func'),
                             ('audio_decode', 'audio_decode_thread_func'), ('audio', 'audio_output_thread')):
        replace(controller, f'        evo_thread_create(&{thread}_thread, {function}, nullptr);',
            f'''        const int thread_rc = evo_thread_create(&{thread}_thread, {function}, nullptr);
        evo_boot_log("playback worker start: kind={thread} rc=%d", thread_rc);''')


def patch_playback_read_diagnostics(app):
    """Bound numeric network demux timing without exporting request context."""
    stream_io = app/'media/src/evo_stream_io.c'
    replace(stream_io, '    av_dict_set(opts, "reconnect", "1", 0);', '''    /* Controlled receive-buffer experiment: FFmpeg forwards this option
     * through HTTP/TLS to TCP before connect. Read-path diagnostics report
     * the actual accepted SO_RCVBUF, which the OS may cap or reject. */
    av_dict_set(opts, "recv_buffer_size", "4194304", 0);
    av_dict_set(opts, "reconnect", "1", 0);''')
    demux = app/'media/src/evo_demux.c'
    replace(demux, '#include <unistd.h>', '''#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <libavformat/avio.h>

/* Exact declarations from pinned FFmpeg 7.1.1 avio_internal.h and url.h.
 * Use its URL/HTTP/TLS dispatch, never cast private protocol layouts. */
struct URLContext;
struct URLContext *ffio_geturlcontext(AVIOContext *s);
int ffurl_get_file_handle(struct URLContext *h);''')
    replace(demux, '''    while (demux_thread_running) {
        /*
         * Process seek requests before checking the paused state.''', '''    /* At most 24 five-second windows per network playback. AVIO bytes are
     * payload read by libavformat, not socket bytes or a CDN speed test. */
    int rd_reports = 0, rd_calls = 0, rd_video = 0, rd_audio = 0, rd_errors = 0;
    int rd_counter_resets = 0, rd_last_rc = 0;
    long long rd_since = av_gettime_relative();
    long long rd_read_us = 0, rd_wait_us = 0, rd_max_us = 0, rd_bytes = 0;
    while (demux_thread_running) {
        if (pb_rebuffer_enabled && rd_reports < 24) {
            const long long rd_now = av_gettime_relative();
            if (rd_now - rd_since >= 5000000) {
                struct URLContext *rd_url = ffio_geturlcontext(play_fmt->pb);
                const int rd_fd = rd_url ? ffurl_get_file_handle(rd_url) : -1;
                int rd_recvbuf = -1, rd_sock_rc = -1, rd_sock_error = 0;
                socklen_t rd_sock_len = sizeof(rd_recvbuf);
                if (rd_fd >= 0) {
                    rd_sock_rc = getsockopt(rd_fd, SOL_SOCKET, SO_RCVBUF,
                                           &rd_recvbuf, &rd_sock_len);
                    if (rd_sock_rc < 0) rd_sock_error = errno;
                }
                if (rd_sock_rc != 0 || rd_sock_len != sizeof(rd_recvbuf)) rd_recvbuf = -1;
                evo_boot_log("read path: window=%d elapsed_us=%lld calls=%d read_us=%lld "
                    "max_read_us=%lld queue_wait_us=%lld avio_bytes=%lld io=%d resets=%d "
                    "video=%d audio=%d errors=%d last_rc=%d vq=%d aq=%d paused=%d prebuffer=%d "
                    "socket=%d recvbuf_bytes=%d sock_rc=%d sock_errno=%d sock_len=%u avio_buf=%d",
                    ++rd_reports, rd_now - rd_since, rd_calls, rd_read_us, rd_max_us,
                    rd_wait_us, rd_bytes, play_fmt->pb != NULL, rd_counter_resets,
                    rd_video, rd_audio, rd_errors, rd_last_rc,
                    packet_queue_count(&video_packet_queue), packet_queue_count(&audio_packet_queue),
                    player_paused, (int)pb_prebuffer_hold,
                    rd_fd >= 0, rd_recvbuf, rd_sock_rc, rd_sock_error, (unsigned)rd_sock_len,
                    play_fmt->pb ? play_fmt->pb->buffer_size : 0);
                rd_since = rd_now;
                rd_calls = rd_video = rd_audio = rd_errors = rd_counter_resets = 0;
                rd_read_us = rd_wait_us = rd_max_us = rd_bytes = 0;
            }
        }
        const int rd_enabled = pb_rebuffer_enabled && rd_reports < 24;
        /*
         * Process seek requests before checking the paused state.''')
    replace(demux, '''        int read_result =
            av_read_frame(
                play_fmt,
                pkt
            );

        if (read_result < 0) {''', '''        const long long rd_begin = rd_enabled ? av_gettime_relative() : 0;
        const int64_t rd_before = rd_enabled && play_fmt->pb ? play_fmt->pb->bytes_read : -1;
        int read_result =
            av_read_frame(
                play_fmt,
                pkt
            );
        if (rd_enabled) {
            const long long rd_elapsed = av_gettime_relative() - rd_begin;
            rd_read_us += rd_elapsed;
            if (rd_elapsed > rd_max_us) rd_max_us = rd_elapsed;
            ++rd_calls;
            rd_last_rc = read_result;
            if (read_result < 0) ++rd_errors;
            else if (pkt->stream_index == video_stream_index) ++rd_video;
            else if (pkt->stream_index == audio_stream_index) ++rd_audio;
            if (rd_before >= 0 && play_fmt->pb) {
                const int64_t rd_after = play_fmt->pb->bytes_read;
                if (rd_after >= rd_before) rd_bytes += rd_after - rd_before;
                else ++rd_counter_resets;
            }
        }

        if (read_result < 0) {''')
    for queue, deadline in (
            ('video', 'prebuffer_deadline_ms,\n                                playback_profile >= 3 ? 300 : 500'),
            ('audio', 'prebuffer_deadline_ms, 1000')):
        other = 'audio' if queue == 'video' else 'video'
        call = f'''            demux_wait_for_room(&{queue}_packet_queue, {queue}_packet_cap,
                                {queue}_queue_byte_cap,
                                &{other}_packet_queue, {other}_packet_cap,
                                {deadline});'''
        replace(demux, call, '''            const long long rd_wait_begin = rd_enabled ? av_gettime_relative() : 0;
''' + call + '''
            if (rd_enabled) rd_wait_us += av_gettime_relative() - rd_wait_begin;''')


def patch_playback_progress(app):
    web = app/'src/evo_webui.c'
    replace(web, 'static void serve_evo(int fd, const char *path)',
        (Path(__file__).parent/'ps5-playback-progress.c').read_text() +
        '\nstatic void serve_evo(int fd, const char *path)')
    replace(web, 'static void serve_evo(int fd, const char *path)\n{',
        '''static void serve_evo(int fd, const char *path)
{
    if (!strcmp(path, "/evo/progress") || !strncmp(path, "/evo/progress?", 14)) {
        playback_progress_serve(fd, path);
        return;
    }''')
    replace(web, '        s_h_start = seconds;',
        '''        s_h_start = seconds;
        query_param(path, "session", s_h_progress_session, sizeof s_h_progress_session);
        tlog("handoff: session=%s start=%.3f", s_h_progress_session[0] ? "set" : "empty", seconds);''')
    replace(web, '            s_play_start = s_h_start;',
        '''            s_play_start = s_h_start;
            snprintf(s_play_progress_session, sizeof s_play_progress_session, "%s", s_h_progress_session);''')
    replace(web, '    *start = s_play_start;', '''    *start = s_play_start;
    pthread_mutex_lock(&s_mx);
    snprintf(s_progress_session, sizeof s_progress_session, "%s", s_play_progress_session);
    s_progress_position = s_progress_duration = 0.0;
    s_progress_finished = 0;
    ++s_progress_revision;
    pthread_mutex_unlock(&s_mx);''')
    replace(web, '    if (s_state != P_PLAYING) return;',
        '''    pthread_mutex_lock(&s_mx);
    s_progress_finished = 1;
    ++s_progress_revision;
    pthread_mutex_unlock(&s_mx);
    if (s_state != P_PLAYING) return;''')
    replace(web, '''    while (!s_srv_stop) {
        int c = accept(s_listen_fd, NULL, NULL);''',
        '''    while (!s_srv_stop) {
        playback_progress_checkpoint();
        struct pollfd listener = {s_listen_fd, POLLIN, 0};
        int ready = poll(&listener, 1, 1000);
        if (ready == 0 || (ready < 0 && errno == EINTR)) continue;
        if (ready < 0 || !(listener.revents & POLLIN)) break;
        int c = accept(s_listen_fd, NULL, NULL);''')
    header = app/'include/evo_webui.h'
    replace(header, 'void evo_webui_playback_ended(int played);',
        'void evo_webui_progress_sample(double position, double duration);\nvoid evo_webui_playback_ended(int played);')
    replace(header, 'static inline void evo_webui_playback_ended(int played) { (void)played; }',
        '''static inline void evo_webui_progress_sample(double p, double d) { (void)p; (void)d; }
static inline void evo_webui_playback_ended(int played) { (void)played; }''')
    replace(app/'core/src/Application.cpp', '            double pos = pb->getPositionSeconds();',
        '''            double pos = pb->getPositionSeconds();
            if (!pb->isScrubbing()) {
                evo_webui_progress_sample(pos, pb->getDurationSeconds());
                if (g_web_rep.frames % 600 == 0)
                    EVO_LOGI("web", "progress sample position=%.3f duration=%.3f", pos, pb->getDurationSeconds());
            }''')
    playback = app/'core/src/services/PlaybackController.cpp'
    replace(playback, '#include "evo/services/PlaybackController.hpp"',
        '#include "evo/services/PlaybackController.hpp"\n#include "evo_webui.h"')
    replace(playback, '''void PlaybackController::stopPlayback() {
    if (isActive()) {
        saveResumePosition();''', '''void PlaybackController::stopPlayback() {
    if (isActive()) {
        if (!isScrubbing())
            evo_webui_progress_sample(getPositionSeconds(), getDurationSeconds());
        saveResumePosition();''')


def patch_playback_hui(app):
    """The AGC renderer prefers homebrew-ui over playback.rml on the console."""
    header = app/'ui_kit/include/evo_hui_osd.hpp'
    replace(header, '    void draw_top(hui::gfx::DrawList &list, const Context &ctx) const;',
        '    void draw_nuvio_prompts(hui::gfx::DrawList &list, const Context &ctx) const;\n    void draw_top(hui::gfx::DrawList &list, const Context &ctx) const;')
    source = app/'ui_kit/src/evo_hui_osd.cpp'
    # Upstream now owns the copied skip label. Only native-library playback
    # uses its Triangle prompt; browser handoffs retain Nuvio's R1 policies.
    replace(source, '    if (skip_.value <= 0.01f || skip_label_.empty())',
        '    if (raw_.nuvio_active || skip_.value <= 0.01f || skip_label_.empty())')
    replace(source, 'void OsdScreen::draw_top(DrawList &list, const Context &ctx) const', r'''void OsdScreen::draw_nuvio_prompts(DrawList &list, const Context &ctx) const
{
    if (!raw_.nuvio_active) return;
    const ui::Fonts &fonts = ctx.fonts;
    const Palette &p = ctx.palette;
    if (skip_on_)
    {
        const Rect card{1920 - kMargin - 500, 740, 500, 76};
        list.push_opacity(raw_.skip_countdown > 0 ? 1.0f : 0.5f);
        list.bordered_rect(card, 12, kInk.with_alpha(0.95f), 2, p.accent);
        ui::Hint hint{ui::Button::r1, skip_label_.c_str()};
        ui::HintLayout layout;
        layout.size = 32;
        layout.text_size = 24;
        layout.cy = card.cy();
        ui::draw_hints(list, fonts, ui::GlyphStyle::dark(), &hint, 1, card.x + 24, false, layout);
        if (raw_.skip_countdown > 0)
        {
            const std::string countdown = "Dims in " + std::to_string(raw_.skip_countdown) + "s";
            ui::text(list, fonts.regular, countdown, card.x + card.w - 24, card.y + 46,
                18, kWhite.with_alpha(0.8f), Align::right);
        }
        list.pop_opacity();
    }
    if (raw_.next_episode || raw_.playback_ended)
    {
        const Rect card{1920 - kMargin - 620, !skip_on_ ? 740.0f : 600.0f, 620, 124};
        list.bordered_rect(card, 12, kInk.with_alpha(0.95f), 2, p.accent);
        const std::string label = raw_.next_episode > 0
            ? "Next episode in " + std::to_string(raw_.next_episode) + "s"
            : raw_.next_episode ? "Next episode" : "Playback ended";
        ui::text(list, fonts.semibold, label, card.x + 24, card.y + 38, 24, kWhite);
        ui::Hint hints[3];
        int n = 0;
        if (raw_.next_episode && !skip_on_)
            hints[n++] = {ui::Button::r1, "Play now"};
        if (raw_.next_episode)
            hints[n++] = {ui::Button::l1, "Keep watching"};
        hints[n++] = {ui::Button::circle, "Back to Nuvio"};
        ui::HintLayout layout;
        layout.size = 28;
        layout.text_size = 18;
        layout.item_gap = 20;
        layout.cy = card.y + 88;
        ui::draw_hints(list, fonts, ui::GlyphStyle::dark(), hints, n, card.x + 24, false, layout);
    }
}

void OsdScreen::draw_top(DrawList &list, const Context &ctx) const''')
    replace(source, '        draw_captions(list, ctx, chrome);',
        '        draw_captions(list, ctx, chrome);\n        draw_nuvio_prompts(list, ctx);')
    replace(source, '    return chrome_.value > 0.01f || raw_.scrub_active || raw_.paused;',
        '    return chrome_.value > 0.01f || raw_.scrub_active || raw_.paused ||\n        skip_on_ || raw_.next_episode || raw_.playback_ended;')


def patch_skip_metadata_proxy(source):
    """Fetch only validated IntroDB metadata, never an arbitrary client URL."""
    anchor = 'static void serve_evo(int fd, const char *path)'
    if source.count(anchor) != 1 or source.count('#include "evo_webui.h"') != 1:
        raise RuntimeError('Pinned skip metadata anchors changed')
    source = source.replace('#include "evo_webui.h"', '#include "evo_webui.h"\n#include "evo_net.h"')
    source = source.replace(anchor, r'''static void serve_skip_metadata(int fd, const char *path)
{
    char imdb[32], season[16], episode[16], movie[16], url[256];
    query_param(path, "imdb_id", imdb, sizeof imdb);
    query_param(path, "season", season, sizeof season);
    query_param(path, "episode", episode, sizeof episode);
    query_param(path, "is_movie", movie, sizeof movie);
    int valid_id = !strncmp(imdb, "tt", 2) && imdb[2] &&
        strspn(imdb + 2, "0123456789") == strlen(imdb + 2);
    int series = season[0] && episode[0] &&
        strspn(season, "0123456789") == strlen(season) &&
        strspn(episode, "0123456789") == strlen(episode);
    if (!valid_id || (strcmp(movie, "true") && (movie[0] || !series))) {
        respond(fd, "400 Bad Request", "application/json", "{}", 2);
        return;
    }
    if (!strcmp(movie, "true"))
        snprintf(url, sizeof url, "https://api.introdb.app/segments?imdb_id=%s&is_movie=true", imdb);
    else
        snprintf(url, sizeof url, "https://api.introdb.app/segments?imdb_id=%s&season=%s&episode=%s", imdb, season, episode);
    char *body = NULL;
    size_t length = 0;
    int status = 0;
    int rc = evo_net_http_get_sync(url, NULL, 0, &body, &length, &status);
    tlog("skip metadata: rc=%d status=%d bytes=%zu", rc, status, length);
    if (!rc && status == 200 && body && length <= 32768)
        respond(fd, "200 OK", "application/json", body, length);
    else
        respond(fd, "502 Bad Gateway", "application/json", "{}", 2);
    free(body);
}

''' + anchor)
    source = source.replace(anchor + '\n{', anchor + '''
{
    if (!strncmp(path, "/evo/skip-metadata?", 19)) {
        serve_skip_metadata(fd, path);
        return;
    }''')
    return source


def patch_playback_skip(app):
    """Carry skip intervals and per-segment policy through the browser handoff."""
    web = app/'src/evo_webui.c'
    web.write_text(patch_skip_metadata_proxy(web.read_text()))
    replace(web, 'static void serve_evo(int fd, const char *path)',
        (Path(__file__).parent/'ps5-skip.c').read_text() +
        '\nstatic void serve_evo(int fd, const char *path)')
    replace(web, '        s_h_start = seconds;',
        '        s_h_start = seconds;\n        playback_skip_parse(path);')
    replace(web, '            s_play_start = s_h_start;',
        '            s_play_start = s_h_start;\n            memcpy(s_play_skip, s_h_skip, sizeof s_play_skip);')
    replace(web, '    *start = s_play_start;', '''    *start = s_play_start;
    memcpy(s_skip, s_play_skip, sizeof s_skip);
    int skipRecords = 0;
    for (int i = 0; i < 4; ++i) {
        if (!s_skip[i].type) continue;
        ++skipRecords;
        LOG("skip session: type=%d auto=%d start=%.3f end=%.3f",
            s_skip[i].type, s_skip[i].automatic, s_skip[i].start, s_skip[i].end);
    }
    LOG("skip session: records=%d", skipRecords);
    s_skip_suppressed = -1;
    s_skip_retry_after = 0;
    evo_webui_skip_countdown(0.0, 0, 0);''')
    replace(web, '    if (s_state != P_PLAYING) return;',
        '    memset(s_skip, 0, sizeof s_skip);\n    if (s_state != P_PLAYING) return;')
    header = app/'include/evo_webui.h'
    replace(header, '#include <stddef.h>', '#include <stddef.h>\n#include <stdint.h>')
    replace(header, 'void evo_webui_progress_sample(double position, double duration);',
        '''int evo_webui_skip_interval(double position, double duration, uint64_t now,
                            int consume, double *target);
int evo_webui_skip_countdown(double target, uint64_t now, int running);
void evo_webui_progress_sample(double position, double duration);''')
    replace(header, 'static inline void evo_webui_progress_sample(double p, double d) { (void)p; (void)d; }',
        '''static inline int evo_webui_skip_interval(double p, double d, uint64_t n, int c, double *t)
{ (void)p; (void)d; (void)n; (void)c; (void)t; return 0; }
static inline int evo_webui_skip_countdown(double t, uint64_t n, int r)
{ (void)t; (void)n; (void)r; return 0; }
static inline void evo_webui_progress_sample(double p, double d) { (void)p; (void)d; }''')
    # Keep the prompt eligible in exactly the same states for rendering/input.
    player = app/'core/src/screens/PlayerScreen.cpp'
    replace(player, 'bool PlayerScreen::hasActiveOverlay() const {', '''int PlayerScreen::skipInterval(double* target, int consume) const {
    auto playback = Application::getInstance().getPlaybackController();
    if (!playback || !playback->isActive() || playback->isMusicMode() ||
        playback->isLiveSource() || playback->isScrubbing() || !video_frame_loaded ||
        g_pp_pb.seek_discarding || pb_prebuffer_hold || readerStalled() || m_showStatsForNerds ||
        (consume == 2 && (playback->isPaused() || evo_pb_is_paused())))
        return 0;
    return evo_webui_skip_interval(playback->getPositionSeconds(),
        playback->getDurationSeconds(), NowMs(), consume, target);
}

bool PlayerScreen::hasActiveOverlay() const {
    double target;
    if (skipInterval(&target)) return true;''')
    replace(player, '    if (pressed & PadButtons::R1) {\n        playback->jumpChapter(1);',
        '''    if (pressed & PadButtons::R1) {
        double target;
        if (skipInterval(&target, true)) {
            evo_boot_log("skip R1: action=segment position=%.3f target=%.3f",
                playback->getPositionSeconds(), target);
            playback->seekTo(target);
            return true;
        }
        playback->jumpChapter(1);''')
    replace(player, '    const bool ended = (evo_pb_is_eof() != 0);',
        '''    double autoSkipTarget;
    if (skipInterval(&autoSkipTarget, 2)) {
        playback->seekTo(autoSkipTarget);
        return;
    }
    const bool ended = (evo_pb_is_eof() != 0);''')
    replace(player, '    if (m_osdVisibilityAlpha > 0 && evo_rmlui_is_initialized()) {',
        '''    double skipTarget;
    const int skipType = skipInterval(&skipTarget);
    const char* skipLabel = skipType == 1 ? "Skip intro" : skipType == 2 ? "Skip credits" : skipType == 3 ? "Skip recap" : "";
    const int skipCountdown = evo_webui_skip_countdown(skipType ? skipTarget : 0.0,
        NowMs(), !playback->isPaused() && !evo_pb_is_paused());
    if (m_osdVisibilityAlpha > 0 && evo_rmlui_is_initialized()) {''')
    replace(player, '        p.chrome_hidden = 0;',
        '        p.chrome_hidden = 0;\n        p.skip_label = skipLabel;\n        p.skip_countdown = skipCountdown;')
    replace(player, '    } else if ((activeSubText[0] || secondarySubText[0]',
        '    } else if ((skipType || activeSubText[0] || secondarySubText[0]')
    replace(player, '        p.chrome_hidden = 1;',
        '        p.chrome_hidden = 1;\n        p.skip_label = skipLabel;\n        p.skip_countdown = skipCountdown;')
    replace(app/'core/include/evo/screens/PlayerScreen.hpp',
        '    void initPlayerStateMachine();',
        '    int skipInterval(double* target, int consume = 0) const;\n    void initPlayerStateMachine();')
    replace(app/'ui_rml/include/evo_rmlui_bridge.h', '    int chrome_hidden;',
        '    int chrome_hidden;\n    int skip_countdown; /* Seconds at full opacity, then dim at zero. */')
    text = player.read_text()
    anchor = '        p.skip_label = g_skip.shown >= 0 ? g_skip.label.c_str() : nullptr;'
    if text.count(anchor) != 2: raise RuntimeError('Pinned upstream skip OSD branches changed')
    player.write_text(text.replace(anchor,
        '        p.skip_label = evo_webui_native_requested() ?\n            (g_skip.shown >= 0 ? g_skip.label.c_str() : nullptr) : skipLabel;'))
    replace(player, '    skip_tick(playback, playback->getSource(), now);',
        '    if (evo_webui_native_requested()) skip_tick(playback, playback->getSource(), now);')
    state = app/'ui_rml/include/evo_rmlui_app.h'
    replace(state, 'struct EvoPlaybackState {', 'struct EvoPlaybackState {\n    std::string skip_label;\n    int skip_countdown = 0;')
    replace(state, '        return title == o.title && meta == o.meta && res_badge == o.res_badge &&',
        '        return skip_countdown == o.skip_countdown && skip_label == o.skip_label &&\n               title == o.title && meta == o.meta && res_badge == o.res_badge &&')
    replace(app/'ui_rml/src/evo_rmlui_bridge.cpp', '    state.chrome_hidden = (p->chrome_hidden != 0);',
        '    state.chrome_hidden = (p->chrome_hidden != 0);\n    state.skip_label = p->skip_label ? p->skip_label : "";\n    state.skip_countdown = p->skip_countdown;')
    replace(app/'ui_rml/src/evo_rmlui_app.cpp', '    m_last_state = state;', r'''    if (state.skip_label != m_last_state.skip_label) {
        if (auto* prompt = m_playback_doc->GetElementById("nuvio-skip")) {
            prompt->SetProperty("display", state.skip_label.empty() ? "none" : "flex");
            if (auto* label = m_playback_doc->GetElementById("nuvio-skip-label"))
                label->SetInnerRML(state.skip_label);
        }
        if (auto* chapter = m_playback_doc->GetElementById("item-chapter"))
            chapter->SetInnerRML(state.skip_label.empty()
                ? "<span class=\"btn-tag\">L1 / R1</span><span class=\"control-label\">CHAPTER</span>"
                : "<span class=\"btn-tag\">L1</span><span class=\"control-label\">CHAPTER</span>");
    }
    if (state.skip_countdown != m_last_state.skip_countdown || state.skip_label != m_last_state.skip_label) {
        if (auto* prompt = m_playback_doc->GetElementById("nuvio-skip"))
            prompt->SetProperty("opacity", state.skip_countdown > 0 ? "1" : "0.5");
        if (auto* countdown = m_playback_doc->GetElementById("nuvio-skip-countdown")) {
            countdown->SetProperty("display", state.skip_countdown > 0 ? "block" : "none");
            countdown->SetInnerRML("Dims in " + std::to_string(state.skip_countdown) + "s");
        }
    }
    m_last_state = state;''')
    replace(app/'assets/rml/playback.rml', '    <!-- Bottom Netflix Controller Bar -->',
        '''    <div id="nuvio-skip"><span class="btn-tag">R1</span><span id="nuvio-skip-label"></span><span id="nuvio-skip-countdown"></span></div>

    <!-- Bottom Netflix Controller Bar -->''')
    css = app/'assets/rml/playback.rcss'
    css.write_text(css.read_text() + '''
/* Independent of the fading controls and clear of the subtitle centre. */
#nuvio-skip {
    display: none;
    position: absolute;
    right: 60dp;
    bottom: 260dp;
    height: 64dp;
    padding: 0 24dp;
    align-items: center;
    gap: 16dp;
    background-color: #101827f2;
    border: 2dp #8bb9ff;
    border-radius: 12dp;
    font-size: 24dp;
    font-weight: bold;
}
#nuvio-skip-countdown {
    font-size: 18dp;
    font-weight: normal;
    color: #c5d3e5;
}
''')


def patch_next_episode(app):
    web = app/'src/evo_webui.c'
    replace(web, 'static void serve_evo(int fd, const char *path)',
        (Path(__file__).parent/'ps5-next.c').read_text() +
        '\nstatic void serve_evo(int fd, const char *path)')
    replace(web, '        playback_skip_parse(path);',
        '        playback_skip_parse(path);\n        playback_next_parse(path);')
    replace(web, '            memcpy(s_play_skip, s_h_skip, sizeof s_play_skip);',
        '            memcpy(s_play_skip, s_h_skip, sizeof s_play_skip);\n            s_play_next = s_h_next;')
    replace(web, '    evo_webui_skip_countdown(0.0, 0, 0);',
        '    evo_webui_skip_countdown(0.0, 0, 0);\n    playback_next_begin();')
    replace(web, '    s_progress_finished = 0;',
        '    s_progress_finished = 0;\n    s_progress_next_episode = 0;\n    s_progress_return_detail = 0;')
    replace(web, '    memset(s_skip, 0, sizeof s_skip);',
        '''    memset(s_skip, 0, sizeof s_skip);
    /* A later native-library source has no browser handoff to replace this. */
    memset(&s_play_next, 0, sizeof s_play_next);
    playback_next_begin();''')
    header = app/'include/evo_webui.h'
    replace(header, 'int evo_webui_skip_countdown(double target, uint64_t now, int running);',
        '''int evo_webui_skip_countdown(double target, uint64_t now, int running);
int evo_webui_next_episode(double position, double duration, uint64_t now, int running, int visible, int action);''')
    replace(header, 'static inline int evo_webui_skip_countdown(double t, uint64_t n, int r)',
        '''static inline int evo_webui_next_episode(double p, double d, uint64_t n, int r, int v, int a)
{ (void)p; (void)d; (void)n; (void)r; (void)v; (void)a; return 0; }
static inline int evo_webui_skip_countdown(double t, uint64_t n, int r)''')
    player = app/'core/src/screens/PlayerScreen.cpp'
    replace(player, 'bool PlayerScreen::hasActiveOverlay() const {', '''int PlayerScreen::nextEpisode(int action) const {
    auto playback = Application::getInstance().getPlaybackController();
    const bool ended = evo_pb_is_eof() != 0;
    const bool visible = !evo_webui_native_requested() && playback && playback->isActive() && !playback->isMusicMode() &&
        !playback->isLiveSource() && !playback->isScrubbing() && video_frame_loaded &&
        !g_pp_pb.seek_discarding && !m_showStatsForNerds && !evo_pb_decode_fatal() &&
        (ended || (!pb_prebuffer_hold && !readerStalled()));
    double position = playback ? playback->getPositionSeconds() : 0.0;
    const double duration = playback ? playback->getDurationSeconds() : 0.0;
    if (ended && position >= duration - 2.0) position = duration;
    return evo_webui_next_episode(position, duration, NowMs(),
        playback && !playback->isPaused() && !evo_pb_is_paused(), visible, action);
}

bool PlayerScreen::hasActiveOverlay() const {
    if (m_nextEpisodeState || m_playbackEnded) return true;''')
    replace(player, '''void PlayerScreen::onExit() {
    StatefulScreen::onExit();''', '''void PlayerScreen::onExit() {
    evo_webui_next_episode(0.0, 0.0, NowMs(), 0, 0, 0);
    m_nextEpisodeState = 0;
    m_playbackEnded = false;
    StatefulScreen::onExit();''')
    replace(player, '    if (pressed & PadButtons::L1) {\n        playback->jumpChapter(-1);',
        '''    if (pressed & PadButtons::L1) {
        if (m_nextEpisodeState) { nextEpisode(2); m_nextEpisodeState = 0; return true; }
        playback->jumpChapter(-1);''')
    replace(player, '        playback->jumpChapter(1);', '''        if (m_nextEpisodeState && nextEpisode(1) == -2) {
            playback->stopPlayback();
            if (screenMgr) screenMgr->returnFromPlayback();
            return true;
        }
        evo_boot_log("skip R1: action=chapter position=%.3f", playback->getPositionSeconds());
        playback->jumpChapter(1);''')
    replace(player, '    const bool ended = (evo_pb_is_eof() != 0);',
        '''    const bool ended = (evo_pb_is_eof() != 0);
    m_playbackEnded = !evo_webui_native_requested() && evo_pb_is_finished() &&
        !playback->isMusicMode() && !playback->isLiveSource() && !playback->isScrubbing() &&
        video_frame_loaded && !g_pp_pb.seek_discarding && !m_showStatsForNerds;
    m_nextEpisodeState = nextEpisode();
    if (m_nextEpisodeState == -2) {
        playback->stopPlayback();
        if (auto sm = Application::getInstance().getScreenManager()) sm->returnFromPlayback();
        m_nextEpisodeState = 0;
        return;
    }''')
    replace(player, '    } else if ((skipType || activeSubText[0] || secondarySubText[0]',
        '    } else if ((m_nextEpisodeState || m_playbackEnded || skipType || activeSubText[0] || secondarySubText[0]')
    source = player.read_text()
    if source.count('        p.skip_countdown = skipCountdown;') != 2:
        raise RuntimeError('Pinned next-episode OSD branches changed')
    player.write_text(source.replace('        p.skip_countdown = skipCountdown;',
        '        p.skip_countdown = skipCountdown;\n        p.next_episode = m_nextEpisodeState;\n        p.playback_ended = m_playbackEnded;'))
    replace(app/'core/include/evo/screens/PlayerScreen.hpp', '    void initPlayerStateMachine();',
        '    int nextEpisode(int action = 0) const;\n    int m_nextEpisodeState = 0;\n    bool m_playbackEnded = false;\n    void initPlayerStateMachine();')
    replace(app/'ui_rml/include/evo_rmlui_bridge.h', '    int skip_countdown;',
        '    int playback_ended;\n    int next_episode; /* 0 hidden, -1 manual, positive countdown. */\n    int skip_countdown;')
    state = app/'ui_rml/include/evo_rmlui_app.h'
    replace(state, '    int skip_countdown = 0;', '    int playback_ended = 0;\n    int next_episode = 0;\n    int skip_countdown = 0;')
    replace(state, '        return skip_countdown == o.skip_countdown',
        '        return playback_ended == o.playback_ended && next_episode == o.next_episode && skip_countdown == o.skip_countdown')
    replace(app/'ui_rml/src/evo_rmlui_bridge.cpp', '    state.skip_countdown = p->skip_countdown;',
        '    state.skip_countdown = p->skip_countdown;\n    state.next_episode = p->next_episode;\n    state.playback_ended = p->playback_ended;')
    replace(app/'ui_rml/src/evo_rmlui_app.cpp', '    m_last_state = state;', r'''    if (state.next_episode != m_last_state.next_episode || state.playback_ended != m_last_state.playback_ended || state.skip_label != m_last_state.skip_label) {
        if (auto* prompt = m_playback_doc->GetElementById("nuvio-next"))
            prompt->SetProperty("display", state.next_episode || state.playback_ended ? "flex" : "none");
        if (auto* label = m_playback_doc->GetElementById("nuvio-next-label"))
            label->SetInnerRML(state.next_episode > 0
                ? "Next episode in " + std::to_string(state.next_episode) + "s"
                : state.next_episode ? "Next episode" : "Playback ended");
        if (auto* play = m_playback_doc->GetElementById("nuvio-next-play"))
            play->SetProperty("display", state.next_episode && state.skip_label.empty() ? "flex" : "none");
        if (auto* keep = m_playback_doc->GetElementById("nuvio-next-keep"))
            keep->SetProperty("display", state.next_episode ? "flex" : "none");
    }
    m_last_state = state;''')
    replace(app/'ui_rml/src/evo_rmlui_app.cpp',
        '                e->SetProperty("display", live_off);',
        '''                e->SetProperty("display", state.next_episode && std::strcmp(id, "item-chapter") == 0
                    ? "none" : live_off);''')
    replace(app/'assets/rml/playback.rml', '    <!-- Bottom Netflix Controller Bar -->',
        '''    <div id="nuvio-next"><span id="nuvio-next-label"></span><span id="nuvio-next-play"><span class="btn-tag">R1</span><span>Play now</span></span><span id="nuvio-next-keep"><span class="btn-tag">L1</span><span>Keep watching</span></span><span class="btn-tag">O</span><span>Back to Nuvio</span></div>

    <!-- Bottom Netflix Controller Bar -->''')
    css = app/'assets/rml/playback.rcss'
    css.write_text(css.read_text() + '''
#nuvio-next {
    display: none;
    position: absolute;
    right: 60dp;
    bottom: 340dp;
    height: 64dp;
    padding: 0 24dp;
    align-items: center;
    gap: 16dp;
    background-color: #101827f2;
    border: 2dp #8bb9ff;
    border-radius: 12dp;
    font-size: 24dp;
}
#nuvio-next-label { font-weight: bold; }
#nuvio-next-play, #nuvio-next-keep { display: flex; align-items: center; gap: 12dp; }
''')


def patch_playback_end(app):
    # Demux EOF can precede the last decoded frame by an entire read-ahead
    # buffer. Publish completion only once video and queued audio have drained.
    media = app/'media/src/evo_playback.c'
    replace(media, 'static int s_vdec_fatal_streak = 0;',
        'static int s_vdec_fatal_streak = 0;\nstatic volatile int s_video_drained;')
    replace(media, '    s_vdec_fatal_streak = 0;\n}',
        '    s_vdec_fatal_streak = 0;\n    s_video_drained = 0;\n}')
    replace(media, '    if (!video_decode_ready || player_paused) return 0;',
        '    if (!video_decode_done) s_video_drained = 0;\n    if (!video_decode_ready || player_paused) return 0;')
    replace(media, '        if (recv_ret >= 1) {',
        '        if (recv_ret >= 1) {\n            s_video_drained = 0;')
    replace(media, '''            return 0;
        }

        int64_t send_pts_us''', '''            s_video_drained = 1;
            return 0;
        }

        int64_t send_pts_us''')
    replace(media, 'int evo_pb_is_eof(void)            { return video_decode_done; }',
        '''int evo_pb_is_eof(void)            { return video_decode_done; }
int evo_pb_is_finished(void) {
    return video_decode_done && s_video_drained && !video_video_pending_pkt &&
        packet_queue_count(&video_packet_queue) == 0 &&
        packet_queue_count(&audio_packet_queue) == 0 && audio_queue_count == 0;
}''')
    replace(app/'media/include/evo_playback.h', 'int    evo_pb_is_eof(void);',
        'int    evo_pb_is_finished(void); /* demux EOF and drained playback */\nint    evo_pb_is_eof(void);')
    header = app/'include/evo_webui.h'
    replace(header, 'int evo_webui_next_episode(double position,',
        'void evo_webui_return_to_nuvio(void);\nint evo_webui_next_episode(double position,')
    replace(header, 'static inline int evo_webui_next_episode(double p,',
        'static inline void evo_webui_return_to_nuvio(void) {}\nstatic inline int evo_webui_next_episode(double p,')
    player = app/'core/src/screens/PlayerScreen.cpp'
    replace(player, '''        if (!evo_webui_native_requested()) {
            playback->stopPlayback();''', '''        if (!evo_webui_native_requested()) {
            if (m_nextEpisodeState || m_playbackEnded) evo_webui_return_to_nuvio();
            playback->stopPlayback();''')
    replace(player, '    const bool stalled = readerStalled();',
        '    const bool stalled = !evo_pb_is_finished() && readerStalled();')
    replace(player, '    const bool isBuffering = !playback->isMusicMode() &&',
        '    const bool isBuffering = !evo_pb_is_finished() && !playback->isMusicMode() &&')
    replace(player, '        if (readerStalled())\n            metaStr =',
        '        if (m_playbackEnded)\n            metaStr = "PLAYBACK ENDED";\n        else if (readerStalled())\n            metaStr =')
    # Keep recovery, buffering UI and private logs. Only connection toasts are
    # hidden for Nuvio sessions; native-library playback retains upstream UX.
    demux = app/'media/src/evo_demux.c'
    replace(demux, '#include "evo_parallel_io.h"', '#include "evo_parallel_io.h"\n#include "evo_webui.h"')
    for path, messages in ((player, (
        'toast("CONNECTION LOST", "Can\'t get data from the server - retrying...");',
        'toast("CONNECTION", "Reconnected - the stream is back");')),
        (demux, (
        'toast("CONNECTION LOST", "The stream dropped - reconnecting...");',
        'toast("CONNECTION", "Reconnected - the stream is back");',
        'toast("PLAYBACK ERROR", "The connection did not come back - stream stopped");'))):
        for message in messages:
            replace(path, message, 'if (evo_webui_native_requested()) ' + message)
