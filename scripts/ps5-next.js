// Save episode identity before the browser closes. Resolve a fresh stream only
// after the native countdown/action returns through the normal profile gate.
globalThis.__nuvioCaptureNextEpisode = function () {
  if (!globalThis.__NUVIO_PS5__ || Router.current !== "player") return null;
  const screen = Router.getCurrentScreen();
  const next = screen?.resolveNextEpisodeInfo?.();
  if (!next?.videoId || !next.hasAired) return null;
  const settings = PlayerSettingsStore.get();
  const count = Number(screen.consecutiveAutoPlayCount || 0);
  const stillWatching = shouldEnterStillWatchingPrompt({
    stillWatchingEnabled: settings.stillWatchingEnabled,
    autoPlayNextEpisodeEnabled: settings.autoplayNextEpisode,
    nextEpisodeHasAired: true,
    consecutiveAutoPlayCount: count,
    threshold: settings.stillWatchingEpisodeThreshold
  });
  const minutes = normalizeNextEpisodeThresholdMode(settings.nextEpisodeThresholdMode) === "MINUTES_BEFORE_END";
  const threshold = minutes ? normalizeThresholdMinutesBeforeEnd(settings.nextEpisodeThresholdMinutesBeforeEnd) * 60
    : normalizeThresholdPercent(settings.nextEpisodeThresholdPercent) / 100;
  return {
    policy: `${settings.autoplayNextEpisode ? stillWatching ? 2 : 1 : 0},${settings.nextEpisodeCountdownEnabled === false ? 0 : 3},${minutes ? "s" : "p"},${threshold}`,
    params: {
      ...screen.buildStreamRouteParamsFromPlayer(),
      playerTitle: screen.params?.playerTitle || screen.params?.itemTitle || screen.params?.itemId,
      playerBackdropUrl: screen.params?.playerBackdropUrl || null,
      playerLogoUrl: screen.params?.playerLogoUrl || null,
      consecutiveAutoPlayCount: count,
      ps5NativeBingeGroup: screen.getCurrentStreamBingeGroup(),
      resumePositionMs: 0
    }
  };
};

globalThis.__nuvioPlaybackNextPolicy = function (session) {
  const saved = LocalStore.get(PS5_PROGRESS_KEY, null);
  return session && saved?.session === session ? saved.next?.policy || "" : "";
};

let ps5NextReturn = null;
let ps5NextAuthorization = "";
globalThis.__nuvioAcceptNextEpisode = function (saved, mode) {
  if ((mode !== 1 && mode !== 2) || !saved.next?.params || !canResumePs5Playback()) return;
  if (mode === 2 && !PlayerSettingsStore.get().autoplayNextEpisode) return;
  ps5NextReturn = {
    profileId: saved.profileId,
    params: { ...saved.next.params, ps5NextEpisodeSession: saved.session, ps5NextEpisodeUserInitiated: mode === 1 }
  };
};

globalThis.__nuvioTakeNextEpisodeRoute = function () {
  const pending = ps5NextReturn;
  ps5NextReturn = null;
  if (!pending || pending.profileId !== String(ProfileManager.getActiveProfileId())) return null;
  ps5NextAuthorization = pending.params.ps5NextEpisodeSession;
  return pending.params;
};

globalThis.__nuvioConsumeNextEpisode = function (params) {
  if (!ps5NextAuthorization || params.ps5NextEpisodeSession !== ps5NextAuthorization) return false;
  ps5NextAuthorization = "";
  delete params.ps5NextEpisodeSession;
  return true;
};
