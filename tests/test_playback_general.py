"""Public presentation contracts, using no generated tree or external services."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import playback_general


HARNESS = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(process.argv[1], 'utf8');
const copy = value => JSON.parse(JSON.stringify(value));
function fixture() {
  const state = { profile: '1', live: true, calls: [], commits: [], posts: [], timers: [],
    settings: { parentalGuideEnabled: true, skipIntroEnabled: true, postPlayRecommendationsEnabled: true,
      loadingOverlayEnabled: true, showPlayerLoadingStatus: true, pauseOverlayEnabled: true, osdClockEnabled: true,
      postPlayMovieThresholdPercent: 85, nextEpisodeThresholdMode: 'PERCENTAGE', nextEpisodeThresholdPercent: 99 },
    meta: { description: 'Resolved synopsis', videos: [{ id: 'tt1:1:1', season: 1, episode: 1 }] },
    guide: { parentalGuide: { violence: 'mild' } },
    intervals: [ { type: 'movie-credits', startTime: 100, endTime: 120 },
      { type: 'movie-credits', startTime: 140, endTime: 160 },
      { type: 'post-credits', startTime: 125, endTime: 135 },
      { type: 'post-credits', startTime: -2, endTime: 900 },
      { type: 'post-credits', startTime: 10, endTime: 999999999 } ],
    seeds: Array.from({length: 4}, (_, i) => ({ id: `tt${i + 2}`, title: `Localized ${i + 2}`,
      description: 'Related synopsis', contentType: 'movie', sourceAddonBaseUrl: 'https://addon.invalid/private',
      poster: 'https://image.invalid/poster', imdbId: `tt${i + 2}` })) };
  const params = { itemId: 'tt1', videoId: 'tt1:1:1', itemType: 'movie', season: 1, episode: 1, returnToSearchOnBack: true };
  const candidate = { id: 'stream-1' };
  const screen = {
    params, episodes: [{ id: 'DO NOT MUTATE' }], activePlaybackUrl: 'https://stream.invalid/signed', pauseOverlayDelayMs: 4567,
    postPlayRecommendationController: { sentinel: true },
    getCurrentStreamCandidate: () => candidate,
    buildPlaybackIdentityContext() { return { itemType: this.params.itemType, imdbId: 'tt1', season: 1, episode: 1 }; },
    buildPostPlayRecommendationSnapshot() { return { contentType: this.params.itemType, contentId: this.params.itemId, videoId: this.params.videoId }; },
    buildPauseOverlayMeta(meta) { return { title: 'Title', episodeCode: 'S1E1', episodeTitle: 'Episode',
      description: meta?.description || 'Fallback synopsis', cast: [{ name: 'Actor' }] }; },
    resolveCurrentEpisodeEntry() { return this.episodes.find(ep => ep.id === this.params.videoId); },
    resolveNextEpisodeInfo() { return { hasAired: this.episodes.length > 1 }; }
  };
  const storage = new Map();
  class Controller {
    constructor() { this.pipelineToken = 0; state.controllers = (state.controllers || 0) + 1; }
    async loadCurrentMeta() { state.calls.push('meta'); return state.loadMeta ? state.loadMeta() : state.meta; }
    async loadCandidateSeeds(meta) { assert.equal(meta, state.meta); state.calls.push('policy'); return state.seeds; }
    async resolveCandidate(seed) { state.calls.push(seed.id); return state.resolve ? state.resolve(seed) : seed; }
    update() { throw Error('must not evaluate playback'); }
    loadRecommendation() { throw Error('must not start trailer pipeline'); }
  }
  const context = vm.createContext({
    __NUVIO_PS5__: true, console, URLSearchParams, AbortController,
    Date: class extends Date { getTimezoneOffset() { return -120; } },
    setTimeout(callback, ms) { const timer = { callback, ms }; state.timers.push(timer); return timer; },
    clearTimeout(timer) { if (timer) timer.cleared = true; },
    Router: { current: 'player', currentParams: params, getCurrentScreen: () => screen },
    ProfileManager: { getActiveProfileId: () => state.profile },
    PlayerSettingsStore: { get: () => state.settings },
    StreamPreferencesStore: { set(...args) { state.commits.push(copy(args)); } },
    PS5_PROGRESS_KEY: 'progress',
    LocalStore: { get: (key, fallback) => storage.has(key) ? storage.get(key) : fallback, set: (key, value) => storage.set(key, copy(value)) },
    canResumePs5Playback: () => state.live,
    PostPlayRecommendationController: Controller,
    parentalGuideRepository: {
      async getMovieGuide(...args) { state.calls.push(['movieGuide', ...args]); return state.loadGuide ? state.loadGuide() : state.guide; },
      async getTvGuide(...args) { state.calls.push(['tvGuide', ...args]); return state.loadGuide ? state.loadGuide() : state.guide; }
    },
    buildLocalizedParentalWarnings: guide => Object.keys(guide).map(key => ({ label: 'Localized violence', severity: 'Localized mild' })),
    normalizePlayerEpisodeMetadata: videos => videos || [],
    shouldUsePostPlayRecommendation: input => input.enabled && (input.contentType === 'movie' ||
      input.contentType === 'series' && input.nextEpisodeMetadataResolved && input.nextEpisodeHasAired !== true),
    normalizeNextEpisodeThresholdMode: value => value === 'MINUTES_BEFORE_END' ? value : 'PERCENTAGE',
    normalizeThresholdMinutesBeforeEnd: value => Number.isFinite(Number(value)) ? Math.max(0.5, Math.min(10, Number(value))) : 2,
    normalizeThresholdPercent: value => Number.isFinite(Number(value)) ? Math.max(80, Math.min(100, Number(value))) : 99,
    skipIntroRepository: { async getMovieSkipIntervals() { state.calls.push('skip'); return state.intervals; } },
    async fetch(url, options) { state.posts.push({ url, options, dto: JSON.parse(options.body) }); return { ok: true }; }
  });
  vm.runInContext(source, context);
  function save(session = 'session-1') {
    const saved = { session, profileId: state.profile, general: context.__nuvioCapturePresentation() };
    storage.set('progress', saved); return saved;
  }
  return { state, screen, params, candidate, context, save, storage };
}
const tick = async () => { for (let i = 0; i < 20; ++i) await Promise.resolve(); };
'''


class PresentationTests(unittest.TestCase):
    def run_js(self, body):
        result = subprocess.run(['node', '-e', HARNESS + '\n(async () => {\n' + body +
                                 '\n})().catch(error => { console.error(error); process.exitCode = 1; });',
                                 str(SCRIPTS / 'ps5-general.js')], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_snapshot_dto_and_browser_only_routes(self):
        self.run_js(r'''
const { state: s, context: c, screen, save } = fixture();
assert.equal(await c.__nuvioPreparePresentation(), true);
assert.deepEqual(screen.episodes, [{ id: 'DO NOT MUTATE' }]);
assert.deepEqual(screen.postPlayRecommendationController, { sentinel: true });
const saved = save();
assert.equal(saved.general.dto.recommendations.length, 3);
assert.equal(saved.general.routes.length, 3);
assert.equal(saved.general.routes[0].addonBaseUrl, 'https://addon.invalid/private');
saved.general.dto.secretAccount = 'never send';
assert.equal(await c.__nuvioSendPresentation('session-1'), true);
const { dto, options, url } = s.posts[0];
assert.equal(url, '/evo/presentation');
assert.equal(options.headers['Content-Type'], 'application/json');
assert.equal(dto.parental, 'Localized violence: Localized mild');
assert.equal(dto.description, 'Title\nS1E1 · Episode\nResolved synopsis\nActor');
assert.equal(dto.threshold, .85);
assert.equal(dto.thresholdMinutes, false);
assert.equal(dto.episodeThreshold, .99);
assert.equal(dto.creditsStart, 100);
assert.equal(dto.creditsEnd, 160);
assert.equal(dto.postCreditsEnd, 135);
assert.equal(dto.pauseDelayMs, 4567);
assert.equal(dto.utcOffsetMinutes, 120);
assert.equal(dto.loading && dto.loadingDetail && dto.pause && dto.clock && dto.movie && dto.recommendationEnabled, true);
assert(!/invalid|secretAccount|addonBaseUrl|profileId|itemId/.test(options.body));
assert(Buffer.byteLength(options.body) <= 8192);
saved.general.dto.description = 'altered';
assert.notEqual(c.__nuvioCapturePresentation().dto.description, 'altered');
assert.equal(await c.__nuvioSendPresentation('wrong-session'), false);
assert.equal(await c.__nuvioSendPresentation('bad/session'), false);
s.profile = '2';
assert.equal(await c.__nuvioSendPresentation('session-1'), false);
assert.equal(c.__nuvioCapturePresentation(), null);
''')

    def test_each_toggle_and_threshold_units(self):
        self.run_js(r'''
for (const [setting, wire] of Object.entries({ loadingOverlayEnabled: 'loading', showPlayerLoadingStatus: 'loadingDetail',
    pauseOverlayEnabled: 'pause', osdClockEnabled: 'clock', postPlayRecommendationsEnabled: 'recommendationEnabled' })) {
  const { state: s, context: c, save } = fixture();
  s.settings[setting] = false;
  await c.__nuvioPreparePresentation();
  const dto = save().general.dto;
  assert.equal(dto[wire], false, setting);
  for (const other of ['loading', 'loadingDetail', 'pause', 'clock', 'recommendationEnabled']) {
    if (other !== wire) assert.equal(dto[other], true, `${setting} must not disable ${other}`);
  }
  if (setting === 'postPlayRecommendationsEnabled') assert.equal(dto.recommendations.length, 0);
}
const { state: s, context: c, save } = fixture();
s.settings.parentalGuideEnabled = false;
s.settings.skipIntroEnabled = false;
s.settings.nextEpisodeThresholdMode = 'MINUTES_BEFORE_END';
s.settings.nextEpisodeThresholdMinutesBeforeEnd = 1.5;
await c.__nuvioPreparePresentation();
let dto = save().general.dto;
assert.equal(dto.parental, '');
assert.equal(dto.postCreditsEnd, 0);
assert.equal(dto.creditsStart, 0);
assert.equal(dto.episodeThresholdMinutes, true);
assert.equal(dto.episodeThreshold, 90);
assert.equal(dto.threshold, .85); // movie policy is still the movie percentage
assert(!s.calls.some(call => Array.isArray(call) && call[0].endsWith('Guide')));
assert(!s.calls.includes('skip'));
''')

    def test_series_requires_canonical_metadata_and_no_aired_next(self):
        self.run_js(r'''
for (const [videos, expected] of [[undefined, 0], [[], 0],
  [[{ id: 'different' }], 0], [[{ id: 'tt1:1:1' }], 3],
  [[{ id: 'tt1:1:1' }, { id: 'tt1:1:2' }], 0]]) {
  const { state: s, context: c, params, save, screen } = fixture();
  params.itemType = 'series'; s.meta.videos = videos;
  s.settings.nextEpisodeThresholdMode = 'MINUTES_BEFORE_END'; s.settings.nextEpisodeThresholdMinutesBeforeEnd = 2.5;
  await c.__nuvioPreparePresentation();
  const dto = save().general.dto;
  assert.equal(dto.movie, false);
  assert.equal(dto.thresholdMinutes, true);
  assert.equal(dto.threshold, 150);
  assert.equal(dto.recommendations.length, expected);
  assert.deepEqual(screen.episodes, [{ id: 'DO NOT MUTATE' }]);
  assert(s.calls.some(call => Array.isArray(call) && call.join(',') === 'tvGuide,tt1,1,1'));
}
''')

    def test_stale_route_profile_screen_and_selection_cancel(self):
        self.run_js(r'''
for (const change of [f => f.context.Router.current = 'detail', f => f.context.Router.currentParams = {...f.params},
    f => f.params.videoId = 'different', f => f.state.profile = '2',
    f => f.candidate.id = 'different', f => f.screen.activePlaybackUrl = 'different']) {
  const f = fixture(); const { state: s, context: c } = f;
  await c.__nuvioPreparePresentation(); assert(c.__nuvioCapturePresentation());
  let resolve; s.loadMeta = () => new Promise(r => resolve = r);
  const pending = c.__nuvioPreparePresentation();
  assert.equal(c.__nuvioCapturePresentation(), null); // entry clears prior title
  change(f); resolve(s.meta);
  assert.equal(await pending, null);
  assert.equal(c.__nuvioCapturePresentation(), null);
}
''')

    def test_timeout_partial_results_late_completion_and_missing_metadata(self):
        self.run_js(r'''
const { state: s, context: c, save } = fixture();
let finish; s.resolve = seed => seed.id === 'tt2' ? seed : new Promise(resolve => finish = resolve);
const pending = c.__nuvioPreparePresentation();
await tick();
assert.equal(s.timers.length, 1);
assert.equal(s.timers[0].ms, 4000);
s.timers[0].callback();
assert.equal(await pending, true);
const dto = save().general.dto;
assert.equal(dto.recommendations.length, 1);
finish(s.seeds[2]); await tick();
assert.equal(c.__nuvioCapturePresentation().dto.recommendations.length, 1);
s.loadMeta = async () => { throw Error('metadata unavailable'); };
s.loadGuide = async () => { throw Error('guide unavailable'); };
assert.equal(await c.__nuvioPreparePresentation(), true);
assert.equal(save().general.dto.recommendations.length, 0);
assert.equal(save().general.dto.parental, '');
assert(save().general.dto.description.includes('Fallback synopsis'));
''')

    def test_late_toggle_changes_and_utf8_wire_bound(self):
        self.run_js(r'''
const { state: s, context: c, screen, save } = fixture();
let resolve; s.loadMeta = () => new Promise(r => resolve = r);
const pending = c.__nuvioPreparePresentation();
s.settings.parentalGuideEnabled = false;
s.settings.postPlayRecommendationsEnabled = false;
s.settings.skipIntroEnabled = false;
resolve(s.meta); await pending;
let dto = save().general.dto;
assert.equal(dto.parental, ''); assert.equal(dto.recommendations.length, 0); assert.equal(dto.postCreditsEnd, 0);
s.settings.parentalGuideEnabled = true; s.settings.postPlayRecommendationsEnabled = true;
s.loadMeta = null;
screen.buildPauseOverlayMeta = () => ({ description: '界😀'.repeat(1000) + '\ud800' });
s.seeds.forEach(seed => { seed.title = '😀'.repeat(100); seed.description = '界'.repeat(400); });
await c.__nuvioPreparePresentation(); save();
assert.equal(await c.__nuvioSendPresentation('session-1'), true);
dto = s.posts[0].dto;
assert(Buffer.byteLength(dto.description) <= 800);
for (const item of dto.recommendations) { assert(Buffer.byteLength(item.title) <= 160); assert(Buffer.byteLength(item.description) <= 400); }
assert(Buffer.byteLength(s.posts[0].options.body) <= 8192);
''')

    def test_remember_requires_played_and_is_profile_session_gated(self):
        self.run_js(r'''
const { state: s, context: c, screen, save } = fixture();
c.__nuvioDeferStreamPreference(screen, 'tt1', 'tt1:1:1', 'stream-1', {
  bingeGroup: 'release-group', resumeIdentity: 'url:["https://signed.invalid/?token=secret"]' });
await c.__nuvioPreparePresentation();
const saved = save();
assert.equal(saved.general.pending.metadata.resumeIdentity, '');
assert.equal(s.commits.length, 0);
c.__nuvioAcceptPresentation(saved, { session: 'session-1', positionMs: 900000, played: false });
c.__nuvioAcceptPresentation(saved, { session: 'other', played: true });
s.profile = '2'; c.__nuvioAcceptPresentation(saved, { session: 'session-1', played: true });
assert.equal(s.commits.length, 0);
s.profile = '1'; c.__nuvioAcceptPresentation(saved, { played: true }); // verified endpoint need not echo session
assert.equal(s.commits.length, 1);
assert.deepEqual(s.commits[0], ['tt1', 'tt1:1:1', 'stream-1', { bingeGroup: 'release-group', resumeIdentity: '' }, '1']);
c.__nuvioAcceptPresentation(saved, { session: 'session-1', played: true });
assert.equal(s.commits.length, 1);
assert.equal(saved.general.pending, null);
''')

    def test_one_use_details_route_live_return_only_no_autoplay(self):
        self.run_js(r'''
const { state: s, context: c, save } = fixture();
await c.__nuvioPreparePresentation(); const saved = save();
for (const recommendation of [0, 4, 1.5, '1', null]) {
  c.__nuvioAcceptPresentation(saved, { session: saved.session, recommendation });
  assert.equal(c.__nuvioTakePresentationRoute(), null);
}
s.live = false;
c.__nuvioAcceptPresentation(saved, { session: saved.session, recommendation: 1 });
assert.equal(c.__nuvioTakePresentationRoute(), null);
s.live = true;
c.__nuvioAcceptPresentation(saved, { session: saved.session, recommendation: 2 });
let params = c.__nuvioTakePresentationRoute();
assert.equal(params.itemId, 'tt3'); assert.equal(params.addonBaseUrl, 'https://addon.invalid/private');
assert.equal(params.returnToSearchOnBack, true); assert.equal(params.playOnLoad, false); assert.equal(params.manualSelection, true);
assert.equal(c.__nuvioTakePresentationRoute(), null);
c.__nuvioAcceptPresentation(saved, { session: saved.session, recommendation: 1 }); s.profile = '2';
assert.equal(c.__nuvioTakePresentationRoute(), null);
s.profile = '1'; s.settings.postPlayRecommendationsEnabled = false;
c.__nuvioAcceptPresentation(saved, { session: saved.session, recommendation: 1 });
assert.equal(c.__nuvioTakePresentationRoute(), null);
''')


# Minimal pinned public anchors, not a dependency on an ignored generated tree.
FRONTEND = {
    'js/app.js': 'import { PlayerController } from "./core/player/playerController.js";\nlet hasSelectedProfileThisSession = false;\n',
    'js/ui/screens/player/playerScreenMethods-06-handle-post-play-key.js': '''function remember(streamCandidate) {
      const prefContentId = this.params.itemId;
      const prefVideoId = this.params.videoId;
      StreamPreferencesStore.set(prefContentId, prefVideoId, streamCandidate.id, {
        bingeGroup: streamCandidate?.behaviorHints?.bingeGroup || streamCandidate?.raw?.behaviorHints?.bingeGroup || "",
        resumeIdentity: buildStreamResumeIdentity(streamCandidate)
      });
}''',
    'js/ui/screens/settings/settingsScreenHelpers-04-row-icons.js': '''export function arePluginsSupported() {
  return TizenCapabilities.canUsePlugins();
}''',
    'js/ui/screens/settings/settingsScreenPlaybackActions-01.js': '''function options() { return {
      options: STREAM_AUTOPLAY_SOURCE_OPTIONS,
}; }''',
    'js/platform/tizen/tizenCapabilities.js': '''const TizenCapabilities = {
  canUsePlugins(runtime = globalThis) {
    return runtime.tvSupported !== false;
  }
};''',
    'js/data/local/playerSettingsStore.js': '''const STREAM_AUTO_PLAY_SOURCES = ["ALL_SOURCES", "INSTALLED_ADDONS_ONLY", "ENABLED_PLUGINS_ONLY"];
function normalizeStreamAutoPlaySource(value) {
  const normalized = String(value || "").trim().toUpperCase();
  return STREAM_AUTO_PLAY_SOURCES.includes(normalized) ? normalized : "ALL_SOURCES";
}''',
    'js/data/local/streamPreferencesStore.js': '''export const StreamPreferencesStore = {
  getEntry() { return { bingeGroup: 'exact-video' }; }
};''',
    'js/data/repository/skipIntroRepository.js': '''const CACHE = new Map();
async function lookup(cacheKey) {
    if (CACHE.has(cacheKey)) return CACHE.get(cacheKey);
    const url = new URL('https://metadata.invalid');
    const data = await fetchJson(url.toString());
    const intervals = mapIntroDbSegmentsToSkipIntervals(data, { isMovie: true });
    CACHE.set(cacheKey, intervals);
    return intervals;
}''',
    'js/ui/screens/stream/streamScreenMethods-05-maybe-auto-resume-stream.js': '''function select(settings) {
      const savedPreference =
        settings.streamAutoPlayPreferBingeGroupForNextEpisode && settings.streamAutoPlayReuseBingeGroup
          ? StreamPreferencesStore.getEntry(this.params?.itemId, this.params?.videoId || this.params?.itemId)
          : null;
      return savedPreference;
}'''
}


class FrontendPatchTests(unittest.TestCase):
    def test_emitted_capability_scope_remember_and_group_contracts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, text in FRONTEND.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            playback_general.patch_frontend(root)
            emitted = {key: (root / key).read_text() for key in FRONTEND}
            self.assertIn('__nuvioPreparePresentation', emitted['js/app.js'])
            self.assertIn('import { parentalGuideRepository }', emitted['js/app.js'])
            code = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const files = JSON.parse(process.argv[1]);
const load = (suffix, context) => vm.runInContext(Object.entries(files).find(([key]) => key.endsWith(suffix))[1].replace(/export /g, ''), context);
let deferred = 0; let committed = 0;
const context = vm.createContext({ __NUVIO_PS5__: true, __NUVIO_ALLOW_BROWSER_PLUGIN_RUNTIME__: true,
  Platform: { isBrowser: () => true }, buildStreamResumeIdentity: () => 'file:identity',
  __nuvioDeferStreamPreference: () => ++deferred,
  StreamPreferencesStore: { set: () => ++committed },
  STREAM_AUTOPLAY_SOURCE_OPTIONS: [{id:'ALL_SOURCES'}, {id:'INSTALLED_ADDONS_ONLY'}, {id:'ENABLED_PLUGINS_ONLY'}] });
load('tizenCapabilities.js', context);
load('settingsScreenHelpers-04-row-icons.js', context);
load('settingsScreenPlaybackActions-01.js', context);
load('playerSettingsStore.js', context);
load('playerScreenMethods-06-handle-post-play-key.js', context);
assert.equal(vm.runInContext('TizenCapabilities.canUsePlugins()', context), false);
assert.equal(context.arePluginsSupported(), false);
assert.equal(context.options().options.length, 2);
assert.equal(context.normalizeStreamAutoPlaySource('ENABLED_PLUGINS_ONLY'), 'INSTALLED_ADDONS_ONLY');
context.remember.call({ params: { itemId: 'tt1', videoId: 'tt1:1:1' } }, { id: 'stream' });
assert.equal(deferred, 1); assert.equal(committed, 0);
context.__NUVIO_PS5__ = false; context.__NUVIO_ALLOW_BROWSER_PLUGIN_RUNTIME__ = false;
assert.equal(context.arePluginsSupported(), false); // ordinary browser has no execution capability
context.__NUVIO_ALLOW_BROWSER_PLUGIN_RUNTIME__ = true;
assert.equal(context.arePluginsSupported(), true);
assert.equal(context.options().options.length, 3);
assert.equal(context.normalizeStreamAutoPlaySource('ENABLED_PLUGINS_ONLY'), 'ENABLED_PLUGINS_ONLY');
context.remember.call({ params: { itemId: 'tt1', videoId: 'tt1:1:1' } }, { id: 'stream' });
assert.equal(committed, 1); assert.equal(deferred, 1);
const groupContext = vm.createContext({ __NUVIO_PS5__: true,
  activeProfileId: () => '1', buildContentKey: id => id,
  readEntries: profile => profile === '1' ? [{ key: 'tt10::ep1', bingeGroup: 'wrong' },
    { key: 'tt1::ep1', bingeGroup: 'series-group', cachedAtMs: 10 }] : [] });
load('streamPreferencesStore.js', groupContext);
load('streamScreenMethods-05-maybe-auto-resume-stream.js', groupContext);
const result = groupContext.select.call({ params: { itemId: 'tt1', videoId: 'ep2' } },
  { streamAutoPlayPreferBingeGroupForNextEpisode: true, streamAutoPlayReuseBingeGroup: true });
assert.equal(result.bingeGroup, 'series-group'); assert.equal(result.cachedAtMs, 10);
assert.equal(groupContext.select.call({params:{}}, {streamAutoPlayPreferBingeGroupForNextEpisode:false, streamAutoPlayReuseBingeGroup:true}), null);
assert.equal(vm.runInContext('StreamPreferencesStore.getBingeGroupEntry("tt1", "2")', groupContext), null);
let requests = 0; let complete;
const cacheContext = vm.createContext({ URL,
  fetchJson: () => { ++requests; return new Promise(resolve => complete = resolve); },
  mapIntroDbSegmentsToSkipIntervals: value => value });
load('skipIntroRepository.js', cacheContext);
const first = cacheContext.lookup('movie:tt1'); const second = cacheContext.lookup('movie:tt1');
assert.equal(requests, 1);
complete([{startTime: 10, endTime: 20}]);
Promise.all([first, second]).then(async ([a, b]) => {
  assert.equal(a, b); assert.equal(await cacheContext.lookup('movie:tt1'), a); assert.equal(requests, 1);
}).catch(error => { console.error(error); process.exitCode = 1; });
'''
            result = subprocess.run(['node', '-e', code, json.dumps(emitted)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class NativePresentationTests(unittest.TestCase):
    def test_native_clock_has_one_end_time_and_preserves_remaining_duration(self):
        from tests.test_native_subtitles import compile_run
        fill = 'void PlayerScreen::fillNuvioPresentation' + (
            SCRIPTS / 'ps5-general-player.cpp').read_text().split(
                'void PlayerScreen::fillNuvioPresentation', 1)[1]
        source = r'''
#include <cassert>
#include <cstring>
#include <string>
#include "ps5-general.h"
static nuvio_presentation_t policy;
const nuvio_presentation_t *evo_webui_presentation(){return &policy;}
static bool video_frame_loaded=true,pb_prebuffer_hold;
static struct {bool seek_discarding;} g_pp_pb;
static bool evo_pb_is_finished(){return false;}
static bool readerStalled(){return false;}
static uint64_t now;
uint64_t NowMs(){return now;}
struct evo_playback_osd_params_t {
 const char *ends_at="21:30",*remaining="-45:00",*nuvio_pause_text,*nuvio_parental;
 const char *nuvio_recommendation,*nuvio_clock,*nuvio_loading_status,*skip_label;
 int nuvio_active,nuvio_still_countdown,next_episode=3,playback_ended=1,chrome_hidden=0;
 bool loading;
};
struct PlayerScreen {
 nuvio_presentation_view_t m_nuvioView{};
 std::string m_nuvioRecommendation;
 char m_nuvioClock[64]{};
 int m_nextEpisodeState=0;
 uint64_t m_nuvioEndSuggestionSince=0;
 void fillNuvioPresentation(evo_playback_osd_params_t&);
};
''' + fill + r'''
int main(){
 PlayerScreen screen;
 for(int active=0;active<=1;++active)for(int clock=0;clock<=1;++clock){
  policy.active=active;policy.clock=clock;
  strcpy(screen.m_nuvioClock,clock?"20:45   Ends 21:30":"");
  evo_playback_osd_params_t p;
  screen.fillNuvioPresentation(p);
  assert(!strcmp(p.remaining,"-45:00"));
  assert(!strcmp(p.ends_at,active?"":"21:30"));
  assert(!strcmp(p.nuvio_clock,clock?"20:45   Ends 21:30":""));
 }
 policy.active=1;
 for(int kind=0;kind<3;++kind){
  screen.m_nuvioEndSuggestionSince=0;
  screen.m_nuvioRecommendation=kind==2?"Next movie":"";
  for(uint64_t elapsed : {0,9999,10000,10001,20000}){
   now=500000+elapsed; // A late end card must still receive ten seconds.
   evo_playback_osd_params_t p;p.next_episode=kind==0?3:0;p.playback_ended=kind==1;
   screen.fillNuvioPresentation(p);
   bool visible=elapsed<10000;
   assert(p.next_episode==(visible && kind==0?3:0));
   assert(p.playback_ended==(visible && kind==1?1:0));
   assert(!strcmp(p.nuvio_recommendation,visible && kind==2?"Next movie":""));
  }
  evo_playback_osd_params_t hidden;hidden.chrome_hidden=1;
  screen.fillNuvioPresentation(hidden);
  assert(!hidden.next_episode && !hidden.playback_ended && !*hidden.nuvio_recommendation);
  ++now;
  evo_playback_osd_params_t revealed;screen.fillNuvioPresentation(revealed);
  assert(revealed.next_episode==3 && revealed.playback_ended==1);
 }
 // Native-library prompts are not governed by Nuvio's policy.
 policy.active=0;
 evo_playback_osd_params_t native;native.chrome_hidden=1;
 screen.fillNuvioPresentation(native);assert(native.next_episode==3 && native.playback_ended==1);
 // Still Watching is a separate confirmation, not an expiring end suggestion.
 policy.active=1;screen.m_nextEpisodeState=1042;
 evo_playback_osd_params_t p;p.chrome_hidden=1;
 screen.fillNuvioPresentation(p);assert(p.nuvio_still_countdown==42);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            compile_run(source, tmp, cpp=True, extra_flags=['-I', str(SCRIPTS)])

    def test_native_timers_recommendation_thresholds_actions_and_session_reset(self):
        # Transport parsing is covered by the real-stack validation. This host
        # probe exercises the playback-facing policy interface without an SDK.
        source = r'''
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <math.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "ps5-general.h"
static time_t fixed_time(time_t *out) { if(out) *out=0; return 0; }
#define time fixed_time
static pthread_mutex_t s_mx = PTHREAD_MUTEX_INITIALIZER;
static int s_progress_finished, s_progress_played, s_progress_recommendation;
static int s_progress_next_episode, s_progress_return_detail;
static char s_progress_session[64]="test-session", s_presentation_session[64];
static nuvio_presentation_t s_pending_presentation, s_h_presentation, s_play_presentation, s_presentation;
static uint64_t s_presentation_last, s_presentation_running_ms, s_presentation_paused_ms;
static int s_presentation_running, s_presentation_paused, s_recommendation_index, s_recommendation_dismissed;
static struct { int type; double start, end; } s_skip[4];
''' + 'static void presentation_handoff' + (SCRIPTS/'ps5-general.c').read_text().split('static void presentation_handoff', 1)[1] + r'''
static void begin(nuvio_presentation_t policy) {
 s_pending_presentation=policy;strcpy(s_presentation_session,"test-session");
 presentation_handoff("test-session");s_play_presentation=s_h_presentation;presentation_begin();
 s_progress_played=s_progress_recommendation=s_progress_next_episode=s_progress_return_detail=0;
}
static nuvio_presentation_view_t tick(double pos,uint64_t ms,int ready,int paused,int blocked) {
 return evo_webui_presentation_update(pos,1000,ms,ready,paused,blocked,0);
}
int main(void) {
 nuvio_presentation_t p={0};
 p.active=p.pause=p.clock=p.recommendation_enabled=p.movie=1;
 p.pause_delay_ms=3000;p.threshold=.85;p.episode_threshold=.99;
 p.recommendation_count=2;strcpy(p.parental,"Violence: mild");begin(p);
 assert(!tick(0,0,0,0,0).parental && !s_progress_played);
 assert(tick(1,1000,1,0,0).parental && s_progress_played);
 assert(tick(2,7999,1,0,0).parental);
 assert(!tick(2,8000,1,1,0).pause);
 assert(!tick(2,10999,1,1,0).pause);
 assert(tick(2,11000,1,1,0).pause);
 assert(!tick(2,12000,0,1,0).pause); /* Buffering isn't a paused synopsis. */
 assert(!tick(2,13000,1,1,0).pause); /* Readiness restarts delay. */
 assert(!tick(3,14000,1,0,0).pause);
 assert(tick(3,14001,1,0,0).parental); /* Pause doesn't consume warning time. */
 assert(!tick(4,15001,1,0,0).parental);
 assert(!tick(849.99,16000,1,0,0).recommendation);
 assert(tick(850,17000,1,0,0).recommendation==1);
 assert(!tick(900,18000,1,0,1).recommendation);
 evo_webui_presentation_action(1);assert(tick(900,19000,1,0,0).recommendation==2);
 evo_webui_recommendation_selected(2);assert(s_progress_recommendation==2);
 evo_webui_recommendation_selected(3);assert(s_progress_recommendation==2);
 evo_webui_presentation_action(1);assert(tick(900,20000,1,0,0).recommendation==1);
 evo_webui_presentation_action(2);assert(!tick(1000,21000,1,0,0).recommendation);
 p.parental[0]=0;p.credits_start=880;p.credits_end=940;begin(p);
 assert(!tick(989.99,0,1,0,0).recommendation); /* Preserve 60s post-credit gap. */
 assert(tick(990,1,1,0,0).recommendation==1);
 p.post_credits_end=997;begin(p);
 assert(!tick(996.99,0,1,0,0).recommendation);
 assert(tick(997,1,1,0,0).recommendation==1);
 p.post_credits_end=0;p.credits_end=995;begin(p);
 assert(!tick(879.99,0,1,0,0).recommendation);
 assert(tick(880,1,1,0,0).recommendation==1);
 p.movie=0;p.threshold_minutes=1;p.threshold=90;begin(p);
 assert(!tick(909.99,0,1,0,0).recommendation);
 assert(tick(910,1,1,0,0).recommendation==1);
 p.pause=p.recommendation_enabled=p.clock=0;begin(p);
 assert(!tick(999,0,1,0,0).recommendation && !tick(999,10000,1,1,0).pause);
 char clock[64];evo_webui_presentation_clock(10,1000,clock,sizeof clock);assert(!clock[0]);
 p.clock=1;p.utc_offset_minutes=120;begin(p);evo_webui_presentation_clock(10,1000,clock,sizeof clock);
 assert(!strcmp(clock,"02:00   Ends 02:16"));
 evo_webui_presentation_clock(1000,1000,clock,sizeof clock);assert(!strcmp(clock,"02:00"));
 strcpy(s_presentation_session,"other");s_pending_presentation=p;
 presentation_handoff("test-session");s_play_presentation=s_h_presentation;presentation_begin();
 assert(!evo_webui_presentation()->active && !tick(999,20000,1,0,0).recommendation);
 puts("Native General timers, boundaries, actions and session reset: PASS");
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp)/'general.c'
            probe.write_text(source)
            binary = Path(tmp)/'general'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(SCRIPTS),
                            '-x', 'c', str(probe), '-lm', '-pthread', '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
