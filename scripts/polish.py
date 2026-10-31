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
    patch_playback_progress(app)
    web.write_text(patch_controller_hook(web.read_text()))
    web.write_text(patch_storage_hook(web.read_text()))
    patch_search_keyboard(app)
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
    if (status && status->GetInnerRML() != (message ? message : "Opening Nuvio"))
        status->SetInnerRML(message ? message : "Opening Nuvio");
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
    application=app/'core/src/Application.cpp'
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
                                     pressed & PadButtons::Triangle, direction);''')
    h=app/'include/evo_webui.h'
    h.write_text(h.read_text()+'\n#ifdef __cplusplus\nextern "C"\n#endif\nvoid evo_webui_controller(int options, int menu, int direction);\n')
    replace(application,'std::atomic<bool> g_web_done{false};','std::atomic<bool> g_web_done{false};\nbool g_nuvio_preparing = false;')
    replace(application,'        g_web_src = PlaybackSource();','        g_nuvio_preparing = true;\n        g_web_src = PlaybackSource();')
    replace(application,'        pthread_join(g_web_thread, nullptr);','        pthread_join(g_web_thread, nullptr);\n        g_nuvio_preparing = false;')
    replace(application,'        bool isSurround = (m_screenManager->getCurrentScreenId() == ScreenId::SurroundTest);','        bool nuvioShell = !isPlayer &&\n            !(m_playbackController && m_playbackController->isActive()) &&\n            !evo_webui_native_requested();\n        bool isSurround = (m_screenManager->getCurrentScreenId() == ScreenId::SurroundTest);')
    replace(application,'int uiActive = (frame < 10) || isPlayer || isSurround || hasInput || hasAnim ||','int uiActive = nuvioShell || (frame < 10) || isPlayer || isSurround || hasInput || hasAnim ||')
    source=application.read_text();anchor='                m_screenManager->render(m_uiScratch, DisplayWidth, DisplayHeight);'
    if source.count(anchor)!=2:raise RuntimeError('Pinned render branches changed')
    before,after=source.rsplit(anchor,1)
    application.write_text(before+'''                if (nuvioShell)
                    evo_rmlui_render_nuvio(m_uiScratch, DisplayWidth, DisplayHeight,
                        g_nuvio_preparing ? "Preparing playback" : "Opening Nuvio");
                else
                    m_screenManager->render(m_uiScratch, DisplayWidth, DisplayHeight);'''+after)
    asset=Path(__file__).resolve().parent.parent/'assets'
    shutil.copyfile(asset/'nuvio.rml',app/'assets/rml/nuvio.rml')
    shutil.copyfile(nuvio/'assets/brand/app_logo_wordmark.png',app/'assets/icons/nuvio-wordmark.png')
    # Fixed-size repository artwork: the title icon and the launch screens.
    shutil.copyfile(asset/'icon.png',app/'sce_sys/icon0.png')
    for name in ('pic0.png','pic1.png'):
        shutil.copyfile(asset/'launch.png',app/'sce_sys'/name)


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
" x.send(sv);if(x.status===204)lastSnap=sv;}catch(e){}}"'''
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


def patch_collection_filters(text):
    # Number(null) must not create a zero rating ceiling during normalization.
    for field in ('voteAverageGte', 'voteAverageLte', 'voteCountGte'):
        old=f'Number.isFinite(Number(raw.{field}))'
        if text.count(old)!=1:
            raise RuntimeError('Pinned collection filter changed: '+field)
        text=text.replace(old, f'raw.{field} != null && '+old)
    return text


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


def patch_nuvio(nuvio):
    replace(nuvio/'js/platform/adapters/browserAdapter.js',
        '    return "Web Browser";',
        '    return globalThis.__NUVIO_PS5__ ? "PS5" : "Web Browser";')
    replace(nuvio/'js/core/auth/deviceSessionRegistration.js',
        '  const platformName = normalizedText(platform.getName?.()).toLowerCase();',
        '''  if (runtime.__NUVIO_PS5__) {
    return { clientName: CLIENT_NAME, deviceName: "PS5", platform: "PS5" };
  }
  const platformName = normalizedText(platform.getName?.()).toLowerCase();''')
    replace(nuvio/'js/core/profile/profileSelectionScreenMethods-01-mount.js',
        't("profile_selection_hint", {}, "Hold to manage profile")',
        '(globalThis.__NUVIO_PS5__ ? "Press Square or Options to manage profile" : '
        't("profile_selection_hint", {}, "Hold to manage profile"))')
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
    search_actions=nuvio/'js/ui/screens/search/searchScreenMethods-06-activate-action-node.js'
    search_actions.write_text(patch_search_back(search_actions.read_text()))
    replace(navigation/'focusEngine.js',
        'import { Router } from "./routerState.js";',
        'import { Router } from "./routerState.js";\nimport { initPs5Navigation } from "./ps5-navigation.js";')
    replace(navigation/'focusEngine.js', '  init() {', '  init() {\n    initPs5Navigation();')
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
        '''      // PS5 Search must paint within the Triangle user gesture so
      // focusing its real input can request the browser's native keyboard.
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
    collections=nuvio/'js/data/local/collectionsStore.js'
    collections.write_text(patch_collection_filters(collections.read_text()))
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
    replace(nuvio/'js/ui/screens/stream/streamScreenMethods-05-maybe-auto-resume-stream.js',
        '''      if (this.autoResumeAttempted) {
        return;
      }''',
        '''      if (this.autoResumeAttempted) {
        return;
      }
      // Manual selection must also bypass the progress stream identity.
      // Disabling only stored-link reuse still allowed an automatic launch.
      if (globalThis.__NUVIO_PS5__ && this.params?.manualSelection) {
        this.autoResumeUiActive = false;
        return;
      }''')
    settings=nuvio/'js/ui/screens/settings/settingsScreenMethods-14-activate-focused.js'
    replace(settings,
        'if ((code === 38 || code === 40) && !(activeField && this.textDialog.multiline)) {',
        'if ((code === 38 || code === 40) && (globalThis.__NUVIO_PS5__ || !(activeField && this.textDialog.multiline))) {')
    replace(nuvio/'js/ui/screens/settings/settingsScreenMethods-10-render-playback-section.js',
        '      registerPlaybackActionsPart02.call(this, model);',
        '''      registerPlaybackActionsPart02.call(this, model);
      if (globalThis.__NUVIO_PS5__) {
        this.actionMap.set("playback:ps5-native", () => document.getElementById("__evoClose")?.click());
      }''')
    replace(nuvio/'js/ui/screens/settings/settingsScreenPlaybackMarkup-06-section.js',
        '          ${this.renderSectionHeader(SECTION_META.find((item) => item.id === "playback"))}',
        '''          ${this.renderSectionHeader(SECTION_META.find((item) => item.id === "playback"))}
          ${globalThis.__NUVIO_PS5__ ? this.renderActionRow({ focusKey: "playback:ps5-native", title: "Player settings", subtitle: "Open the native PS5 player settings" }) : ""}''')
    router=nuvio/'js/ui/navigation/routerMethods-02-complete-route-return-back-guard.js'
    router.write_text(patch_resume_router(router.read_text()))
    app=nuvio/'js/app.js'
    replace(app, 'let hasSelectedProfileThisSession = false;',
        'let hasSelectedProfileThisSession = false;\n' +
        (Path(__file__).parent/'ps5-resume.js').read_text() + '\n' +
        (Path(__file__).parent/'ps5-playback-progress.js').read_text())
    replace(app, 'async function enterWithLastProfile({ restoreWebOsRoute = false } = {}) {',
        '''async function enterWithLastProfile({ restoreWebOsRoute = false } = {}) {
  await restorePs5PlaybackProgress();''')
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


def patch_search_keyboard(app):
    keyboard=app/'ui/src/evo_keyboard.c'
    source=keyboard.read_text()
    signature='evo_keyboard_cb on_submit, void *userdata, int phone)'
    if source.count(signature)!=2:
        raise RuntimeError('Pinned keyboard signatures changed')
    source=source.replace(signature, signature[:-1]+', int native_only)')
    keyboard.write_text(source)
    replace(keyboard, 'on_submit, userdata, 0);', 'on_submit, userdata, 0, 0);')
    replace(keyboard, 'on_submit, userdata, 1);', 'on_submit, userdata, 1, 0);')
    replace(keyboard,
        'if (g_kb_type == EVO_KEYBOARD_TYPE_NATIVE && !g_native_ime_broken && !phone) {',
        'if ((native_only || g_kb_type == EVO_KEYBOARD_TYPE_NATIVE) && !g_native_ime_broken && !phone) {')
    replace(keyboard, '        if (cd_rc != 0) {',
        '        if (cd_rc != 0) {\n            if (native_only) { g_kb.is_open = 0; return; }')
    replace(keyboard,
        '        g_native_ime_broken = 1;\n        char err_msg[64];',
        '        if (native_only) { g_kb.is_open = 0; return; }\n        g_native_ime_broken = 1;\n        char err_msg[64];')
    replace(keyboard,
        '    g_kb.is_native_active = 0;\n    evo_feedback(EVO_FB_OPEN);',
        '    if (native_only) { g_kb.is_open = 0; return; }\n    g_kb.is_native_active = 0;\n    evo_feedback(EVO_FB_OPEN);')
    # Diagnostic only: keep the existing NONE/FINISHED handling unchanged.
    replace(keyboard, '#include <string.h>', '#include <string.h>\n#include <time.h>')
    replace(keyboard, 'static uint16_t g_ime_buf[1024];', '''static struct timespec s_ime_trace_start;
static int s_ime_trace_status, s_ime_trace_changes, s_ime_trace_checkpoint;

static long ime_trace_ms(void)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (now.tv_sec - s_ime_trace_start.tv_sec) * 1000L +
           (now.tv_nsec - s_ime_trace_start.tv_nsec) / 1000000L;
}

static uint16_t g_ime_buf[1024];''')
    replace(keyboard, '        int rc = sceImeDialogInit(&param, NULL);', '''        clock_gettime(CLOCK_MONOTONIC, &s_ime_trace_start);
        s_ime_trace_status = -1;
        s_ime_trace_changes = 0;
        s_ime_trace_checkpoint = 0;
        int rc = sceImeDialogInit(&param, NULL);''')
    replace(keyboard, '        int status = sceImeDialogGetStatus();', '''        int status = sceImeDialogGetStatus();
        long elapsed = ime_trace_ms();
        int checkpoint = elapsed >= 10000 ? 3 : elapsed >= 5000 ? 2 : elapsed >= 1000 ? 1 : 0;
        if ((status != s_ime_trace_status && s_ime_trace_changes < 16) ||
            checkpoint > s_ime_trace_checkpoint) {
            evo_log("ime trace: status=%d elapsed_ms=%ld open=%d native=%d",
                    status, elapsed, g_kb.is_open, g_kb.is_native_active);
            evo_log_flush();
            if (status != s_ime_trace_status) ++s_ime_trace_changes;
        }
        s_ime_trace_status = status;
        s_ime_trace_checkpoint = checkpoint;''')
    replace(keyboard, '            sceImeDialogGetResult(&result);', '''            int result_rc = sceImeDialogGetResult(&result);
            evo_log("ime trace: GetResult rc=0x%08x end=%d elapsed_ms=%ld",
                    (unsigned)result_rc, result.endStatus, ime_trace_ms());
            evo_log_flush();''')
    # Capture every existing cleanup call without changing its result handling.
    source = keyboard.read_text()
    source = source.replace('        sceImeDialogAbort();', '''        int abort_rc = sceImeDialogAbort();
        evo_log("ime trace: Abort rc=0x%08x elapsed_ms=%ld", (unsigned)abort_rc, ime_trace_ms());
        evo_log_flush();''')
    if source.count('sceImeDialogTerm();') != 3:
        raise RuntimeError('Pinned IME cleanup paths changed')
    source = source.replace('sceImeDialogTerm();', '''int term_rc = sceImeDialogTerm();
        evo_log("ime trace: Term rc=0x%08x elapsed_ms=%ld", (unsigned)term_rc, ime_trace_ms());
        evo_log_flush();''')
    keyboard.write_text(source)
    keyboard.write_text(keyboard.read_text()+'''
/* Browser Search must not silently replace the PS5 keyboard with EVO's UI.
 * A busy browser/CommonDialog refusal is not a permanent native-IME failure. */
int evo_keyboard_open_native(const char *title, const char *initial_value,
                             int max_len, evo_keyboard_cb callback, void *userdata)
{
    if (g_kb.is_open || g_native_ime_broken) return 0;
    kb_open(title, initial_value, max_len, callback, userdata, 0, 1);
    return evo_keyboard_is_native_active();
}
''')
    header=app/'ui/include/evo_keyboard.h'
    replace(header, 'void evo_keyboard_close(void);',
        '''int evo_keyboard_open_native(const char *title, const char *initial_value,
                             int max_len, evo_keyboard_cb callback, void *userdata);
void evo_keyboard_close(void);''')
    web=app/'src/evo_webui.c'
    replace(web, 'static void serve_evo(int fd, const char *path)',
        '#include "evo_keyboard.h"\n'+(Path(__file__).parent/'ps5-text-input.c').read_text()+
        '\n'+(Path(__file__).parent/'ps5-text-input-session.c').read_text()+
        '\nstatic void serve_evo(int fd, const char *path)')
    replace(web, '    if (!strncmp(path, "/evo/hook.js", 12)) {',
        '''    if (!strcmp(path, "/evo/text-input") || !strncmp(path, "/evo/text-input?", 16)) {
        text_input_serve(fd, path);
    } else if (!strncmp(path, "/evo/hook.js", 12)) {''')
    replace(web, 'void evo_webui_pump(void)\n{',
        'void evo_webui_pump(void)\n{\n    if (text_input_session_pump()) { tlog_drain(); return; }')
    replace(web, '    return s_state == P_RUN || s_state == P_CLOSING;',
        '    return s_text_phase || s_state == P_RUN || s_state == P_CLOSING;')
    replace(web, '"setInterval(function(){saveNow(0);},5000);"',
        '"window.__nuvioPrepareKeyboard=function(){saveNow(1);};"\n'
        '"setInterval(function(){saveNow(0);},5000);"')


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
    source=source.replace(anchor, anchor+'\nstatic uint32_t s_controller_options, s_controller_menu, s_controller_navigation;\nstatic int s_controller_direction;')
    anchor='    } else if (!strncmp(path, "/evo/close", 10)) {'
    if source.count(anchor)!=1:
        raise RuntimeError('Pinned controller endpoint anchor changed')
    source=source.replace(anchor, '''    } else if (!strcmp(path, "/evo/controller")) {
        char body[160];
        pthread_mutex_lock(&s_mx);
        int n = snprintf(body, sizeof body, "{\\"options\\":%u,\\"menu\\":%u,\\"navigation\\":%u,\\"direction\\":%d}",
                         (unsigned)s_controller_options, (unsigned)s_controller_menu,
                         (unsigned)s_controller_navigation, s_controller_direction);
        pthread_mutex_unlock(&s_mx);
        respond(fd, "200 OK", "application/json", body, (size_t)n);
'''+anchor)
    return source+'''
void evo_webui_controller(int options, int menu, int direction) {
    pthread_mutex_lock(&s_mx);
    if (options) ++s_controller_options;
    if (menu) ++s_controller_menu;
    if (direction >= 1 && direction <= 4) {
        ++s_controller_navigation;
        s_controller_direction = direction;
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
    new = ('" function go(t){if(done)return;done=1;var back=good,start=0,session=\'\';"\n'
           '" if(NUVIO){if(window.__nuvioSavePlaybackReturn)session=window.__nuvioSavePlaybackReturn()||\'\';"\n'
           '" if(window.__nuvioPlaybackStartSeconds)start=window.__nuvioPlaybackStartSeconds();"\n'
           '" var ret=new URL(good,location.href);ret.searchParams.set(\\"nuvioPlaybackReturn\\",\\"1\\");back=ret.href;}saveNow(1);"')
    return source.replace(old, new).replace(end,
        "encodeURIComponent(back)+'&start='+encodeURIComponent(start)+'&session='+encodeURIComponent(session));}")


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
        query_param(path, "session", s_h_progress_session, sizeof s_h_progress_session);''')
    replace(web, '            s_play_start = s_h_start;',
        '''            s_play_start = s_h_start;
            snprintf(s_play_progress_session, sizeof s_play_progress_session, "%s", s_h_progress_session);''')
    replace(web, '    *start = s_play_start;', '''    *start = s_play_start;
    pthread_mutex_lock(&s_mx);
    snprintf(s_progress_session, sizeof s_progress_session, "%s", s_play_progress_session);
    s_progress_position = s_progress_duration = 0.0;
    s_progress_finished = 0;
    pthread_mutex_unlock(&s_mx);''')
    replace(web, '    if (s_state != P_PLAYING) return;',
        '''    if (s_state != P_PLAYING) return;
    pthread_mutex_lock(&s_mx);
    s_progress_finished = 1;
    pthread_mutex_unlock(&s_mx);''')
    header = app/'include/evo_webui.h'
    replace(header, 'void evo_webui_playback_ended(int played);',
        'void evo_webui_progress_sample(double position, double duration);\nvoid evo_webui_playback_ended(int played);')
    replace(header, 'static inline void evo_webui_playback_ended(int played) { (void)played; }',
        '''static inline void evo_webui_progress_sample(double p, double d) { (void)p; (void)d; }
static inline void evo_webui_playback_ended(int played) { (void)played; }''')
    replace(app/'core/src/Application.cpp', '            double pos = pb->getPositionSeconds();',
        '''            double pos = pb->getPositionSeconds();
            if (!pb->isScrubbing())
                evo_webui_progress_sample(pos, pb->getDurationSeconds());''')
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
