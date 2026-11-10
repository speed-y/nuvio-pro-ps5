// Resolve before EVO closes the browser. Only timestamps travel to native code;
// the native player never needs an account, addon URL or metadata service.
globalThis.__nuvioPlaybackSkipSegments = async function () {
  if (!globalThis.__NUVIO_PS5__ || Router.current !== "player") return "";
  const params = Router.currentParams;
  const profile = String(ProfileManager.getActiveProfileId());
  const screen = Router.getCurrentScreen();
  const identity = screen?.buildPlaybackIdentityContext?.();
  if (!identity || !PlayerSettingsStore.get().skipIntroEnabled) return "";
  let timer;
  let intervals = [];
  try {
    const request = ["series", "tv", "show", "tvshow"].includes(identity.itemType)
      ? skipIntroRepository.getSkipIntervals(identity.imdbId, identity.season, identity.episode)
      : skipIntroRepository.getMovieSkipIntervals({
          imdbId: identity.imdbId, tmdbId: identity.tmdbId,
          contentId: params?.itemId || params?.contentId, videoId: params?.videoId
        });
    intervals = await Promise.race([
      request,
      new Promise(resolve => { timer = setTimeout(() => resolve([]), 4000); })
    ]);
  } catch (_) {
    // Metadata failure must not prevent playback.
  } finally {
    clearTimeout(timer);
  }
  // Never start an old selection after the user navigates or changes profile.
  if (Router.current !== "player" || Router.currentParams !== params ||
      String(ProfileManager.getActiveProfileId()) !== profile) return null;
  const settings = PlayerSettingsStore.get();
  if (!settings.skipIntroEnabled || !Array.isArray(intervals)) return "";
  return intervals.filter(interval => ["intro", "recap", "outro", "ed", "mixed-ed", "movie-credits"].includes(interval?.type))
    .map(interval => {
      const setting = ["outro", "ed", "mixed-ed"].includes(interval.type) ? "outro" : interval.type;
      const type = setting === "intro" ? "i" : setting === "recap" ? "r" : "c";
      return {
        type: settings.autoSkipSegmentTypes?.includes(setting) ? type.toUpperCase() : type,
        start: Number(interval.startTime),
        end: getSkipIntervalTargetSeconds(interval, intervals)
      };
    })
    .filter(({ start, end }) => Number.isFinite(start) && Number.isFinite(end) &&
      start >= 0 && end > start && end <= Number.MAX_SAFE_INTEGER / 1000)
    .slice(0, 4)
    .map(({ type, start, end }) => `${type},${start.toFixed(3)},${end.toFixed(3)};`).join("");
};
