/* Included in evo_webui.c. Pending handoffs are copied under s_mx, then owned
 * by the playback thread. No timestamp is persisted between title sessions. */
typedef struct { double start, end; int type, automatic; } nuvio_skip_segment;
static nuvio_skip_segment s_h_skip[4], s_play_skip[4], s_skip[4];
static int s_skip_suppressed = -1;
static uint64_t s_skip_retry_after;

static void playback_skip_parse(const char *path)
{
    char value[256];
    query_param(path, "skip", value, sizeof value);
    memset(s_h_skip, 0, sizeof s_h_skip);
    const char *p = value;
    for (int i = 0; *p && i < 4; ++i) {
        /* Uppercase marks only this interval for automatic skipping. */
        int type = (*p == 'i' || *p == 'I') ? 1 : (*p == 'c' || *p == 'C') ? 2 :
                   (*p == 'r' || *p == 'R') ? 3 : 0;
        int automatic = *p == 'I' || *p == 'C' || *p == 'R';
        if (!type || p[1] != ',') goto invalid;
        char *next;
        errno = 0;
        double start = strtod(p + 2, &next);
        if (errno || next == p + 2 || *next != ',') goto invalid;
        p = next + 1;
        errno = 0;
        double end = strtod(p, &next);
        if (errno || next == p || *next != ';' || !isfinite(start) ||
            !isfinite(end) || start < 0.0 || end <= start) goto invalid;
        s_h_skip[i] = (nuvio_skip_segment){start, end, type, automatic};
        p = next + 1;
    }
    if (!*p) return;
invalid:
    /* Reject truncated and malformed payloads, not just their last record. */
    memset(s_h_skip, 0, sizeof s_h_skip);
}

/* consume: 0 inspect, 1 manual action, 2 automatic action. */
int evo_webui_skip_interval(double position, double duration, uint64_t now,
                           int consume, double *target)
{
    if (!isfinite(position) || !isfinite(duration) || position < 0.0 || duration <= 0.0)
        return 0;
    for (int i = 0; i < 4; ++i) {
        const nuvio_skip_segment *segment = &s_skip[i];
        if (!segment->type || segment->end > duration ||
            position < segment->start || position >= segment->end - 0.5) continue;
        if (s_skip_suppressed == i && now < s_skip_retry_after) return 0;
        if (consume == 2 && !segment->automatic) return 0;
        if (consume) {
            s_skip_suppressed = i;
            s_skip_retry_after = now + 5000;
        }
        *target = segment->end;
        return segment->type;
    }
    return 0;
}

/* Presentation only: reaching zero dims the prompt, never consumes a skip. */
int evo_webui_skip_countdown(double target, uint64_t now, int running)
{
    static double previous_target;
    static uint64_t elapsed, last;
    static int was_running;
    if (target <= 0.0 || target != previous_target) {
        previous_target = target;
        elapsed = 0;
        was_running = 0;
    } else if (was_running && now >= last) {
        elapsed += now - last;
        if (elapsed > 10000) elapsed = 10000;
    }
    last = now;
    was_running = running;
    return target <= 0.0 ? 0 : (int)((10000 - elapsed + 999) / 1000);
}
