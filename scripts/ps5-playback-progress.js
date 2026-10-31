// The browser is absent during EVO playback. Keep the frontend's exact progress
// context, not a guessed identity derived from the URL or display title.
const PS5_PROGRESS_KEY = "ps5_native_progress";
globalThis.__nuvioCapturePlayback = function () {
  if (!globalThis.__NUVIO_PS5__ || Router.current !== "player") return "";
  const context = PlayerController.createProgressContext();
  if (!context.itemId) return "";
  const session = Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
  LocalStore.set(PS5_PROGRESS_KEY, {
    session,
    profileId: String(ProfileManager.getActiveProfileId()),
    context
  });
  return session;
};

let ps5ProgressImport;
function restorePs5PlaybackProgress() {
  if (ps5ProgressImport) return ps5ProgressImport;
  ps5ProgressImport = (async () => {
    if (!canResumePs5Playback()) return;
    const saved = LocalStore.get(PS5_PROGRESS_KEY, null);
    if (!saved?.session || !saved.context?.itemId ||
        saved.profileId !== ps5PlaybackReturn.profileId ||
        saved.session !== ps5PlaybackReturn.progressSession) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch("/evo/progress?session=" + encodeURIComponent(saved.session), {
        cache: "no-store", signal: controller.signal
      });
      if (response.status === 204 || response.status === 404) {
        LocalStore.remove(PS5_PROGRESS_KEY);
        LocalStore.remove(PS5_PLAYBACK_RETURN_KEY);
        globalThis.__nuvioPrepareKeyboard?.();
        return;
      }
      if (!response.ok) throw new Error("Native progress unavailable");
      const { positionMs, durationMs } = await response.json();
      if (!Number.isFinite(positionMs) || positionMs <= 0 ||
          !Number.isFinite(durationMs) || durationMs < 0) return;
      // Never switch profiles to apply an old report, even if fetching yielded.
      if (String(ProfileManager.getActiveProfileId()) !== saved.profileId) return;
      await PlayerController.flushProgress(positionMs, durationMs, false, saved.context, {
        allowCloudSync: false, syncRemote: true
      });
      LocalStore.remove(PS5_PROGRESS_KEY);
      LocalStore.remove(PS5_PLAYBACK_RETURN_KEY);
      globalThis.__nuvioPrepareKeyboard?.(); // Flush the existing console storage bridge.
    } catch (error) {
      console.warn("Native playback progress could not be restored", error);
    } finally {
      clearTimeout(timeout);
    }
  })().finally(() => { ps5ProgressImport = null; });
  return ps5ProgressImport;
}
