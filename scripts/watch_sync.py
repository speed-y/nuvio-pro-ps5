"""Keep Continue Watching mark-as-watched changes synced with Nuvio Sync."""
from pathlib import Path

_EPISODE_VIDEO_HELPERS = """function toOptionalProgressInt(value, { allowZero = false } = {}) {
  if (value == null || value === "" || typeof value === "boolean") {
    return null;
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return null;
  }
  const integer = Math.trunc(numeric);
  if (allowZero) {
    return integer >= 0 ? integer : null;
  }
  return integer > 0 ? integer : null;
}

function extractProgressEpisode(record = {}, fallbackVideoId = null, fallbackContentId = null) {
  const explicitSeason = toOptionalProgressInt(record?.season, { allowZero: true });
  const explicitEpisode = toOptionalProgressInt(record?.episode, { allowZero: false });
  if (explicitSeason != null && explicitEpisode != null) {
    return { season: explicitSeason, episode: explicitEpisode };
  }
  const rawVid = String(record?.videoId ?? fallbackVideoId ?? "").trim();
  const baseContentId = String(record?.contentId ?? fallbackContentId ?? "").trim();
  if (!rawVid || rawVid === "main" || (baseContentId && rawVid === baseContentId)) {
    return null;
  }
  if (rawVid.startsWith("__nuvio_episode__:")) {
    const parts = rawVid.slice("__nuvio_episode__:".length).split(":");
    if (parts.length === 2) {
      const season = toOptionalProgressInt(parts[0], { allowZero: true });
      const episode = toOptionalProgressInt(parts[1], { allowZero: false });
      if (season != null && episode != null) {
        return { season, episode };
      }
    }
    return null;
  }
  const parts = rawVid.split(":");
  if (parts.length >= 3 && parts.slice(0, -2).join(":").trim()) {
    const rawSeason = parts[parts.length - 2];
    const rawEpisode = parts[parts.length - 1];
    if (/^\\d+$/.test(rawSeason) && /^\\d+$/.test(rawEpisode)) {
      const season = toOptionalProgressInt(rawSeason, { allowZero: true });
      const episode = toOptionalProgressInt(rawEpisode, { allowZero: false });
      if (season != null && episode != null) {
        return { season, episode };
      }
    }
  }
  return null;
}

function normalizeVariantVideoId(rawVideoId, rawContentId) {
  const cid = String(rawContentId || "").trim();
  const vid = String(rawVideoId || "").trim();
  if (!vid || vid === "main" || (cid && vid === cid)) {
    return "";
  }
  return vid;
}"""


def _replace_exact(source, old, new, label):
    if old not in source:
        raise ValueError(f"Missing anchor in {label}: {old.splitlines()[0]!r}")
    return source.replace(old, new, 1)


def patch_normalize_continue_watching_source(source):
    """Avoid turning movie null season/episode fields into 0."""
    source = _replace_exact(
        source,
        "export function normalizeContinueWatchingItem(item) {",
        """function toOptionalContinueWatchingInt(value) {
  if (value == null || value === "" || typeof value === "boolean") {
    return null;
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export function normalizeContinueWatchingItem(item) {""",
        "homeScreenHelpers-09 normalize header",
    )
    return _replace_exact(
        source,
        """    season: Number.isFinite(Number(item.season)) ? Number(item.season) : null,
    episode: Number.isFinite(Number(item.episode)) ? Number(item.episode) : null,""",
        """    season: toOptionalContinueWatchingInt(item.season),
    episode: toOptionalContinueWatchingInt(item.episode),""",
        "homeScreenHelpers-09 season/episode",
    )


def patch_home_hero_watched_source(source):
    """Match episode items by season and episode so S01E01 does not hide S01E02."""
    return _replace_exact(
        source,
        """    isContinueWatchingItemWatched(item) {
      const contentId = String(item?.contentId || "");
      if (!contentId) {
        return false;
      }
      return Boolean((this.watchedItems || []).some((entry) => watchedItemsShareIdentity(entry, item)));
    },""",
        """    isContinueWatchingItemWatched(item) {
      const contentId = String(item?.contentId || "");
      if (!contentId) {
        return false;
      }
      const parseEpisode = (record = {}) => {
        if (
          record?.season != null &&
          record.season !== "" &&
          typeof record.season !== "boolean" &&
          record?.episode != null &&
          record.episode !== "" &&
          typeof record.episode !== "boolean"
        ) {
          const s = Math.trunc(Number(record.season));
          const e = Math.trunc(Number(record.episode));
          if (Number.isFinite(s) && s >= 0 && Number.isFinite(e) && e > 0) {
            return { season: s, episode: e };
          }
        }
        const vid = String(record?.videoId || "").trim();
        const cid = String(record?.contentId || record?.id || "").trim();
        if (!vid || vid === "main" || (cid && vid === cid)) {
          return null;
        }
        const parts = vid.split(":");
        if (parts.length >= 3 && parts.slice(0, -2).join(":").trim()) {
          const rawS = parts[parts.length - 2];
          const rawE = parts[parts.length - 1];
          if (/^\\d+$/.test(rawS) && /^\\d+$/.test(rawE)) {
            const s = Number(rawS);
            const e = Number(rawE);
            if (s >= 0 && e > 0) {
              return { season: s, episode: e };
            }
          }
        }
        return null;
      };
      const targetEp = parseEpisode(item);
      return Boolean(
        (this.watchedItems || []).some((entry) => {
          if (!watchedItemsShareIdentity(entry, item)) {
            return false;
          }
          const entryEp = parseEpisode(entry);
          if (targetEp) {
            return entryEp
              ? entryEp.season === targetEp.season && entryEp.episode === targetEp.episode
              : true;
          }
          return entryEp == null;
        })
      );
    },""",
        "homeScreenMethods-06 isContinueWatchingItemWatched",
    )


def patch_watched_items_repository_source(source):
    """Expose immediate cloud push flushing for watched items."""
    source = _replace_exact(
        source,
        """function queueWatchedItemsCloudSync(profileId = activeProfileId(), delayMs = 250) {
  const profileKey = String(profileId || "1");
  const generation = watchedItemsSyncGeneration;
  const existingTimer = watchedItemsSyncTimers.get(profileKey);
  if (existingTimer) {
    clearTimeout(existingTimer);
  }
  const timerId = setTimeout(() => {
    if (generation !== watchedItemsSyncGeneration) {
      return;
    }
    watchedItemsSyncTimers.delete(profileKey);
    const runPush = async () => {
      if (generation !== watchedItemsSyncGeneration) {
        return;
      }
      const inFlight = watchedItemsSyncInFlightByProfile.get(profileKey);
      if (inFlight) {
        await inFlight.catch(() => false);
      }
      if (generation !== watchedItemsSyncGeneration) {
        return;
      }
      const pushPromise = import("../../core/profile/watchedItemsSyncService.js")
        .then(({ WatchedItemsSyncService }) => WatchedItemsSyncService.push(profileId))
        .catch((error) => {
          console.warn("Watched items cloud sync enqueue failed", error);
          return false;
        })
        .finally(() => {
          if (watchedItemsSyncInFlightByProfile.get(profileKey) === pushPromise) {
            watchedItemsSyncInFlightByProfile.delete(profileKey);
          }
        });
      watchedItemsSyncInFlightByProfile.set(profileKey, pushPromise);
      const didPush = await pushPromise;
      if (generation !== watchedItemsSyncGeneration) {
        return;
      }
      if (!didPush) {
        const retryDelayMs = getSyncBackoffRemainingMs();
        if (retryDelayMs > 0) {
          queueWatchedItemsCloudSync(profileId, Math.max(5000, retryDelayMs));
        }
      }
    };
    void runPush();
  }, delayMs);
  watchedItemsSyncTimers.set(profileKey, timerId);
}""",
        """async function runWatchedItemsCloudPush(
  profileId = activeProfileId(),
  generation = watchedItemsSyncGeneration
) {
  const profileKey = String(profileId || "1");
  const existingTimer = watchedItemsSyncTimers.get(profileKey);
  if (existingTimer) {
    clearTimeout(existingTimer);
    watchedItemsSyncTimers.delete(profileKey);
  }
  if (generation !== watchedItemsSyncGeneration) {
    return false;
  }
  const inFlight = watchedItemsSyncInFlightByProfile.get(profileKey);
  if (inFlight) {
    await inFlight.catch(() => false);
  }
  if (generation !== watchedItemsSyncGeneration) {
    return false;
  }
  const pushPromise = import("../../core/profile/watchedItemsSyncService.js")
    .then(({ WatchedItemsSyncService }) => WatchedItemsSyncService.push(profileId))
    .catch((error) => {
      console.warn("Watched items cloud sync enqueue failed", error);
      return false;
    })
    .finally(() => {
      if (watchedItemsSyncInFlightByProfile.get(profileKey) === pushPromise) {
        watchedItemsSyncInFlightByProfile.delete(profileKey);
      }
    });
  watchedItemsSyncInFlightByProfile.set(profileKey, pushPromise);
  const didPush = await pushPromise;
  if (generation !== watchedItemsSyncGeneration) {
    return false;
  }
  if (!didPush) {
    const retryDelayMs = getSyncBackoffRemainingMs();
    if (retryDelayMs > 0) {
      queueWatchedItemsCloudSync(profileId, Math.max(5000, retryDelayMs));
    }
  }
  return Boolean(didPush);
}

function queueWatchedItemsCloudSync(profileId = activeProfileId(), delayMs = 250) {
  const profileKey = String(profileId || "1");
  const generation = watchedItemsSyncGeneration;
  const existingTimer = watchedItemsSyncTimers.get(profileKey);
  if (existingTimer) {
    clearTimeout(existingTimer);
  }
  const timerId = setTimeout(() => {
    if (generation !== watchedItemsSyncGeneration) {
      return;
    }
    watchedItemsSyncTimers.delete(profileKey);
    void runWatchedItemsCloudPush(profileId, generation);
  }, delayMs);
  watchedItemsSyncTimers.set(profileKey, timerId);
}""",
        "watchedItemsRepository queueWatchedItemsCloudSync",
    )
    source = _replace_exact(
        source,
        """    invalidateTraktWatchedForItems(normalizedItems);
    queueWatchedItemsCloudSync(profileId);
    const current = succeeded.filter((item) => manualWatchedCurrent(operation, item));""",
        """    invalidateTraktWatchedForItems(normalizedItems);
    globalThis.__nuvioFlushStorage?.();
    if (options?.syncNow === true) {
      await this.flushCloudSync(profileId);
    } else if (options?.syncRemote !== false) {
      queueWatchedItemsCloudSync(profileId);
    }
    const current = succeeded.filter((item) => manualWatchedCurrent(operation, item));""",
        "watchedItemsRepository markBatch",
    )
    source = _replace_exact(
        source,
        """    await deleteWatchedItemsFromCloud(removedItems, pid);
    queueWatchedItemsCloudSync(pid);
    return targets.every((item) => manualWatchedCurrent(operation, item));""",
        """    await deleteWatchedItemsFromCloud(removedItems, pid);
    globalThis.__nuvioFlushStorage?.();
    if (options?.syncNow === true) {
      await this.flushCloudSync(pid);
    } else if (options?.syncRemote !== false) {
      queueWatchedItemsCloudSync(pid);
    }
    return targets.every((item) => manualWatchedCurrent(operation, item));""",
        "watchedItemsRepository unmark",
    )
    return _replace_exact(
        source,
        """  async replaceAll(items, profileId = activeProfileId()) {""",
        """  async flushCloudSync(profileId = activeProfileId()) {
    return runWatchedItemsCloudPush(profileId, watchedItemsSyncGeneration);
  }

  async replaceAll(items, profileId = activeProfileId()) {""",
        "watchedItemsRepository flushCloudSync",
    )


def patch_watch_progress_repository_source(source):
    """Match episode/alias progress accurately and support completed progress creation + flush."""
    source = _replace_exact(
        source,
        """function queueWatchProgressCloudSync(
  profileId = activeProfileId(),
  delayMs = getWatchProgressSyncDebounceMs()
) {
  const profileKey = String(profileId || "1");
  const generation = watchProgressSyncGeneration;
  const existingTimer = watchProgressSyncTimers.get(profileKey);
  if (existingTimer) {
    clearTimeout(existingTimer);
  }
  const timerId = setTimeout(() => {
    if (generation !== watchProgressSyncGeneration) {
      return;
    }
    watchProgressSyncTimers.delete(profileKey);
    const runPush = async () => {
      if (generation !== watchProgressSyncGeneration) {
        return;
      }
      const inFlight = watchProgressSyncInFlightByProfile.get(profileKey);
      if (inFlight) {
        await inFlight.catch(() => false);
      }
      if (generation !== watchProgressSyncGeneration) {
        return;
      }
      const pushPromise = import("../../core/profile/watchProgressSyncService.js")
        .then(({ WatchProgressSyncService }) => WatchProgressSyncService.push(profileId))
        .catch((error) => {
          console.warn("Watch progress cloud sync enqueue failed", error);
          return false;
        })
        .finally(() => {
          if (watchProgressSyncInFlightByProfile.get(profileKey) === pushPromise) {
            watchProgressSyncInFlightByProfile.delete(profileKey);
          }
        });
      watchProgressSyncInFlightByProfile.set(profileKey, pushPromise);
      const didPush = await pushPromise;
      if (generation !== watchProgressSyncGeneration) {
        return;
      }
      if (!didPush) {
        const retryDelayMs = getSyncBackoffRemainingMs();
        if (retryDelayMs > 0) {
          queueWatchProgressCloudSync(profileId, Math.max(5000, retryDelayMs));
        }
      }
    };
    void runPush();
  }, delayMs);
  watchProgressSyncTimers.set(profileKey, timerId);
}""",
        """async function runWatchProgressCloudPush(
  profileId = activeProfileId(),
  generation = watchProgressSyncGeneration
) {
  const profileKey = String(profileId || "1");
  const existingTimer = watchProgressSyncTimers.get(profileKey);
  if (existingTimer) {
    clearTimeout(existingTimer);
    watchProgressSyncTimers.delete(profileKey);
  }
  if (generation !== watchProgressSyncGeneration) {
    return false;
  }
  const inFlight = watchProgressSyncInFlightByProfile.get(profileKey);
  if (inFlight) {
    await inFlight.catch(() => false);
  }
  if (generation !== watchProgressSyncGeneration) {
    return false;
  }
  const pushPromise = import("../../core/profile/watchProgressSyncService.js")
    .then(({ WatchProgressSyncService }) => WatchProgressSyncService.push(profileId))
    .catch((error) => {
      console.warn("Watch progress cloud sync enqueue failed", error);
      return false;
    })
    .finally(() => {
      if (watchProgressSyncInFlightByProfile.get(profileKey) === pushPromise) {
        watchProgressSyncInFlightByProfile.delete(profileKey);
      }
    });
  watchProgressSyncInFlightByProfile.set(profileKey, pushPromise);
  const didPush = await pushPromise;
  if (generation !== watchProgressSyncGeneration) {
    return false;
  }
  if (!didPush) {
    const retryDelayMs = getSyncBackoffRemainingMs();
    if (retryDelayMs > 0) {
      queueWatchProgressCloudSync(profileId, Math.max(5000, retryDelayMs));
    }
  }
  return Boolean(didPush);
}

function queueWatchProgressCloudSync(
  profileId = activeProfileId(),
  delayMs = getWatchProgressSyncDebounceMs()
) {
  const profileKey = String(profileId || "1");
  const generation = watchProgressSyncGeneration;
  const existingTimer = watchProgressSyncTimers.get(profileKey);
  if (existingTimer) {
    clearTimeout(existingTimer);
  }
  const timerId = setTimeout(() => {
    if (generation !== watchProgressSyncGeneration) {
      return;
    }
    watchProgressSyncTimers.delete(profileKey);
    void runWatchProgressCloudPush(profileId, generation);
  }, delayMs);
  watchProgressSyncTimers.set(profileKey, timerId);
}""",
        "watchProgressRepository queueWatchProgressCloudSync",
    )
    source = _replace_exact(
        source,
        """function matchesProgressTarget(item = {}, contentId, videoId = null) {
  const wantedContentId = String(contentId || "").trim();
  if (!wantedContentId || !watchedItemsShareIdentity(item, { contentId: wantedContentId })) {
    return false;
  }
  if (videoId == null) {
    return true;
  }
  return String(item.videoId || "") === String(videoId);
}""",
        _EPISODE_VIDEO_HELPERS
        + """

// Cloud pull strips synthetic __nuvio_episode__: and self-referential movie
// videoId values to null, so match by episode numbers or canonical movie videoId.
function matchesProgressTarget(item = {}, contentId, videoId = null, target = null) {
  const wantedContentId = String(contentId || target?.contentId || "").trim();
  const identityTarget =
    target && typeof target === "object"
      ? { ...target, contentId: wantedContentId || target.contentId }
      : { contentId: wantedContentId };
  if (!wantedContentId || !watchedItemsShareIdentity(item, identityTarget)) {
    return false;
  }
  const targetEp = extractProgressEpisode(target || {}, videoId, wantedContentId);
  const itemEp = extractProgressEpisode(item, item?.videoId, item?.contentId);
  if (targetEp) {
    if (itemEp) {
      return itemEp.season === targetEp.season && itemEp.episode === targetEp.episode;
    }
    const wantedVid = normalizeVariantVideoId(videoId, wantedContentId);
    const itemVid = normalizeVariantVideoId(item?.videoId, item?.contentId || wantedContentId);
    return Boolean(wantedVid && itemVid && wantedVid === itemVid);
  }
  if (videoId == null) {
    return true;
  }
  const wantedVid = normalizeVariantVideoId(videoId, wantedContentId);
  const itemVid = normalizeVariantVideoId(item?.videoId, item?.contentId || wantedContentId);
  if (!wantedVid) {
    return (
      itemEp == null &&
      (!itemVid || watchedItemsShareIdentity({ contentId: itemVid }, identityTarget))
    );
  }
  return itemVid === wantedVid;
}""",
        "watchProgressRepository matchesProgressTarget",
    )
    source = _replace_exact(
        source,
        "  async getProgressByContentId(contentId) {",
        """  async flushCloudSync(profileId = activeProfileId()) {
    return runWatchProgressCloudPush(profileId, watchProgressSyncGeneration);
  }

  async markStoredProgressWatched(contentId, videoId = null, options = {}) {
    const pid = activeProfileId();
    const wantedContentId = String(contentId || options?.contentId || "").trim();
    if (!wantedContentId) {
      return false;
    }
    const opts = options && typeof options === "object" ? options : {};
    const rows = WatchProgressStore.listForProfile(pid).filter((item) =>
      matchesProgressTarget(item, wantedContentId, videoId, opts)
    );
    const now = Date.now();
    const parsedEp = extractProgressEpisode(opts, videoId, wantedContentId);
    const optionDuration = Number(opts.durationMs);
    const resolveDurationMs = (item = null) => {
      const stored = Number(item?.durationMs);
      if (Number.isFinite(stored) && stored >= 60000) {
        return Math.trunc(stored);
      }
      if (Number.isFinite(optionDuration) && optionDuration >= 60000) {
        return Math.trunc(optionDuration);
      }
      return 60000;
    };

    let updated = false;
    if (rows.length) {
      const completed = rows.map((item) => {
        const durationMs = resolveDurationMs(item);
        return {
          ...item,
          positionMs: durationMs,
          durationMs,
          progressPercent: 100,
          updatedAt: now
        };
      });
      WatchProgressStore.upsertMany(completed, pid);
      updated = true;
    } else if (opts.createIfMissing === true) {
      const contentType = String(opts.contentType || opts.type || "movie").trim() || "movie";
      if (!isSeriesType(contentType) || Boolean(parsedEp)) {
        const durationMs = resolveDurationMs(null);
        const rawVid = videoId != null ? String(videoId).trim() : "";
        const resolvedVideoId =
          rawVid && rawVid !== wantedContentId
            ? rawVid
            : parsedEp
              ? `${wantedContentId}:${parsedEp.season}:${parsedEp.episode}`
              : null;
        WatchProgressStore.upsert(
          {
            contentId: wantedContentId,
            contentType,
            videoId: resolvedVideoId,
            season: parsedEp ? parsedEp.season : null,
            episode: parsedEp ? parsedEp.episode : null,
            imdbId: opts.imdbId || null,
            tmdbId: opts.tmdbId || null,
            traktId: opts.traktId || null,
            title: opts.title || opts.name || wantedContentId,
            poster: opts.poster || null,
            background: opts.background || opts.backdrop || null,
            logo: opts.logo || null,
            positionMs: durationMs,
            durationMs,
            progressPercent: 100,
            source: selectedLocalProgressSource(),
            updatedAt: now
          },
          pid
        );
        updated = true;
      }
    }
    if (!updated) {
      return false;
    }
    invalidateContinueWatchingDisplaySnapshot();
    if (opts.flushStorage !== false) {
      globalThis.__nuvioFlushStorage?.();
    }
    if (opts.syncNow === true) {
      await this.flushCloudSync(pid);
    } else if (opts.syncRemote !== false) {
      const delayMs = Number(opts.syncDelayMs);
      queueWatchProgressCloudSync(pid, Number.isFinite(delayMs) && delayMs >= 0 ? delayMs : 250);
    }
    return true;
  }

  async getProgressByContentId(contentId) {""",
        "watchProgressRepository markStoredProgressWatched",
    )
    return _replace_exact(
        source,
        """  async removeProgress(contentId, videoId = null) {
    const pid = activeProfileId();
    if (selectedContinueWatchingSource() === WatchProgressSource.MDBLIST)
      await MdbListTracking.clearProgress(contentId, videoId);
    if (activeProfileId() !== pid) return;
    const removedItems = WatchProgressStore.listForProfile(pid).filter((item) =>
      matchesProgressTarget(item, contentId, videoId)
    );
    if (removedItems.length) {
      const remaining = WatchProgressStore.listForProfile(pid).filter(
        (item) => !matchesProgressTarget(item, contentId, videoId)
      );
      WatchProgressStore.replaceForProfile(pid, remaining);
    } else {
      WatchProgressStore.remove(contentId, videoId, pid);
    }
    await deleteWatchProgressFromCloud(removedItems, pid);
    // Android removeProgress() -> refreshNow(): force the next reconciliation.
    requestTraktRefreshAfterWatchAction();
    invalidateContinueWatchingDisplaySnapshot();
    queueWatchProgressCloudSync(pid);
  }""",
        """  async removeProgress(contentId, videoId = null, options = {}) {
    const pid = activeProfileId();
    const opts = options && typeof options === "object" ? options : {};
    if (selectedContinueWatchingSource() === WatchProgressSource.MDBLIST)
      await MdbListTracking.clearProgress(contentId, videoId);
    if (activeProfileId() !== pid) return;
    const removedItems = WatchProgressStore.listForProfile(pid).filter((item) =>
      matchesProgressTarget(item, contentId, videoId, opts)
    );
    if (removedItems.length) {
      const remaining = WatchProgressStore.listForProfile(pid).filter(
        (item) => !matchesProgressTarget(item, contentId, videoId, opts)
      );
      WatchProgressStore.replaceForProfile(pid, remaining);
    } else {
      WatchProgressStore.remove(contentId, videoId, pid);
    }
    await deleteWatchProgressFromCloud(removedItems, pid);
    // Android removeProgress() -> refreshNow(): force the next reconciliation.
    requestTraktRefreshAfterWatchAction();
    invalidateContinueWatchingDisplaySnapshot();
    globalThis.__nuvioFlushStorage?.();
    if (opts.syncNow === true) {
      await this.flushCloudSync(pid);
    } else if (opts.syncRemote !== false) {
      queueWatchProgressCloudSync(pid);
    }
  }""",
        "watchProgressRepository removeProgress",
    )


def patch_home_toggle_watched_source(source):
    """Complete stored progress and flush cloud sync for Continue Watching actions."""
    upstream_progress_stmt = """      await watchProgressRepository.saveProgress({
        contentId: normalized.contentId,
        imdbId: normalized.imdbId || null,
        tmdbId: normalized.tmdbId || null,
        traktId: normalized.traktId || null,
        contentType: normalized.type || "movie",
        videoId: normalized.videoId || null,
        season: normalized.season,
        episode: normalized.episode,
        positionMs: 100,
        durationMs: 100,
        updatedAt: Date.now()
      });"""
    polish_progress_stmt = (
        "      await watchProgressRepository.markStoredProgressWatched(normalized.contentId, normalized.videoId || null);"
    )
    if polish_progress_stmt in source:
        source = _replace_exact(source, polish_progress_stmt, upstream_progress_stmt, "homeScreenMethods-09 polish normalize")
    elif upstream_progress_stmt not in source:
        raise ValueError("Missing anchor in homeScreenMethods-09 progress update statement")

    source = _replace_exact(
        source,
        "  return {\n    async toggleContinueWatchingWatched(item) {",
        """  const flushContinueWatchingWatchedSync = async () => {
    globalThis.__nuvioFlushStorage?.();
    let timeoutId = null;
    try {
      await Promise.race([
        Promise.allSettled([
          watchedItemsRepository.flushCloudSync?.(),
          watchProgressRepository.flushCloudSync?.()
        ]),
        new Promise((resolve) => {
          timeoutId = setTimeout(resolve, 4000);
        })
      ]);
    } finally {
      if (timeoutId != null) {
        clearTimeout(timeoutId);
      }
      globalThis.__nuvioFlushStorage?.();
    }
  };

  const applyContinueWatchingMarkWatched = async (
    screen,
    normalized,
    { ensureWatchedItem = true } = {}
  ) => {
    const contentType = normalized.type || "movie";
    const targetSeason = normalized.season ?? null;
    const targetEpisode = normalized.episode ?? null;
    if (
      ensureWatchedItem &&
      (await watchedItemsRepository.mark(
        {
          contentId: normalized.contentId,
          contentType,
          season: targetSeason,
          episode: targetEpisode,
          videoId: normalized.videoId || null,
          imdbId: normalized.imdbId || null,
          tmdbId: normalized.tmdbId || null,
          traktId: normalized.traktId || null,
          title: normalized.title || normalized.contentId || "Untitled",
          watchedAt: Date.now()
        },
        { syncRemote: false }
      )) === false
    ) {
      return false;
    }
    await watchProgressRepository.markStoredProgressWatched(
      normalized.contentId,
      normalized.videoId || null,
      {
        contentType,
        season: targetSeason,
        episode: targetEpisode,
        imdbId: normalized.imdbId || null,
        tmdbId: normalized.tmdbId || null,
        traktId: normalized.traktId || null,
        title: normalized.title || normalized.contentId || "Untitled",
        poster: normalized.poster || null,
        background: normalized.backdrop || normalized.background || null,
        logo: normalized.logo || null,
        durationMs: normalized.durationMs,
        createIfMissing: true,
        syncRemote: false
      }
    );
    await flushContinueWatchingWatchedSync();
    screen.watchedItems = await watchedItemsRepository.getAll(2000).catch(() => screen.watchedItems);
    screen.watchedTitleIds = buildWatchedTitleIdSet(screen.watchedItems);
    screen.pruneContinueWatchingItem(normalized);
    if (isSeriesTypeForContinueWatching(contentType)) {
      void watchedSeriesReconciliationService
        .reconcile(normalized.contentId, contentType)
        .then(async (changed) => {
          if (!changed) {
            return;
          }
          await flushContinueWatchingWatchedSync();
          screen.watchedItems = await watchedItemsRepository
            .getAll(2000)
            .catch(() => screen.watchedItems);
          screen.watchedTitleIds = buildWatchedTitleIdSet(screen.watchedItems);
        })
        .catch(() => false);
    }
    return true;
  };

  return {
    async toggleContinueWatchingWatched(item) {""",
        "homeScreenMethods-09 return block",
    )
    return _replace_exact(
        source,
        """    async toggleContinueWatchingWatched(item) {
      const normalized = normalizeContinueWatchingItem(item);
      if (!normalized?.contentId) {
        return false;
      }
      if (this.isContinueWatchingItemWatched(normalized)) {
        if (
          (await watchedItemsRepository.unmark(normalized.contentId, {
            contentType: normalized.type || "movie",
            season: normalized.season ?? null,
            episode: normalized.episode ?? null,
            videoId: normalized.videoId || null,
            imdbId: normalized.imdbId || null,
            tmdbId: normalized.tmdbId || null,
            traktId: normalized.traktId || null,
            title: normalized.title || normalized.contentId || "Untitled"
          })) === false
        )
          return false;
        await watchProgressRepository.removeProgress(normalized.contentId, normalized.videoId || null);
        this.watchedItems = await watchedItemsRepository.getAll(2000).catch(() => this.watchedItems);
        this.watchedTitleIds = buildWatchedTitleIdSet(this.watchedItems);
        return true;
      }
      if (
        (await watchedItemsRepository.mark({
          contentId: normalized.contentId,
          contentType: normalized.type || "movie",
          season: normalized.season ?? null,
          episode: normalized.episode ?? null,
          videoId: normalized.videoId || null,
          imdbId: normalized.imdbId || null,
          tmdbId: normalized.tmdbId || null,
          traktId: normalized.traktId || null,
          title: normalized.title || normalized.contentId || "Untitled",
          watchedAt: Date.now()
        })) === false
      )
        return false;
      await watchProgressRepository.saveProgress({
        contentId: normalized.contentId,
        imdbId: normalized.imdbId || null,
        tmdbId: normalized.tmdbId || null,
        traktId: normalized.traktId || null,
        contentType: normalized.type || "movie",
        videoId: normalized.videoId || null,
        season: normalized.season,
        episode: normalized.episode,
        positionMs: 100,
        durationMs: 100,
        updatedAt: Date.now()
      });
      this.watchedItems = await watchedItemsRepository.getAll(2000).catch(() => this.watchedItems);
      this.watchedTitleIds = buildWatchedTitleIdSet(this.watchedItems);
      this.pruneContinueWatchingItem(normalized);
      return true;
    },
    async markContinueWatchingItemWatched(item) {
      const normalized = normalizeContinueWatchingItem(item);
      if (!normalized?.contentId) {
        return false;
      }
      if (this.isContinueWatchingItemWatched(normalized)) {
        // Already watched: the menu action only has to drop the row.
        this.pruneContinueWatchingItem(normalized);
        return true;
      }
      return this.toggleContinueWatchingWatched(normalized);
    },""",
        """    async toggleContinueWatchingWatched(item) {
      const normalized = normalizeContinueWatchingItem(item);
      if (!normalized?.contentId) {
        return false;
      }
      if (this.isContinueWatchingItemWatched(normalized)) {
        if (
          (await watchedItemsRepository.unmark(normalized.contentId, {
            contentType: normalized.type || "movie",
            season: normalized.season ?? null,
            episode: normalized.episode ?? null,
            videoId: normalized.videoId || null,
            imdbId: normalized.imdbId || null,
            tmdbId: normalized.tmdbId || null,
            traktId: normalized.traktId || null,
            title: normalized.title || normalized.contentId || "Untitled",
            syncRemote: false
          })) === false
        )
          return false;
        await watchProgressRepository.removeProgress(
          normalized.contentId,
          normalized.videoId || null,
          {
            season: normalized.season ?? null,
            episode: normalized.episode ?? null,
            imdbId: normalized.imdbId || null,
            tmdbId: normalized.tmdbId || null,
            traktId: normalized.traktId || null,
            syncRemote: false
          }
        );
        await flushContinueWatchingWatchedSync();
        this.watchedItems = await watchedItemsRepository.getAll(2000).catch(() => this.watchedItems);
        this.watchedTitleIds = buildWatchedTitleIdSet(this.watchedItems);
        return true;
      }
      return applyContinueWatchingMarkWatched(this, normalized, { ensureWatchedItem: true });
    },
    async markContinueWatchingItemWatched(item) {
      const normalized = normalizeContinueWatchingItem(item);
      if (!normalized?.contentId) {
        return false;
      }
      return applyContinueWatchingMarkWatched(this, normalized, {
        ensureWatchedItem: !this.isContinueWatchingItemWatched(normalized)
      });
    },""",
        "homeScreenMethods-09 toggle/mark Continue Watching",
    )


def patch_frontend(nuvio):
    """Apply Continue Watching and Nuvio Sync fixes to the extracted Nuvio UI tree."""
    nuvio = Path(nuvio)
    targets = (
        (
            nuvio / "js/ui/screens/home/homeScreenHelpers-09-normalize-continue-watching-item.js",
            patch_normalize_continue_watching_source,
        ),
        (
            nuvio / "js/ui/screens/home/homeScreenMethods-06-get-hero-source-from-focus-state.js",
            patch_home_hero_watched_source,
        ),
        (
            nuvio / "js/data/repository/watchedItemsRepository.js",
            patch_watched_items_repository_source,
        ),
        (
            nuvio / "js/data/repository/watchProgressRepository.js",
            patch_watch_progress_repository_source,
        ),
        (
            nuvio / "js/ui/screens/home/homeScreenMethods-09-toggle-continue-watching-watched.js",
            patch_home_toggle_watched_source,
        ),
    )
    for path, transform in targets:
        path.write_text(transform(path.read_text()))
