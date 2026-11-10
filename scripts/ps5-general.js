// Browser-owned General settings and metadata. Only the explicit DTO below
// crosses the native boundary; routes and source preferences stay in Nuvio.
let ps5Presentation = null;
let ps5PresentationGeneration = 0;
let ps5PresentationRoute = null;

function ps5GeneralBytes(value) {
  return unescape(encodeURIComponent(value)).length;
}

function ps5GeneralText(value, limit) {
  const text = String(value ?? "").replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, "")
    .replace(/(?:https?:\/\/|magnet:|www\.)\S+/gi, "").trim();
  let result = "";
  let bytes = 0;
  for (const character of text) {
    // Ignore unpaired surrogates rather than throwing during UTF-8 encoding.
    if (character.length === 1 && /[\ud800-\udfff]/.test(character)) continue;
    const size = ps5GeneralBytes(character);
    if (bytes + size > limit) break;
    result += character;
    bytes += size;
  }
  return result;
}

// Preference identities may otherwise embed a signed URL (the upstream url:
// fallback). Keep only bounded non-URL identities; never cache the stream URL.
function ps5GeneralPreferenceText(value, limit) {
  const text = String(value ?? "").trim();
  if (/(?:[a-z][a-z0-9+.-]*:\/\/|magnet:|[?&](?:token|key|signature)=)/i.test(text) ||
      /^(?:url|magnet):/i.test(text) || ps5GeneralText(text, limit) !== text) return "";
  return text;
}

globalThis.__nuvioDeferStreamPreference = function (screen, contentId, videoId, streamId, metadata) {
  if (!globalThis.__NUVIO_PS5__) return;
  screen.ps5PendingStreamParams = screen.params;
  screen.ps5PendingStreamPreference = {
    profileId: String(ProfileManager.getActiveProfileId()),
    contentId: ps5GeneralPreferenceText(contentId, 256),
    videoId: ps5GeneralPreferenceText(videoId, 256),
    streamId: ps5GeneralPreferenceText(streamId, 512),
    metadata: {
      bingeGroup: ps5GeneralPreferenceText(metadata?.bingeGroup, 512),
      resumeIdentity: ps5GeneralPreferenceText(metadata?.resumeIdentity, 2048)
    }
  };
};

function ps5GeneralSynopsis(screen, meta) {
  const info = screen.buildPauseOverlayMeta?.(meta) || screen.pauseOverlayMeta || {};
  const cast = (Array.isArray(info.cast) ? info.cast : []).slice(0, 6)
    .map(person => typeof person === "string" ? person : person?.name).filter(Boolean).join(", ");
  return ps5GeneralText([
    info.title, [info.episodeCode, info.episodeTitle].filter(Boolean).join(" · "),
    info.description, cast
  ].filter(Boolean).join("\n"), 800);
}

function ps5GeneralDetailParams(recommendation, screen) {
  // Same details navigation shape as navigateToPostPlayRecommendation, but
  // deliberately no play-on-load or automatic recommendation playback.
  return {
    itemId: recommendation.id,
    itemType: recommendation.contentType === "series" ? "series" : "movie",
    fallbackTitle: recommendation.title || recommendation.name || recommendation.id,
    fallbackPoster: recommendation.poster || "",
    fallbackBackground: recommendation.backdrop || recommendation.background || recommendation.poster || "",
    addonBaseUrl: recommendation.sourceAddonBaseUrl || "",
    imdbId: recommendation.imdbId || null,
    tmdbId: recommendation.tmdbId || null,
    traktId: recommendation.traktId || null,
    contentLanguage: recommendation.contentLanguage || screen.contentLanguage || "",
    returnHomeOnBack: Boolean(screen.params?.returnHomeOnBack || screen.params?.returnToHomeOnBack),
    returnToHomeOnBack: Boolean(screen.params?.returnHomeOnBack || screen.params?.returnToHomeOnBack),
    returnToSearchOnBack: Boolean(screen.params?.returnToSearchOnBack),
    playOnLoad: false,
    manualSelection: true,
    heroBackdropUrl: recommendation.backdrop || recommendation.background || ""
  };
}

function ps5GeneralThresholds(settings, movie) {
  const episodeThresholdMinutes = normalizeNextEpisodeThresholdMode(settings.nextEpisodeThresholdMode) === "MINUTES_BEFORE_END";
  const episodeThreshold = episodeThresholdMinutes
    ? normalizeThresholdMinutesBeforeEnd(settings.nextEpisodeThresholdMinutesBeforeEnd) * 60
    : normalizeThresholdPercent(settings.nextEpisodeThresholdPercent) / 100;
  const selected = Number(settings.postPlayMovieThresholdPercent);
  const movieThreshold = Number.isFinite(selected) ? Math.max(80, Math.min(100, selected)) / 100 : 0.9;
  return {
    movie, thresholdMinutes: !movie && episodeThresholdMinutes,
    threshold: movie ? movieThreshold : episodeThreshold,
    episodeThresholdMinutes, episodeThreshold
  };
}

globalThis.__nuvioPreparePresentation = async function () {
  ps5Presentation = null;
  ps5PresentationRoute = null;
  const generation = ++ps5PresentationGeneration;
  if (!globalThis.__NUVIO_PS5__ || Router.current !== "player") return null;
  const params = Router.currentParams;
  const screen = Router.getCurrentScreen();
  const profileId = String(ProfileManager.getActiveProfileId());
  const routeIdentity = () => JSON.stringify([params?.itemId, params?.contentId, params?.videoId,
    params?.itemType, params?.season, params?.episode]);
  const originalIdentity = routeIdentity();
  const selection = () => String(screen?.getCurrentStreamCandidate?.()?.id || "") + "|" + String(screen?.activePlaybackUrl || "");
  const selected = selection();
  const current = () => generation === ps5PresentationGeneration && Router.current === "player" &&
    Router.currentParams === params && Router.getCurrentScreen() === screen &&
    String(ProfileManager.getActiveProfileId()) === profileId && routeIdentity() === originalIdentity && selection() === selected;
  if (!screen) return null;
  let open = true;
  const active = () => open && current();
  const settings = PlayerSettingsStore.get();
  const identity = screen.buildPlaybackIdentityContext?.() || {};
  const snapshot = screen.buildPostPlayRecommendationSnapshot?.() || {};
  const movie = snapshot.contentType === "movie" || (!snapshot.contentType && identity.itemType === "movie");
  const prepared = {
    profileId,
    identity: { itemId: params?.itemId || params?.contentId || "", videoId: params?.videoId || "", itemType: params?.itemType || "" },
    pending: null,
    routes: [],
    dto: { description: ps5GeneralSynopsis(screen), parental: "", recommendations: [],
      ...ps5GeneralThresholds(settings, movie), creditsStart: 0, creditsEnd: 0, postCreditsEnd: 0 }
  };
  // A separate controller reuses the actual addon/TMDB/Trakt and watched/filter
  // policy. Do NOT call update/loadRecommendation: those evaluate playback and
  // can schedule trailers. The live screen/controller remains untouched.
  const controller = new PostPlayRecommendationController();
  controller.snapshot = { ...snapshot };
  const tasks = [];
  if (settings.parentalGuideEnabled !== false && identity.imdbId) {
    tasks.push((async () => {
      const series = ["series", "tv", "show", "tvshow"].includes(identity.itemType);
      const response = series && identity.season && identity.episode
        ? await parentalGuideRepository.getTvGuide(identity.imdbId, identity.season, identity.episode)
        : await parentalGuideRepository.getMovieGuide(identity.imdbId);
      if (active()) prepared.dto.parental = ps5GeneralText(buildLocalizedParentalWarnings(response?.parentalGuide || {})
        .map(warning => `${warning.label}: ${warning.severity}`).join("\n"), 800);
    })());
  }
  tasks.push((async () => {
    const meta = await controller.loadCurrentMeta();
    if (!active() || !meta) return;
    prepared.dto.description = ps5GeneralSynopsis(screen, meta);
    let resolved = movie;
    let next = null;
    if (!movie && ["series", "tv", "show", "tvshow"].includes(snapshot.contentType)) {
      const episodes = normalizePlayerEpisodeMetadata(meta.videos, { fallbackSeason: params?.season });
      // Resolve the canonical sequence using the screen's pure existing rules,
      // against a detached view, without updating its episodes or trailer state.
      const view = Object.assign(Object.create(screen), { episodes, params: { ...screen.params } });
      resolved = episodes.length > 0 && Boolean(view.resolveCurrentEpisodeEntry?.());
      next = resolved ? view.resolveNextEpisodeInfo?.() : null;
    }
    if (!shouldUsePostPlayRecommendation({ enabled: settings.postPlayRecommendationsEnabled !== false,
      contentType: snapshot.contentType, nextEpisodeMetadataResolved: resolved, nextEpisodeHasAired: next?.hasAired ?? null })) return;
    const seeds = await controller.loadCandidateSeeds(meta);
    if (!active()) return;
    const results = [];
    await Promise.all((Array.isArray(seeds) ? seeds : []).slice(0, 3).map(async (seed, index) => {
      const item = await controller.resolveCandidate(seed, meta);
      if (!active() || !item?.id) return;
      const title = ps5GeneralText(item.title || item.name, 160);
      if (!title) return;
      results[index] = { title, description: ps5GeneralText(item.description, 400), route: ps5GeneralDetailParams(item, screen) };
      const available = results.filter(Boolean);
      prepared.dto.recommendations = available.map(({ title, description }) => ({ title, description }));
      prepared.routes = available.map(item => item.route);
    }));
  })());
  if (movie && settings.skipIntroEnabled) {
    tasks.push((async () => {
      const intervals = await skipIntroRepository.getMovieSkipIntervals({ imdbId: identity.imdbId,
        tmdbId: identity.tmdbId, contentId: params?.itemId || params?.contentId, videoId: params?.videoId });
      if (!active() || !Array.isArray(intervals)) return;
      const valid = intervals.filter(item => Number.isFinite(Number(item?.startTime)) && Number.isFinite(Number(item?.endTime)) &&
        Number(item.startTime) >= 0 && Number(item.endTime) > Number(item.startTime) && Number(item.endTime) <= 604800);
      const credits = valid.filter(item => item.type === "movie-credits");
      prepared.dto.creditsStart = credits.length ? Math.min(...credits.map(item => Number(item.startTime))) : 0;
      prepared.dto.creditsEnd = credits.length ? Math.max(...credits.map(item => Number(item.endTime))) : 0;
      const scenes = valid.filter(item => item.type === "post-credits" && Number(item.startTime) >= prepared.dto.creditsStart);
      prepared.dto.postCreditsEnd = scenes.length ? Math.max(...scenes.map(item => Number(item.endTime))) : 0;
    })());
  }
  let timer;
  try {
    await Promise.race([Promise.all(tasks.map(task => task.catch(() => {}))),
      new Promise(resolve => { timer = setTimeout(resolve, 4000); })]);
  } finally {
    clearTimeout(timer);
    open = false;
    controller.pipelineToken += 1; // invalidate any late candidate resolution
  }
  if (!current()) return null;
  const latest = PlayerSettingsStore.get();
  Object.assign(prepared.dto, ps5GeneralThresholds(latest, movie), {
    loading: latest.loadingOverlayEnabled !== false,
    loadingDetail: latest.showPlayerLoadingStatus !== false,
    pause: latest.pauseOverlayEnabled !== false,
    clock: Boolean(latest.osdClockEnabled),
    pauseDelayMs: Number.isFinite(Number(screen.pauseOverlayDelayMs))
      ? Math.max(0, Math.min(60000, Number(screen.pauseOverlayDelayMs))) : 3000,
    utcOffsetMinutes: Math.max(-840, Math.min(840, -new Date().getTimezoneOffset())),
    recommendationEnabled: latest.postPlayRecommendationsEnabled !== false
  });
  if (latest.parentalGuideEnabled === false) prepared.dto.parental = "";
  if (!latest.skipIntroEnabled) Object.assign(prepared.dto, { creditsStart: 0, creditsEnd: 0, postCreditsEnd: 0 });
  if (!prepared.dto.recommendationEnabled) { prepared.dto.recommendations = []; prepared.routes = []; }
  const pending = screen.ps5PendingStreamPreference;
  prepared.pending = pending?.profileId === profileId && screen.ps5PendingStreamParams === screen.params &&
    pending.streamId === String(screen.getCurrentStreamCandidate?.()?.id || "") ? pending : null;
  ps5Presentation = { prepared, current };
  return true;
};

globalThis.__nuvioCapturePresentation = function () {
  if (!ps5Presentation?.current()) return null;
  // Freeze a serializable per-session copy, not the live screen or controller.
  return JSON.parse(JSON.stringify(ps5Presentation.prepared));
};

globalThis.__nuvioSendPresentation = async function (session) {
  if (!globalThis.__NUVIO_PS5__ || !/^[a-z0-9-]{1,63}$/i.test(String(session || ""))) return false;
  const saved = LocalStore.get(PS5_PROGRESS_KEY, null);
  if (saved?.session !== session || saved.profileId !== String(ProfileManager.getActiveProfileId()) ||
      saved.general?.profileId !== saved.profileId) return false;
  const source = saved.general.dto;
  if (!source) return false;
  // Never spread saved.general here: it contains browser-only route/identity
  // data. Reconstruct the allowlisted wire format even for restored storage.
  const dto = { session, loading: source.loading === true, loadingDetail: source.loadingDetail === true,
    pause: source.pause === true, clock: source.clock === true,
    description: ps5GeneralText(source.description, 800), parental: ps5GeneralText(source.parental, 800),
    recommendations: (Array.isArray(source.recommendations) ? source.recommendations : []).slice(0, 3)
      .map(item => ({ title: ps5GeneralText(item?.title, 160), description: ps5GeneralText(item?.description, 400) })),
    movie: source.movie === true, recommendationEnabled: source.recommendationEnabled === true,
    thresholdMinutes: source.thresholdMinutes === true, threshold: Number(source.threshold),
    episodeThresholdMinutes: source.episodeThresholdMinutes === true, episodeThreshold: Number(source.episodeThreshold),
    creditsStart: Number(source.creditsStart) || 0, creditsEnd: Number(source.creditsEnd) || 0,
    postCreditsEnd: Number(source.postCreditsEnd) || 0,
    pauseDelayMs: Number.isFinite(Number(source.pauseDelayMs)) ? Math.max(0, Math.min(60000, Number(source.pauseDelayMs))) : 3000,
    utcOffsetMinutes: Math.max(-840, Math.min(840, Number(source.utcOffsetMinutes) || 0)) };
  const body = JSON.stringify(dto);
  if (ps5GeneralBytes(body) > 8192) return false;
  const abort = typeof AbortController === "function" ? new AbortController() : null;
  const timer = setTimeout(() => abort?.abort(), 4000);
  try {
    const response = await fetch("/evo/presentation", { method: "POST", headers: { "Content-Type": "application/json" },
      body, signal: abort?.signal });
    return response.ok && saved.profileId === String(ProfileManager.getActiveProfileId()) &&
      LocalStore.get(PS5_PROGRESS_KEY, null)?.session === session && Boolean(ps5Presentation?.current());
  } catch (_) { return false; }
  finally { clearTimeout(timer); }
};

globalThis.__nuvioAcceptPresentation = function (saved, report) {
  ps5PresentationRoute = null;
  // Caller has already verified the session-bound progress endpoint/context.
  // Some report versions echo session; reject a mismatch when it is present.
  if (!globalThis.__NUVIO_PS5__ || !saved?.session || !report || (report.session != null && saved.session !== report.session) ||
      saved.profileId !== String(ProfileManager.getActiveProfileId()) || saved.general?.profileId !== saved.profileId) return;
  const general = saved.general;
  const pending = general.pending;
  if (report.played === true && pending?.profileId === saved.profileId && pending.contentId && pending.streamId &&
      pending.contentId === general.identity?.itemId && pending.videoId === (general.identity?.videoId || general.identity?.itemId)) {
    StreamPreferencesStore.set(pending.contentId, pending.videoId, pending.streamId, pending.metadata, saved.profileId);
    general.pending = null;
    // Make repeat imports idempotent if the following progress/storage flush
    // fails and startup retries the same successful native report.
    if (LocalStore.get(PS5_PROGRESS_KEY, null)?.session === saved.session) LocalStore.set(PS5_PROGRESS_KEY, saved);
  }
  const index = report.recommendation;
  if (!Number.isInteger(index) || index < 1 || index > 3 || !canResumePs5Playback() ||
      PlayerSettingsStore.get().postPlayRecommendationsEnabled === false || !general.dto?.recommendationEnabled) return;
  const params = general.routes?.[index - 1];
  if (params?.itemId) ps5PresentationRoute = { profileId: saved.profileId, params: { ...params, playOnLoad: false, manualSelection: true } };
};

globalThis.__nuvioTakePresentationRoute = function () {
  const pending = ps5PresentationRoute;
  ps5PresentationRoute = null;
  if (!pending || pending.profileId !== String(ProfileManager.getActiveProfileId()) || !canResumePs5Playback()) return null;
  return pending.params;
};
