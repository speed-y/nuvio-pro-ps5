// EVO recreates the browser after playback. Resume the profile that opened Player
// once, rather than treating that browser as a new app launch.
const PS5_PLAYBACK_RETURN_KEY = "ps5_playback_return";
const ps5PlaybackReturn = globalThis.__NUVIO_PS5__
  ? LocalStore.get(PS5_PLAYBACK_RETURN_KEY, null) : null;
// Keep a pending import recoverable if the recreated browser loses transport.
if (globalThis.__NUVIO_PS5__ && !ps5PlaybackReturn?.progressSession) {
  LocalStore.remove(PS5_PLAYBACK_RETURN_KEY);
}

// Read the live route: history updates only after player mounting, while EVO
// intercepts the media source during that mount.
globalThis.__nuvioPlaybackStartSeconds = function () {
  if (!globalThis.__NUVIO_PS5__ || Router.current !== "player") return 0;
  const params = Router.currentParams || {};
  if (params.startFromBeginning) return 0;
  const position = Number(params.resumePositionMs);
  if (Number.isFinite(position) && position > 0) return position / 1000;
  const percent = Number(params.resumeProgressPercent);
  const duration = Number(params.resumeDurationMs);
  if (Number.isFinite(percent) && percent > 0 && Number.isFinite(duration) && duration > 0) {
    return Math.min(100, percent) * duration / 100000;
  }
  return 0;
};

globalThis.__nuvioSavePlaybackReturn = function () {
  if (!globalThis.__NUVIO_PS5__) return;
  const progressSession = globalThis.__nuvioCapturePlayback?.() || "";
  LocalStore.set(PS5_PLAYBACK_RETURN_KEY, {
    profileId: String(ProfileManager.getActiveProfileId()),
    progressSession,
    resume: LocalStore.get("webos_last_resume_route", null),
    savedAt: Date.now()
  });
  return progressSession;
};

function canResumePs5Playback() {
  if (!ps5PlaybackReturn || !globalThis.__NUVIO_PS5__) return false;
  if (new URLSearchParams(window.location.search).get("nuvioPlaybackReturn") !== "1") return false;
  const age = Date.now() - Number(ps5PlaybackReturn.savedAt);
  if (!Number.isFinite(age) || age < 0 || age > 24 * 60 * 60 * 1000) return false;
  const id = String(ProfileManager.getActiveProfileId());
  if (ps5PlaybackReturn.profileId !== id) return false;
  const profiles = LocalStore.get("profiles", []);
  if (!Array.isArray(profiles) || !profiles.some(profile => String(profile.id) === id)) return false;
  const resume = ps5PlaybackReturn.resume;
  if (resume && Router.isWebOsResumeRouteRestorable(resume.route)) {
    // Browser recreation is a playback return, not a fresh Play request.
    // Use the existing stream opt-out instead of changing the user's setting.
    const params = { ...resume.params };
    if (resume.route === "stream") params.manualSelection = true;
    if (resume.route === "detail") {
      delete params.playOnLoad;
      delete params.autoOpenContinueWatching;
    }
    // The route's normal 20-minute lifetime must not expire during a movie.
    LocalStore.set("webos_last_resume_route", { ...resume, params, savedAt: Date.now() });
  } else {
    LocalStore.remove("webos_last_resume_route");
  }
  return true;
}

// Only an explicit live return can replace the browsing route with this title.
// A recovered checkpoint must never reopen an episode or bypass profile gates.
let ps5PlaybackDetail = null;
globalThis.__nuvioAcceptPlaybackDetail = function (saved) {
  if (!saved.detail?.itemId || !canResumePs5Playback()) return;
  const params = { ...saved.detail };
  delete params.playOnLoad;
  delete params.autoOpenContinueWatching;
  ps5PlaybackDetail = { profileId: saved.profileId, params };
};

globalThis.__nuvioTakePlaybackDetailRoute = function () {
  const pending = ps5PlaybackDetail;
  ps5PlaybackDetail = null;
  return pending?.profileId === String(ProfileManager.getActiveProfileId()) ? pending.params : null;
};
