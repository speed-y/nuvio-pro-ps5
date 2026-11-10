// Resolve settings through the active player's authoritative helpers, not
// setting-name guesses or browser media-track indices. No storage or logging.
function ps5CaptureNativePreferences(screen) {
  const profile = ProfileManager.getActiveProfileId();
  if (profile == null || String(profile) === "") return null;
  const mode = screen.getStartupSubtitlePreferenceMode?.();
  if (!["off", "language", "audio-forced"].includes(mode) ||
      typeof screen.getStartupPreferredAudioLanguageTargets !== "function" ||
      typeof screen.getStartupAutoSelectSubtitleLanguageTargets !== "function") return null;
  const targets = values => {
    if (!Array.isArray(values) || values.length > 2) return null;
    // Unresolvable labels are not a license to fall back to native English.
    // Keep an unmatchable empty slot so secondary does not become the primary
    // forced-language condition. Never transport arbitrary preference text.
    return values.map(value => typeof value === "string" &&
      /^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/i.test(value) && value.length < 16 ? value : "");
  };
  const audio = targets(screen.getStartupPreferredAudioLanguageTargets());
  const subtitle = targets(screen.getStartupAutoSelectSubtitleLanguageTargets());
  return audio && subtitle ? { mode, audio, subtitle } : null;
}

function ps5NativeSubtitleForced(screen, item) {
  // Use the frontend's isForcedAddonSubtitle classification as exposed by its
  // actual option collector, rather than inventing a separate forced heuristic.
  const options = screen.collectSubtitleOptionItems?.() || [];
  return options.some(option => option.sourceType === "addon" && option.isForced &&
    (option.entry?.track?.url || option.entry?.url) === item.url);
}
