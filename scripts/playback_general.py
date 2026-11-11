"""Pinned frontend-only General settings adapter; native integration is separate."""
from pathlib import Path


def patch_frontend(nuvio):
    # polish imports this adapter after applying its existing frontend changes.
    from polish import replace

    nuvio = Path(nuvio)
    app = nuvio / 'js/app.js'
    replace(app, 'let hasSelectedProfileThisSession = false;',
            'let hasSelectedProfileThisSession = false;\n' +
            (Path(__file__).parent / 'ps5-general.js').read_text())
    replace(app, 'import { PlayerController } from "./core/player/playerController.js";',
            '''import { PlayerController } from "./core/player/playerController.js";
import { StreamPreferencesStore } from "./data/local/streamPreferencesStore.js";
import { parentalGuideRepository } from "./data/repository/parentalGuideRepository.js";
import { buildLocalizedParentalWarnings } from "./ui/screens/player/playerScreenHelpers-11-flatten-stream-groups.js";
import { normalizePlayerEpisodeMetadata } from "./core/player/playerEpisodeMetadata.js";
import { PostPlayRecommendationController, shouldUsePostPlayRecommendation } from "./ui/screens/player/postPlayRecommendationController.js";''')
    player = nuvio / 'js/ui/screens/player/playerScreenMethods-06-handle-post-play-key.js'
    replace(player, '''      StreamPreferencesStore.set(prefContentId, prefVideoId, streamCandidate.id, {
        bingeGroup: streamCandidate?.behaviorHints?.bingeGroup || streamCandidate?.raw?.behaviorHints?.bingeGroup || "",
        filename: streamCandidate?.behaviorHints?.filename || streamCandidate?.raw?.behaviorHints?.filename || null,
        infoHash: streamCandidate?.infoHash || streamCandidate?.raw?.infoHash || null,
        resumeIdentity: buildStreamResumeIdentity(streamCandidate)
      });''', '''      const metadata = {
        bingeGroup: streamCandidate?.behaviorHints?.bingeGroup || streamCandidate?.raw?.behaviorHints?.bingeGroup || "",
        filename: streamCandidate?.behaviorHints?.filename || streamCandidate?.raw?.behaviorHints?.filename || null,
        infoHash: streamCandidate?.infoHash || streamCandidate?.raw?.infoHash || null,
        resumeIdentity: buildStreamResumeIdentity(streamCandidate)
      };
      if (globalThis.__NUVIO_PS5__) {
        globalThis.__nuvioDeferStreamPreference?.(this, prefContentId, prefVideoId, streamCandidate.id, metadata);
        return;
      }
      StreamPreferencesStore.set(prefContentId, prefVideoId, streamCandidate.id, metadata);''')
    # A non-Tizen browser is not proof of plugin execution. Match the real
    # PluginServiceClient browser capability rather than opting into a runtime.
    helper = nuvio / 'js/ui/screens/settings/settingsScreenHelpers-04-row-icons.js'
    replace(helper, '''export function arePluginsSupported() {
  return TizenCapabilities.canUsePlugins();
}''', '''export function arePluginsSupported() {
  return !globalThis.__NUVIO_PS5__ &&
    (!Platform.isBrowser() || globalThis.__NUVIO_ALLOW_BROWSER_PLUGIN_RUNTIME__ === true) &&
    TizenCapabilities.canUsePlugins();
}''')
    actions = nuvio / 'js/ui/screens/settings/settingsScreenPlaybackActions-01.js'
    replace(actions, '      options: STREAM_AUTOPLAY_SOURCE_OPTIONS,',
            '''      options: STREAM_AUTOPLAY_SOURCE_OPTIONS.filter(option =>
        option.id !== "ENABLED_PLUGINS_ONLY" || arePluginsSupported()),''')
    capabilities = nuvio / 'js/platform/tizen/tizenCapabilities.js'
    replace(capabilities, '  canUsePlugins(runtime = globalThis) {',
            '''  canUsePlugins(runtime = globalThis) {
    if (runtime.__NUVIO_PS5__) return false;''')
    store = nuvio / 'js/data/local/playerSettingsStore.js'
    replace(store, '  return STREAM_AUTO_PLAY_SOURCES.includes(normalized) ? normalized : "ALL_SOURCES";',
            '''  if (globalThis.__NUVIO_PS5__ && normalized === "ENABLED_PLUGINS_ONLY") return "INSTALLED_ADDONS_ONLY";
  return STREAM_AUTO_PLAY_SOURCES.includes(normalized) ? normalized : "ALL_SOURCES";''')
    # Upstream getLatestForContent now provides series-wide binge reuse.
    # Keep PS5 source reuse based on fresh addon results, not cached signed URLs
    # or request headers, regardless of which frontend path attempts a save.
    cache = nuvio / 'js/data/local/streamLinkCacheStore.js'
    replace(cache, '  save(params, payload, profileId = activeStreamLinkProfile()) {',
            '''  save(params, payload, profileId = activeStreamLinkProfile()) {
    if (globalThis.__NUVIO_PS5__) return false;''')
    replace(cache, '  getValid(params, maxAgeMs, profileId = activeStreamLinkProfile()) {',
            '''  getValid(params, maxAgeMs, profileId = activeStreamLinkProfile()) {
    if (globalThis.__NUVIO_PS5__) return null;''')
    # prepare and the skip hook run concurrently. Share the movie lookup rather
    # than queueing duplicate requests on the console's metadata HTTP thread.
    repository = nuvio / 'js/data/repository/skipIntroRepository.js'
    replace(repository, '''    const data = await fetchJson(url.toString());
    const intervals = mapIntroDbSegmentsToSkipIntervals(data, { isMovie: true });
    writeCache(cacheKey, intervals);
    return intervals;''', '''    const pending = fetchJson(url.toString())
      .then(data => mapIntroDbSegmentsToSkipIntervals(data, { isMovie: true }));
    CACHE.set(cacheKey, { intervals: pending, expiresAt: Date.now() + CACHE_EMPTY_TTL_MS });
    const intervals = await pending;
    writeCache(cacheKey, intervals);
    return intervals;''')
