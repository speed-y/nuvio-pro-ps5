"""Continue Watching mark-as-watched and Nuvio Sync round-trip contracts."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import polish
import watch_sync


NODE_HARNESS = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import path from "node:path";

const rootDir = process.argv[2];
const mode = process.argv[3]; // "patched" | "baseline"

function createEnv() {
  const localData = new Map();
  const sessionData = new Map();
  const cloud = {
    watchedItems: new Map(), // key: profileId::contentId::season::episode
    watchProgress: new Map(), // key: profileId::progressKey
    rpcCalls: [],
    flushCount: 0,
    timeline: []
  };

  function seedProfileTables(profileId = 1, { watched = [], progress = [] } = {}) {
    watched.forEach((row) => {
      const k = `${profileId}::${row.content_id}::${row.season ?? ""}::${row.episode ?? ""}`;
      cloud.watchedItems.set(k, { ...row });
    });
    progress.forEach((row) => {
      const k = `${profileId}::${row.progress_key}`;
      cloud.watchProgress.set(k, { ...row });
    });
  }

  function installGlobals(timers, perfConstrained = false) {
    globalThis.__testLocalData = localData;
    globalThis.__testSessionData = sessionData;
    globalThis.__nuvioFlushStorage = () => {
      cloud.flushCount += 1;
      cloud.timeline.push({ type: "flushStorage" });
    };
    globalThis.document = {
      body: {
        classList: {
          contains: (name) => Boolean(perfConstrained && name === "performance-constrained")
        }
      },
      documentElement: { classList: { contains: () => false } }
    };
    globalThis.window = globalThis;
    globalThis.setTimeout = (fn, ms, ...args) => {
      const entry = { fn, ms, args, cleared: false };
      timers.push(entry);
      return entry;
    };
    globalThis.clearTimeout = (entry) => {
      if (entry && typeof entry === "object") {
        entry.cleared = true;
      }
    };
    globalThis.__testRpc = async (name, params) => {
      cloud.rpcCalls.push({ name, params: JSON.parse(JSON.stringify(params || {})) });
      cloud.timeline.push({ type: "rpc", name });
      const pid = String(params?.p_profile_id ?? 1);
      if (name === "sync_pull_watched_items") {
        const prefix = `${pid}::`;
        return Array.from(cloud.watchedItems.entries())
          .filter(([k]) => k.startsWith(prefix))
          .map(([, v]) => ({ ...v }));
      }
      if (name === "sync_push_watched_items") {
        const prefix = `${pid}::`;
        for (const key of Array.from(cloud.watchedItems.keys())) {
          if (key.startsWith(prefix)) cloud.watchedItems.delete(key);
        }
        (params?.p_items || []).forEach((row) => {
          const k = `${pid}::${row.content_id}::${row.season ?? ""}::${row.episode ?? ""}`;
          cloud.watchedItems.set(k, { ...row });
        });
        return { ok: true };
      }
      if (name === "sync_delete_watched_items") {
        (params?.p_keys || []).forEach((item) => {
          const k = `${pid}::${item.content_id}::${item.season ?? ""}::${item.episode ?? ""}`;
          cloud.watchedItems.delete(k);
        });
        return { ok: true };
      }
      if (name === "sync_pull_watch_progress") {
        const prefix = `${pid}::`;
        return Array.from(cloud.watchProgress.entries())
          .filter(([k]) => k.startsWith(prefix))
          .map(([, v]) => ({ ...v }));
      }
      if (name === "sync_push_watch_progress") {
        (params?.p_entries || []).forEach((row) => {
          const k = `${pid}::${row.progress_key}`;
          cloud.watchProgress.set(k, { ...row, profile_id: Number(pid) });
        });
        return { ok: true };
      }
      if (name === "sync_delete_watch_progress") {
        (params?.p_keys || []).forEach((pk) => {
          cloud.watchProgress.delete(`${pid}::${pk}`);
        });
        return { ok: true };
      }
      throw new Error(`Unexpected RPC: ${name}`);
    };
  }

  let sessionTag = 0;
  async function bootSession({ perfConstrained = false, seriesMeta = null } = {}) {
    sessionTag += 1;
    const timers = [];
    installGlobals(timers, perfConstrained);
    globalThis.__testSeriesMeta = seriesMeta;
    const load = (rel) => import(`${pathToFileURL(path.join(rootDir, rel)).href}?boot=${sessionTag}`);

    // Use a dedicated loader tag per app launch so in-memory caches and sync
    // push state start fresh while LocalStore and cloud RPC state persist.
    const { LocalStore } = await load("js/core/storage/localStore.js");
    LocalStore.set("traktSettings", { watchProgressSource: "NUVIO_SYNC" });

    const { watchedItemsRepository } = await load("js/data/repository/watchedItemsRepository.js");
    const { watchProgressRepository } = await load("js/data/repository/watchProgressRepository.js");
    const { WatchedItemsSyncService } = await load("js/core/profile/watchedItemsSyncService.js");
    const { WatchProgressSyncService } = await load("js/core/profile/watchProgressSyncService.js");
    const { watchedItemsShareIdentity } = await load("js/data/repository/watchedIdentity.js");
    const { isWatchProgressCompleted, isWatchProgressInProgress } = await load("js/domain/model/watchProgress.js");
    const { buildWatchedTitleIdSet } = await load("js/ui/components/watchedTitleBadge.js");
    const { normalizeContinueWatchingItem } = await load("js/ui/screens/home/homeScreenHelpers-09-normalize-continue-watching-item.js");
    const { createHomeScreenMethods06 } = await load("js/ui/screens/home/homeScreenMethods-06-get-hero-source-from-focus-state.js");
    const { createHomeScreenMethods08 } = await load("js/ui/screens/home/homeScreenMethods-08-open-hold-menu-for-node.js");
    const { createHomeScreenMethods09 } = await load("js/ui/screens/home/homeScreenMethods-09-toggle-continue-watching-watched.js");

    async function startupPull() {
      await WatchedItemsSyncService.pull(1);
      await WatchProgressSyncService.pull(1);
    }

    function makeHomeScreen(continueWatchingItems = []) {
      const m06 = createHomeScreenMethods06();
      const m08 = createHomeScreenMethods08();
      const m09 = createHomeScreenMethods09();
      const screen = {
        watchedItems: [],
        watchedTitleIds: new Set(),
        allProgress: [],
        continueWatching: [...continueWatchingItems],
        continueWatchingDisplay: [...continueWatchingItems],
        nextUpProgressCandidates: [],
        continueWatchingLoading: false,
        layoutMode: "modern",
        clearContinueWatchingSnapshot() {
          this.snapshotCleared = true;
        },
        pickInitialHero() {
          return this.continueWatching[0] || null;
        },
        ...m06,
        ...m08,
        ...m09
      };
      return screen;
    }

    return {
      timers,
      watchedItemsRepository,
      watchProgressRepository,
      WatchedItemsSyncService,
      WatchProgressSyncService,
      watchedItemsShareIdentity,
      isWatchProgressCompleted,
      isWatchProgressInProgress,
      buildWatchedTitleIdSet,
      normalizeContinueWatchingItem,
      startupPull,
      makeHomeScreen
    };
  }

  return { cloud, seedProfileTables, bootSession };
}

if (mode === "baseline") {
  const env = createEnv();
  env.seedProfileTables(1, {
    watched: [
      { content_id: "ttShow", content_type: "series", title: "Show", season: 1, episode: 1, watched_at: 1000 }
    ],
    progress: [
      {
        content_id: "ttShow",
        content_type: "series",
        video_id: "__nuvio_episode__:1:2",
        season: 1,
        episode: 2,
        position: 900000,
        duration: 2700000,
        last_watched: 2000,
        progress_key: "ttShow_s1e2"
      }
    ]
  });
  const s1 = await env.bootSession({ perfConstrained: true });
  await s1.startupPull();
  const item = {
    contentId: "ttShow",
    contentType: "series",
    type: "series",
    videoId: "ttShow:1:2",
    season: 1,
    episode: 2,
    positionMs: 900000,
    durationMs: 2700000,
    title: "Show"
  };
  const screen = s1.makeHomeScreen([item]);
  screen.watchedItems = await s1.watchedItemsRepository.getAll(2000);
  await screen.markContinueWatchingItemWatched(item);
  const pushRpcs = env.cloud.rpcCalls.filter(
    (c) => c.name === "sync_push_watched_items" || c.name === "sync_push_watch_progress"
  );
  assert.equal(pushRpcs.length, 0, "baseline should fail to push S01E02 after S01E01 is watched");
  process.exit(0);
}

// 1. Series S01E02 (after S01E01 is already watched) with synthetic cloud video_id
// and performance-constrained TV mode pushes immediately and persists across restart.
{
  const env = createEnv();
  env.seedProfileTables(1, {
    watched: [
      { content_id: "ttShow", content_type: "series", title: "Show", season: 1, episode: 1, watched_at: 1000 }
    ],
    progress: [
      {
        content_id: "ttShow",
        content_type: "series",
        video_id: "__nuvio_episode__:1:2",
        season: 1,
        episode: 2,
        position: 900000,
        duration: 2700000,
        last_watched: 2000,
        progress_key: "ttShow_s1e2"
      }
    ]
  });
  const s1 = await env.bootSession({
    perfConstrained: true,
    seriesMeta: {
      id: "ttShow",
      type: "series",
      name: "Show",
      videos: [
        { id: "ttShow:1:1", season: 1, episode: 1, released: "2024-01-01" },
        { id: "ttShow:1:2", season: 1, episode: 2, released: "2024-01-08" },
        { id: "ttShow:1:3", season: 1, episode: 3, released: "2024-01-15" }
      ]
    }
  });
  await s1.startupPull();
  const pulledBefore = await s1.watchProgressRepository.getAll(1);
  assert.equal(pulledBefore[0].videoId, null, "cloud pull strips synthetic __nuvio_episode__ videoId");

  const cwItem = {
    contentId: "ttShow",
    contentType: "series",
    type: "series",
    videoId: "ttShow:1:2",
    season: 1,
    episode: 2,
    positionMs: 900000,
    durationMs: 2700000,
    title: "Show"
  };
  const screen = s1.makeHomeScreen([cwItem]);
  screen.watchedItems = await s1.watchedItemsRepository.getAll(2000);
  screen.watchedTitleIds = s1.buildWatchedTitleIdSet(screen.watchedItems);
  screen.allProgress = pulledBefore;

  assert.equal(screen.isContinueWatchingItemWatched(cwItem), false);
  const ok = await screen.markContinueWatchingItemWatched(cwItem);
  assert.equal(ok, true);
  assert.equal(screen.continueWatching.length, 0);

  // Cloud push must run immediately without waiting for 250ms / 15s debounce timers.
  const activeSyncTimers = s1.timers.filter((t) => !t.cleared && (t.ms === 250 || t.ms === 1500 || t.ms === 15000));
  assert.equal(activeSyncTimers.length, 0, "sync debounce timers must be cleared by flush");
  const pushedWatched = env.cloud.rpcCalls.filter((c) => c.name === "sync_push_watched_items");
  const pushedProgress = env.cloud.rpcCalls.filter((c) => c.name === "sync_push_watch_progress");
  assert.equal(pushedWatched.length >= 1, true, "sync_push_watched_items missing");
  assert.equal(pushedProgress.length >= 1, true, "sync_push_watch_progress missing");

  const remoteE2 = env.cloud.watchProgress.get("1::ttShow_s1e2");
  assert.ok(remoteE2);
  assert.equal(remoteE2.position, 2700000);
  assert.equal(remoteE2.duration, 2700000);
  assert.equal(env.cloud.watchedItems.has("1::ttShow::1::2"), true);
  assert.equal(env.cloud.timeline[env.cloud.timeline.length - 1].type, "flushStorage");

  // Reopen app cleanly and re-run startup cloud pull.
  const s2 = await env.bootSession({ perfConstrained: true });
  await s2.startupPull();
  const watchedAfterReopen = await s2.watchedItemsRepository.getAll(2000);
  const progressAfterReopen = await s2.watchProgressRepository.getAll(1);
  assert.equal(
    watchedAfterReopen.some((e) => e.contentId === "ttShow" && e.season === 1 && e.episode === 2),
    true
  );
  const e2After = progressAfterReopen.find((p) => p.contentId === "ttShow" && p.season === 1 && p.episode === 2);
  assert.ok(e2After);
  assert.equal(s2.isWatchProgressCompleted(e2After), true);
  assert.equal(s2.isWatchProgressInProgress(e2After), false);
}

// 2. Movie already marked in watchedItems (rewatch) + stale partial progressPercent
// + null season/episode normalization: must still complete progress & push to cloud.
{
  const env = createEnv();
  env.seedProfileTables(1, {
    watched: [
      { content_id: "ttMovie", content_type: "movie", title: "Movie", season: null, episode: null, watched_at: 1000 }
    ],
    progress: [
      {
        content_id: "ttMovie",
        content_type: "movie",
        video_id: "ttMovie",
        season: null,
        episode: null,
        position: 600000,
        duration: 5400000,
        progress_percent: 11,
        last_watched: 2000,
        progress_key: "ttMovie"
      }
    ]
  });
  const s1 = await env.bootSession({ perfConstrained: true });
  await s1.startupPull();

  const rawMovieCw = {
    contentId: "ttMovie",
    contentType: "movie",
    type: "movie",
    videoId: "ttMovie",
    season: null,
    episode: null,
    positionMs: 600000,
    durationMs: 5400000,
    progressPercent: 11,
    title: "Movie"
  };
  const normalizedMovie = s1.normalizeContinueWatchingItem(rawMovieCw);
  assert.equal(normalizedMovie.season, null, "movie season must remain null, not 0");
  assert.equal(normalizedMovie.episode, null, "movie episode must remain null, not 0");

  const screen = s1.makeHomeScreen([rawMovieCw]);
  screen.watchedItems = await s1.watchedItemsRepository.getAll(2000);
  screen.watchedTitleIds = s1.buildWatchedTitleIdSet(screen.watchedItems);
  assert.equal(screen.isContinueWatchingItemWatched(rawMovieCw), true);

  const ok = await screen.markContinueWatchingItemWatched(rawMovieCw);
  assert.equal(ok, true);
  assert.equal(screen.continueWatching.length, 0);

  const remoteMovie = env.cloud.watchProgress.get("1::ttMovie");
  assert.ok(remoteMovie);
  assert.equal(remoteMovie.position, 5400000);
  assert.equal(remoteMovie.duration, 5400000);

  const localMovie = (await s1.watchProgressRepository.getAll(1)).find((p) => p.contentId === "ttMovie");
  assert.equal(localMovie.progressPercent, 100);

  const s2 = await env.bootSession({ perfConstrained: true });
  await s2.startupPull();
  const reopenedMovie = (await s2.watchProgressRepository.getAll(1)).find((p) => p.contentId === "ttMovie");
  assert.equal(s2.isWatchProgressCompleted(reopenedMovie), true);
  assert.equal(s2.isWatchProgressInProgress(reopenedMovie), false);
  assert.equal(await s2.watchedItemsRepository.isWatched("ttMovie"), true);
}

// 3. Next Up item without stored progress + alias ID progress match create/complete
// >= 60000ms syncable progress and push to Supabase.
{
  const env = createEnv();
  env.seedProfileTables(1, {
    watched: [
      { content_id: "ttShow2", content_type: "series", title: "Show 2", season: 1, episode: 1, watched_at: 1000 }
    ],
    progress: [
      {
        content_id: "tmdb:550",
        content_type: "movie",
        video_id: "tmdb:550",
        season: null,
        episode: null,
        position: 500000,
        duration: 4200000,
        last_watched: 2000,
        progress_key: "tmdb:550"
      }
    ]
  });
  const s1 = await env.bootSession();
  await s1.startupPull();

  const nextUpItem = {
    contentId: "ttShow2",
    contentType: "series",
    type: "series",
    videoId: "ttShow2:1:2",
    season: 1,
    episode: 2,
    isNextUp: true,
    title: "Show 2"
  };
  const screen = s1.makeHomeScreen([nextUpItem]);
  screen.watchedItems = await s1.watchedItemsRepository.getAll(2000);
  await screen.markContinueWatchingItemWatched(nextUpItem);
  const remoteNextUp = env.cloud.watchProgress.get("1::ttShow2_s1e2");
  assert.ok(remoteNextUp, "Next Up completion must create syncable progress row");
  assert.equal(remoteNextUp.position, 60000);
  assert.equal(remoteNextUp.duration, 60000);
  assert.equal(env.cloud.watchedItems.has("1::ttShow2::1::2"), true);

  // Alias match: progress saved under tmdb:550, CW card uses tt0137523 with tmdbId 550.
  const aliasMovie = {
    contentId: "tt0137523",
    tmdbId: 550,
    imdbId: "tt0137523",
    contentType: "movie",
    type: "movie",
    videoId: "tt0137523",
    season: null,
    episode: null,
    title: "Alias Movie"
  };
  screen.continueWatching.push(aliasMovie);
  await screen.markContinueWatchingItemWatched(aliasMovie);
  const remoteAlias = env.cloud.watchProgress.get("1::tmdb:550");
  assert.equal(remoteAlias.position, 4200000);
  assert.equal(remoteAlias.duration, 4200000);
}
"""


def _stage_frontend_tree(root_dir, apply_patch):
    pin = next(p for p in json.loads((ROOT / "deps.lock").read_text())["artifacts"]
               if p["id"] == "nuvio-tv-source")
    archive = ROOT / ".cache" / pin["cache_file"]
    if not archive.exists():
        raise unittest.SkipTest("Pinned Nuvio archive not cached; no network fetch")
    with tarfile.open(archive) as tf:
        tf.extractall(root_dir, filter="data")
    nv = Path(root_dir) / pin["directory"]
    if apply_patch:
        watch_sync.patch_frontend(nv)

    # Replace only external IO, network, auth and UI context boundaries.
    (nv / "js/core/storage/localStore.js").write_text(
        "export const LocalStore = {\n"
        "  get(k, d = null) { return globalThis.__testLocalData.has(k) ? JSON.parse(globalThis.__testLocalData.get(k)) : d; },\n"
        "  set(k, v) { globalThis.__testLocalData.set(k, JSON.stringify(v)); },\n"
        "  remove(k) { globalThis.__testLocalData.delete(k); }\n"
        "};\n"
    )
    (nv / "js/core/storage/sessionStore.js").write_text(
        "export const SessionStore = {\n"
        "  get(k, d = null) { return globalThis.__testSessionData.has(k) ? JSON.parse(globalThis.__testSessionData.get(k)) : d; },\n"
        "  set(k, v) { globalThis.__testSessionData.set(k, JSON.stringify(v)); },\n"
        "  remove(k) { globalThis.__testSessionData.delete(k); }\n"
        "};\n"
    )
    (nv / "js/data/remote/supabase/supabaseApi.js").write_text(
        "export const SupabaseApi = { async rpc(name, params) { return globalThis.__testRpc(name, params); } };\n"
    )
    (nv / "js/core/auth/authManager.js").write_text(
        "export const AuthManager = {\n"
        "  isAuthenticated: true,\n"
        "  getAuthState() { return 'authenticated'; },\n"
        "  subscribe() { return () => {}; }\n"
        "};\n"
    )
    (nv / "js/data/mediaserver/manualServerWatched.js").write_text(
        "export function hasPendingManualWatched() { return false; }\n"
        "export function beginManualWatched(items) { return { items }; }\n"
        "export function manualWatchedCurrent() { return true; }\n"
        "export function captureManualWatched() {}\n"
        "export function finishManualWatched() {}\n"
        "export async function applyManualServerWatched(items) { return items; }\n"
    )
    (nv / "js/data/repository/metaRepository.js").write_text(
        "export const metaRepository = {\n"
        "  async getMetaFromAllAddons() { return { status: 'success', data: globalThis.__testSeriesMeta || null }; }\n"
        "};\n"
    )
    (nv / "js/i18n/index.js").write_text(
        "export const I18n = { t(k, _vars, fallback) { return fallback || k; } };\n"
    )
    (nv / "js/ui/navigation/routerState.js").write_text("export const Router = { current: 'home', navigate() {} };\n")
    (nv / "js/ui/navigation/screen.js").write_text("export const ScreenUtils = {};\n")
    (nv / "js/ui/screens/home/homeScreenContext.js").write_text(
        'export { Router } from "../../navigation/routerState.js";\n'
        'export { watchProgressRepository } from "../../../data/repository/watchProgressRepository.js";\n'
        'export { CloudLibraryPlaybackProgressStore } from "../../../data/local/cloudLibraryPlaybackStore.js";\n'
        'export { watchedItemsRepository } from "../../../data/repository/watchedItemsRepository.js";\n'
        'export { watchedItemsShareIdentity } from "../../../data/repository/watchedIdentity.js";\n'
        'export { watchedSeriesReconciliationService } from "../../../data/repository/watchedSeriesReconciliationService.js";\n'
        'export { savedLibraryRepository } from "../../../data/repository/savedLibraryRepository.js";\n'
        'export { ContinueWatchingPreferences } from "../../../data/local/continueWatchingPreferences.js";\n'
        'export { buildWatchedTitleIdSet, isTitleItemWatched } from "../../components/watchedTitleBadge.js";\n'
        'export { isSeriesTypeForContinueWatching } from "./homeScreenHelpers-06-resolve-trailer-source.js";\n'
        'export { normalizeContinueWatchingItem, isCloudContinueWatchingItem } from "./homeScreenHelpers-09-normalize-continue-watching-item.js";\n'
    )
    return nv


class ContinueWatchingSyncTests(unittest.TestCase):
    def test_moved_anchors_are_refused(self):
        for fn in (
            watch_sync.patch_normalize_continue_watching_source,
            watch_sync.patch_home_hero_watched_source,
            watch_sync.patch_watched_items_repository_source,
            watch_sync.patch_watch_progress_repository_source,
            watch_sync.patch_home_toggle_watched_source,
        ):
            with self.assertRaises(ValueError):
                fn("// unrelated moved anchor\n")

    def test_polish_applies_watch_sync_cleanly_to_pinned_archive(self):
        pin = next(p for p in json.loads((ROOT / "deps.lock").read_text())["artifacts"]
                   if p["id"] == "nuvio-tv-source")
        archive = ROOT / ".cache" / pin["cache_file"]
        if not archive.exists():
            self.skipTest("Pinned Nuvio archive not cached; no network fetch")
        with tempfile.TemporaryDirectory() as td:
            with tarfile.open(archive) as tf:
                tf.extractall(td, filter="data")
            nv = Path(td) / pin["directory"]
            polish.patch_nuvio(nv)
            self.assertIn("flushCloudSync", (nv / "js/data/repository/watchProgressRepository.js").read_text())
            self.assertIn("flushCloudSync", (nv / "js/data/repository/watchedItemsRepository.js").read_text())
            self.assertIn("toOptionalContinueWatchingInt", (
                nv / "js/ui/screens/home/homeScreenHelpers-09-normalize-continue-watching-item.js"
            ).read_text())

    def test_continue_watching_mark_watched_syncs_and_survives_reopen(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node runtime unavailable in test PATH")
        with tempfile.TemporaryDirectory() as td:
            patched_nv = _stage_frontend_tree(Path(td) / "patched", True)
            baseline_nv = _stage_frontend_tree(Path(td) / "baseline", False)
            script = Path(td) / "harness.mjs"
            script.write_text(NODE_HARNESS)
            for label, tree in (("baseline", baseline_nv), ("patched", patched_nv)):
                result = subprocess.run(
                    [node, str(script), str(tree), label],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, f"{label} failed:\n{result.stdout}\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
