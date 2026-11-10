/* Included in evo_webui.c after progress/skip/next policy definitions. */
#include "nuvio_presentation.h"
#include "cJSON.h"
#include <time.h>

static nuvio_presentation_t s_pending_presentation, s_h_presentation, s_play_presentation, s_presentation;
static char s_presentation_session[64];
static uint64_t s_presentation_last, s_presentation_running_ms, s_presentation_paused_ms;
static int s_presentation_running, s_presentation_paused, s_recommendation_index, s_recommendation_dismissed;

static int presentation_bool(const cJSON *root, const char *key)
{
    return cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(root, key));
}

static double presentation_number(const cJSON *root, const char *key, double fallback, double low, double high)
{
    const cJSON *value = cJSON_GetObjectItemCaseSensitive(root, key);
    return cJSON_IsNumber(value) && isfinite(value->valuedouble) &&
        value->valuedouble >= low && value->valuedouble <= high ? value->valuedouble : fallback;
}

static void presentation_text(const cJSON *root, const char *key, char *out, size_t cap)
{
    const cJSON *value = cJSON_GetObjectItemCaseSensitive(root, key);
    if (!cJSON_IsString(value) || !value->valuestring) return;
    const char *text = value->valuestring;
    size_t len = strlen(text);
    if (len >= cap) {
        len = cap - 1;
        while (len && ((unsigned char)text[len] & 0xc0) == 0x80) --len;
    }
    memcpy(out, text, len);
    out[len] = 0;
}

static int presentation_decode(const char *body, size_t size)
{
    cJSON *root = cJSON_ParseWithLength(body, size + 1);
    if (!cJSON_IsObject(root)) { cJSON_Delete(root); return 0; }
    char session[64] = "";
    presentation_text(root, "session", session, sizeof session);
    const cJSON *raw_session = cJSON_GetObjectItemCaseSensitive(root, "session");
    if (!session[0] || !cJSON_IsString(raw_session) || strlen(raw_session->valuestring) >= sizeof session ||
        strspn(session, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-") != strlen(session)) {
        cJSON_Delete(root);
        return 0;
    }
    nuvio_presentation_t p = {0};
    p.active = 1;
    p.loading = presentation_bool(root, "loading");
    p.loading_detail = presentation_bool(root, "loadingDetail");
    p.pause = presentation_bool(root, "pause");
    p.clock = presentation_bool(root, "clock");
    p.utc_offset_minutes = (int)presentation_number(root, "utcOffsetMinutes", 0, -840, 840);
    p.pause_delay_ms = (int)presentation_number(root, "pauseDelayMs", 3000, 0, 60000);
    p.movie = presentation_bool(root, "movie");
    p.recommendation_enabled = presentation_bool(root, "recommendationEnabled");
    p.threshold_minutes = !p.movie && presentation_bool(root, "thresholdMinutes");
    p.threshold = presentation_number(root, "threshold", p.threshold_minutes ? 120 : p.movie ? 0.9 : 0.99,
        p.threshold_minutes ? 0 : p.movie ? 0.8 : 0.97, p.threshold_minutes ? 210 : 1);
    p.episode_threshold_minutes = presentation_bool(root, "episodeThresholdMinutes");
    p.episode_threshold = presentation_number(root, "episodeThreshold", p.episode_threshold_minutes ? 120 : 0.99,
        p.episode_threshold_minutes ? 0 : 0.97, p.episode_threshold_minutes ? 210 : 1);
    p.credits_start = presentation_number(root, "creditsStart", 0, 0, 864000);
    p.credits_end = presentation_number(root, "creditsEnd", 0, 0, 864000);
    p.post_credits_end = presentation_number(root, "postCreditsEnd", 0, 0, 864000);
    presentation_text(root, "description", p.description, sizeof p.description);
    presentation_text(root, "parental", p.parental, sizeof p.parental);
    const cJSON *recommendations = cJSON_GetObjectItemCaseSensitive(root, "recommendations");
    if (cJSON_IsArray(recommendations) && p.recommendation_enabled) {
        int count = cJSON_GetArraySize(recommendations);
        if (count > 3) count = 3;
        for (int i = 0; i < count; ++i) {
            const cJSON *item = cJSON_GetArrayItem(recommendations, i);
            presentation_text(item, "title", p.recommendations[i].title, sizeof p.recommendations[i].title);
            presentation_text(item, "description", p.recommendations[i].description, sizeof p.recommendations[i].description);
            if (!p.recommendations[i].title[0]) break;
            ++p.recommendation_count;
        }
    }
    cJSON_Delete(root);
    pthread_mutex_lock(&s_mx);
    s_pending_presentation = p;
    snprintf(s_presentation_session, sizeof s_presentation_session, "%s", session);
    pthread_mutex_unlock(&s_mx);
    return 1;
}

static void serve_presentation(int fd, const char *method, char *req, size_t got, size_t hl)
{
    if (strcmp(method, "POST")) { respond(fd, "405 Method Not Allowed", "text/plain", "", 0); return; }
    char length[32];
    long size = header_value(req, hl, "Content-Length", length, sizeof length) ? parse_long(length) : -1;
    if (size < 2 || size > 8192) { respond(fd, "413 Payload Too Large", "text/plain", "", 0); return; }
    char body[8193];
    size_t have = got - hl;
    if (have > (size_t)size) have = (size_t)size;
    memcpy(body, req + hl, have);
    while (have < (size_t)size) {
        ssize_t n = recv(fd, body + have, (size_t)size - have, 0);
        if (n <= 0) break;
        have += (size_t)n;
    }
    body[have] = 0;
    int ok = have == (size_t)size && presentation_decode(body, have);
    respond(fd, ok ? "204 No Content" : "400 Bad Request", "text/plain", "", 0);
}

static void presentation_handoff(const char *session)
{
    memset(&s_h_presentation, 0, sizeof s_h_presentation);
    if (session[0] && !strcmp(session, s_presentation_session)) s_h_presentation = s_pending_presentation;
    s_presentation_session[0] = 0;
    memset(&s_pending_presentation, 0, sizeof s_pending_presentation);
}

static void presentation_begin(void)
{
    s_presentation = s_play_presentation;
    s_presentation_last = s_presentation_running_ms = s_presentation_paused_ms = 0;
    s_presentation_running = s_presentation_paused = s_recommendation_dismissed = 0;
    s_recommendation_index = 1;
}

const nuvio_presentation_t *evo_webui_presentation(void) { return &s_presentation; }

void evo_webui_presentation_started(void)
{
    pthread_mutex_lock(&s_mx);
    if (s_progress_session[0] && !s_progress_finished) s_progress_played = 1;
    pthread_mutex_unlock(&s_mx);
}

void evo_webui_recommendation_selected(int index)
{
    if (index < 1 || index > s_presentation.recommendation_count) return;
    pthread_mutex_lock(&s_mx);
    s_progress_recommendation = index;
    s_progress_next_episode = s_progress_return_detail = 0;
    pthread_mutex_unlock(&s_mx);
}

/* Matches the browser's known-scene rule. Never show recommendations over a
 * known post-credit scene just because a percentage threshold was reached. */
static double presentation_recommendation_start(double duration)
{
    const nuvio_presentation_t *p = &s_presentation;
    double remaining = p->threshold_minutes ? p->threshold : (1.0 - p->threshold) * duration;
    double start = duration - remaining;
    if (p->movie) {
        if (p->post_credits_end > 0 && p->post_credits_end <= duration + 1)
            return fmin(duration, p->post_credits_end);
        if (p->credits_end > p->credits_start && p->credits_end <= duration + 1) {
            double user_remaining = p->episode_threshold_minutes ? p->episode_threshold :
                (1.0 - p->episode_threshold) * duration;
            return duration - p->credits_end > user_remaining
                ? fmax(p->credits_end, duration - user_remaining) : p->credits_start;
        }
    } else {
        double first = duration, last = 0;
        for (int i = 0; i < 4; ++i) {
            if (s_skip[i].type != 2 || s_skip[i].end > duration) continue;
            first = fmin(first, s_skip[i].start);
            last = fmax(last, s_skip[i].end);
        }
        if (last > 0 && duration - last <= remaining) start = first;
    }
    return start;
}

nuvio_presentation_view_t evo_webui_presentation_update(double position, double duration,
    uint64_t now, int ready, int paused, int blocked, int ended)
{
    nuvio_presentation_view_t view = {0};
    uint64_t delta = now >= s_presentation_last ? now - s_presentation_last : 0;
    if (s_presentation_running && ready && !paused) s_presentation_running_ms += delta;
    if (s_presentation_paused && paused && ready) s_presentation_paused_ms += delta;
    else s_presentation_paused_ms = 0;
    s_presentation_last = now;
    s_presentation_running = ready && !paused;
    s_presentation_paused = ready && paused;
    const nuvio_presentation_t *p = &s_presentation;
    if (!p->active || !ready) return view;
    evo_webui_presentation_started();
    if (blocked) return view;
    view.parental = p->parental[0] && !paused && s_presentation_running_ms < 8000;
    view.pause = p->pause && paused && !ended && s_presentation_paused_ms >= (uint64_t)p->pause_delay_ms;
    view.recommendation = p->recommendation_enabled && p->recommendation_count &&
        !s_recommendation_dismissed && !paused && !view.parental && isfinite(position) && position >= 0 &&
        isfinite(duration) && duration > 120.999 && position >= presentation_recommendation_start(duration)
        ? s_recommendation_index : 0;
    return view;
}

void evo_webui_presentation_action(int action)
{
    if (action == 1 && s_presentation.recommendation_count)
        s_recommendation_index = s_recommendation_index % s_presentation.recommendation_count + 1;
    if (action == 2) s_recommendation_dismissed = 1;
}

void evo_webui_presentation_clock(double position, double duration, char *out, size_t size)
{
    out[0] = 0;
    if (!s_presentation.active || !s_presentation.clock) return;
    time_t now = time(NULL) + s_presentation.utc_offset_minutes * 60;
    struct tm clock;
    char current[16], end[16];
    if (!gmtime_r(&now, &clock) || !strftime(current, sizeof current, "%H:%M", &clock)) return;
    if (!isfinite(position) || !isfinite(duration) || duration <= position || position < 0) {
        snprintf(out, size, "%s", current);
        return;
    }
    now += (time_t)(duration - position);
    if (!gmtime_r(&now, &clock) || !strftime(end, sizeof end, "%H:%M", &clock)) return;
    snprintf(out, size, "%s   Ends %s", current, end);
}
