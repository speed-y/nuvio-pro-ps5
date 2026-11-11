// The browser is absent during EVO playback. Keep the frontend's exact progress
// context, not a guessed identity derived from the URL or display title.
const PS5_PROGRESS_KEY = "ps5_native_progress";
globalThis.__nuvioCapturePlayback = function () {
  if (!globalThis.__NUVIO_PS5__ || Router.current !== "player") return "";
  const context = PlayerController.createProgressContext();
  if (!context.itemId) return "";
  const detail = Router.getCurrentScreen()?.buildDetailRouteParamsFromPlayer?.() || null;
  const session = Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
  LocalStore.set(PS5_PROGRESS_KEY, {
    session,
    profileId: String(ProfileManager.getActiveProfileId()),
    context,
    detail: detail ? { ...detail, ps5ReturnEpisodeVideoId: context.season != null ? context.videoId : null } : null,
    next: globalThis.__nuvioCaptureNextEpisode?.() || null,
    general: globalThis.__nuvioCapturePresentation?.() || null
  });
  return session;
};

let ps5ProgressImport;
function restorePs5PlaybackProgress() {
  if (ps5ProgressImport) return ps5ProgressImport;
  ps5ProgressImport = (async () => {
    if (!globalThis.__NUVIO_PS5__) return;
    const saved = LocalStore.get(PS5_PROGRESS_KEY, null);
    const origin = LocalStore.get(PS5_PLAYBACK_RETURN_KEY, null);
    const profileId = String(ProfileManager.getActiveProfileId());
    const profiles = LocalStore.get("profiles", []);
    // A cold launch keeps ordinary profile/PIN selection and route behavior.
    // Recover only after the originating profile is active, without a return TTL.
    if (!saved?.session || !saved.context?.itemId ||
        saved.profileId !== profileId ||
        (origin?.progressSession && saved.session !== origin.progressSession) || !Array.isArray(profiles) ||
        !profiles.some(profile => String(profile.id) === profileId)) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch("/evo/progress?session=" + encodeURIComponent(saved.session), {
        cache: "no-store", signal: controller.signal
      });
      // HTTP 404 can arrive before the native checkpoint is readable. Keep the
      // saved context and retry instead of deleting the only recovery record.
      if (response.status === 204) {
        LocalStore.remove(PS5_PROGRESS_KEY);
        LocalStore.remove(PS5_PLAYBACK_RETURN_KEY);
        globalThis.__nuvioFlushStorage?.();
        return;
      }
      if (response.status === 404 || response.status === 409) return;
      if (!response.ok) throw new Error("Native progress unavailable");
      const report = await response.json();
      const { positionMs, durationMs } = report;
      if (!Number.isFinite(positionMs) || positionMs < 0 ||
          !Number.isFinite(durationMs) || durationMs < 0) return;
      // Never switch profiles to apply an old report, even if fetching yielded.
      if (String(ProfileManager.getActiveProfileId()) !== saved.profileId) return;
      if (positionMs > 0) {
        const progressContext = { ...saved.context };
        delete progressContext.progressSession;
        await PlayerController.flushProgress(positionMs, durationMs, false, progressContext, {
          allowCloudSync: false, syncRemote: true
        });
        LocalStore.remove("homeContinueWatchingDisplaySnapshot");
        globalThis.__nuvioProgressHomeDirty = true;
        const resume = LocalStore.get("webos_last_resume_route", null);
        if (resume?.params) {
          LocalStore.set("webos_last_resume_route", {
            ...resume,
            params: { ...resume.params, resumePositionMs: positionMs, resumeDurationMs: durationMs },
            savedAt: Date.now()
          });
        }
        const home = Router.getCurrent?.() === "home" ? Router.getCurrentScreen?.() : null;
        home?.clearContinueWatchingSnapshot?.();
        home?.refreshHomeContinueWatchingAfterSync?.();
      }
      if (String(ProfileManager.getActiveProfileId()) !== saved.profileId) return;
      globalThis.__nuvioAcceptPresentation?.(saved, report);
      if (report.returnToDetail === true) globalThis.__nuvioAcceptPlaybackDetail?.(saved);
      else globalThis.__nuvioAcceptNextEpisode?.(saved, report.nextEpisode);
      LocalStore.remove(PS5_PROGRESS_KEY);
      LocalStore.remove(PS5_PLAYBACK_RETURN_KEY);
      globalThis.__nuvioFlushStorage?.(); // Flush the existing console storage bridge.
    } catch (error) {
      console.warn("Native playback progress could not be restored", error);
    } finally {
      clearTimeout(timeout);
    }
  })().finally(() => { ps5ProgressImport = null; });
  return ps5ProgressImport;
}
globalThis.__nuvioRestorePlaybackProgress = restorePs5PlaybackProgress;
