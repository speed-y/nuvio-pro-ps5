// Ephemeral candidates only. Never put signed addon URLs in return storage.
let ps5NativeSubtitles = null;
let ps5SubtitleGeneration = 0;

globalThis.__nuvioPrepareSubtitles = async function () {
  ps5NativeSubtitles = null;
  const generation = ++ps5SubtitleGeneration;
  if (!globalThis.__NUVIO_PS5__ || Router.current !== "player") return null;
  const screen = Router.getCurrentScreen();
  if (!screen) return null;
  const params = Router.currentParams;
  const mount = screen.playerMountToken;
  const profile = String(ProfileManager.getActiveProfileId());
  const identity = () => JSON.stringify([params?.itemId, params?.contentId, params?.videoId,
    params?.itemType, params?.season, params?.episode]);
  const initialIdentity = identity();
  const selection = () => String(screen.activePlaybackUrl || "") + "|" +
    String(screen.getCurrentStreamCandidate?.()?.id || "");
  const selected = selection();
  const current = () => generation === ps5SubtitleGeneration && Router.current === "player" &&
    Router.currentParams === params && Router.getCurrentScreen() === screen && screen.playerMountToken === mount &&
    String(ProfileManager.getActiveProfileId()) === profile && selection() === selected && identity() === initialIdentity;
  let timer;
  try {
    // The loader shares a matching in-flight request across initial mount,
    // stream changes and this hook. URL equality alone is not a request:
    // before initial discovery both URL fields can still be undefined.
    const lookup = typeof screen.loadSubtitles === "function" ? screen.loadSubtitles() :
      (screen.ps5SubtitleLoadUrl === screen.activePlaybackUrl ? screen.ps5SubtitleLoadPromise : null);
    await Promise.race([lookup,
      new Promise(resolve => { timer = setTimeout(resolve, 4000); })]);
  } catch (_) { /* Subtitle discovery must not prevent playback. */ }
  finally { clearTimeout(timer); }
  if (!current()) return null;
  const entries = [];
  const seen = new Set();
  for (const item of Array.isArray(screen.subtitles) ? screen.subtitles : []) {
    // Do not silently drop required request headers. Such candidates need a
    // header-aware native downloader before they can be offered safely.
    if (item?.headers && Object.keys(item.headers).length) continue;
    const raw = String(item?.url || "");
    if (!/^https?:\/\//.test(raw) || /[\u0000-\u0020\u007f]/.test(raw) ||
        ps5GeneralBytes(raw) >= 1024) continue;
    let url;
    try {
      url = new URL(raw);
      if (url.username || url.password) continue;
    } catch (_) { continue; }
    if (seen.has(raw)) continue;
    seen.add(raw);
    entries.push({ url: raw, lang: ps5GeneralText(item.lang, 15),
      source: ps5GeneralText(item.addonName || "Addon", 63) });
    if (entries.length === 32) break;
  }
  ps5NativeSubtitles = { current, entries };
  return true;
};

globalThis.__nuvioSendSubtitles = async function (session) {
  const prepared = ps5NativeSubtitles;
  if (!prepared?.current() || !/^[a-z0-9-]{1,63}$/i.test(String(session || ""))) return false;
  const body = JSON.stringify({ session, subtitles: prepared.entries });
  if (ps5GeneralBytes(body) > 49152) return false;
  const abort = typeof AbortController === "function" ? new AbortController() : null;
  const timer = setTimeout(() => abort?.abort(), 4000);
  try {
    const response = await fetch("/evo/subtitles", { method: "POST",
      headers: { "Content-Type": "application/json" }, body, signal: abort?.signal });
    return response.ok && prepared.current();
  } catch (_) { return false; }
  finally { clearTimeout(timer); }
};
