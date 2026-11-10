/* Session-bound browser candidates, never written to settings or diagnostics. */
#include "evo_online_subs.h"

typedef struct {
    char session[64];
    int count;
    evo_osub_t entries[EVO_OSUB_MAX];
} nuvio_subtitles_t;
static nuvio_subtitles_t s_pending_subtitles, s_h_subtitles, s_play_subtitles;

static int subtitle_field(const cJSON *object, const char *name, char *out, size_t cap)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(object, name);
    if (!cJSON_IsString(v) || !v->valuestring || strlen(v->valuestring) >= cap) return 0;
    for (const unsigned char *p = (const unsigned char *)v->valuestring; *p; ++p)
        if (*p < 32 || *p == 127) return 0;
    strcpy(out, v->valuestring);
    return 1;
}

static int subtitles_decode(const char *body, size_t size)
{
    cJSON *root = cJSON_ParseWithLength(body, size + 1);
    nuvio_subtitles_t *p = calloc(1, sizeof *p);
    int ok = p && cJSON_IsObject(root) && subtitle_field(root, "session", p->session, sizeof p->session);
    if (ok) ok = p->session[0] && strspn(p->session,
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-") == strlen(p->session);
    const cJSON *array = cJSON_GetObjectItemCaseSensitive(root, "subtitles");
    if (ok) ok = cJSON_IsArray(array) && cJSON_GetArraySize(array) <= EVO_OSUB_MAX;
    for (int i = 0; ok && i < cJSON_GetArraySize(array); ++i) {
        const cJSON *item = cJSON_GetArrayItem(array, i);
        evo_osub_t *s = &p->entries[p->count];
        ok = subtitle_field(item, "url", s->url, sizeof s->url) &&
             subtitle_field(item, "lang", s->lang_tag, sizeof s->lang_tag) &&
             subtitle_field(item, "source", s->source, sizeof s->source);
        if (ok) ok = (!strncmp(s->url, "http://", 7) || !strncmp(s->url, "https://", 8)) &&
                      !strchr(s->url, ' ');
        if (ok) ++p->count;
    }
    if (ok) {
        pthread_mutex_lock(&s_mx);
        s_pending_subtitles = *p;
        pthread_mutex_unlock(&s_mx);
    }
    free(p);
    cJSON_Delete(root);
    return ok;
}

static void serve_subtitles(int fd, const char *method, char *req, size_t got, size_t hl)
{
    if (strcmp(method, "POST")) { respond(fd, "405 Method Not Allowed", "text/plain", "", 0); return; }
    char length[32];
    long size = header_value(req, hl, "Content-Length", length, sizeof length) ? parse_long(length) : -1;
    if (size < 2 || size > 49152) { respond(fd, "413 Payload Too Large", "text/plain", "", 0); return; }
    char *body = malloc((size_t)size + 1);
    if (!body) { respond(fd, "503 Service Unavailable", "text/plain", "", 0); return; }
    size_t have = got - hl;
    if (have > (size_t)size) have = (size_t)size;
    memcpy(body, req + hl, have);
    while (have < (size_t)size) {
        ssize_t n = recv(fd, body + have, (size_t)size - have, 0);
        if (n <= 0) break;
        have += (size_t)n;
    }
    body[have] = 0;
    int ok = have == (size_t)size && subtitles_decode(body, have);
    free(body);
    respond(fd, ok ? "204 No Content" : "400 Bad Request", "text/plain", "", 0);
}

/* Called with the handoff mutex held; only a matching session receives data. */
static void subtitles_handoff(const char *session)
{
    memset(&s_h_subtitles, 0, sizeof s_h_subtitles);
    if (session[0] && !strcmp(session, s_pending_subtitles.session)) s_h_subtitles = s_pending_subtitles;
    memset(&s_pending_subtitles, 0, sizeof s_pending_subtitles);
}

void evo_webui_import_subtitles(char *key, size_t cap)
{
    pthread_mutex_lock(&s_mx);
    snprintf(key, cap, "web:%s", s_play_subtitles.session);
    evo_osubs_begin(key);
    for (int i = 0; i < s_play_subtitles.count; ++i) {
        const evo_osub_t *s = &s_play_subtitles.entries[i];
        evo_osubs_add(key, s->url, s->lang_tag, s->source);
    }
    memset(&s_play_subtitles, 0, sizeof s_play_subtitles);
    pthread_mutex_unlock(&s_mx);
}
