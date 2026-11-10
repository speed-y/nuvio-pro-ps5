/* Included after ps5-skip.c. Native code receives policy, never episode URLs.
 * Episode identity and stream selection remain in the saved Nuvio context. */
typedef struct { int enabled, automatic, seconds, minutes; double threshold; } nuvio_next_policy;
static nuvio_next_policy s_h_next, s_play_next, s_next;
static int s_next_cancelled, s_next_launch, s_next_was_running;
static int s_still_started;
static uint64_t s_next_elapsed, s_next_last, s_still_start;

static void playback_next_parse(const char *path)
{
    char value[96], mode;
    int automatic, seconds, end = 0;
    double threshold;
    query_param(path, "next", value, sizeof value);
    memset(&s_h_next, 0, sizeof s_h_next);
    if (sscanf(value, "%d,%d,%c,%lf%n", &automatic, &seconds, &mode, &threshold, &end) != 4 ||
        value[end] || automatic < 0 || automatic > 2 || (seconds != 0 && seconds != 3) ||
        !isfinite(threshold) || (mode != 'p' && mode != 's') ||
        (mode == 'p' && (threshold < 0.97 || threshold > 1.0)) ||
        (mode == 's' && (threshold < 0.0 || threshold > 210.0))) return;
    s_h_next = (nuvio_next_policy){1, automatic, seconds, mode == 's', threshold};
}

static void playback_next_begin(void)
{
    s_next = s_play_next;
    s_next_cancelled = s_next_launch = s_next_was_running = 0;
    s_still_started = 0;
    s_next_elapsed = s_next_last = 0;
}

/* 0 hidden, -1 manual, 1..3 countdown, -2 transition, -3 exit to details,
 * 1001..1060 Still Watching countdown (always wall time while paused).
 * Actions: 0 update, 1 play now, 2 keep watching. Only playback owns this state. */
int evo_webui_next_episode(double position, double duration, uint64_t now,
                          int running, int visible, int action)
{
    int was_running = s_next_was_running;
    uint64_t previous = s_next_last;
    s_next_last = now;
    s_next_was_running = 0;
    if (!s_next.enabled || s_next_cancelled || !visible ||
        !isfinite(position) || position < 0.0 || !isfinite(duration) || duration <= 120.999) return 0;
    if (s_next_launch) return -2;
    double remaining = s_next.minutes ? s_next.threshold : (1.0 - s_next.threshold) * duration;
    double start = duration - remaining, first = duration, last = 0.0;
    for (int i = 0; i < 4; ++i) {
        if (s_skip[i].type != 2 || s_skip[i].end > duration) continue;
        if (s_skip[i].start < first) first = s_skip[i].start;
        if (s_skip[i].end > last) last = s_skip[i].end;
    }
    /* Match Nuvio's threshold rule without cutting a known post-outro gap. */
    if (last > 0.0 && duration - last <= remaining) start = first;
    if (position < start) {
        s_next_elapsed = 0;
        return 0;
    }
    if (s_next.automatic == 2) {
        if (!s_still_started) { s_still_start = now; s_still_started = 1; }
        uint64_t elapsed = now >= s_still_start ? now - s_still_start : 0;
        if (action == 2 || elapsed >= 60000) {
            s_next_cancelled = 1;
            pthread_mutex_lock(&s_mx);
            s_progress_return_detail = 1;
            s_progress_next_episode = 0;
            pthread_mutex_unlock(&s_mx);
            return -3;
        }
        if (action != 1) return 1000 + (int)((60000 - elapsed + 999) / 1000);
    }
    if (action == 2) {
        s_next_cancelled = 1;
        return 0;
    }
    s_next_was_running = running;
    if (was_running && now >= previous) s_next_elapsed += now - previous;
    if (action == 1 || (s_next.automatic && running &&
        s_next_elapsed >= (uint64_t)s_next.seconds * 1000)) {
        s_next_launch = 1;
        pthread_mutex_lock(&s_mx);
        s_progress_next_episode = action == 1 ? 1 : 2;
        pthread_mutex_unlock(&s_mx);
        return -2;
    }
    if (!s_next.automatic) return -1;
    if (s_next_elapsed >= (uint64_t)s_next.seconds * 1000) return s_next.seconds ? 1 : -1;
    return (int)(((uint64_t)s_next.seconds * 1000 - s_next_elapsed + 999) / 1000);
}
