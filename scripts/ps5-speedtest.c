/* Included in evo_webui.c. Explicit, single-connection TorBox download test.
 * No stream headers, account data, persistent files or browser-side transfers. */
#include "cJSON.h"
#include <libavformat/avio.h>
#include <libavutil/dict.h>
#include <libavutil/error.h>
#include <libavutil/time.h>

#define SPEEDTEST_BYTES (100 * 1024 * 1024)
#define SPEEDTEST_DOWNLOAD_US 15000000
#define SPEEDTEST_TOTAL_US 25000000

static pthread_mutex_t s_speedtest_mx = PTHREAD_MUTEX_INITIALIZER;
static int s_speedtest_active, s_speedtest_cancel, s_speedtest_blocked = 1;
static const char *s_speedtest_state = "idle", *s_speedtest_error = "";
static char s_speedtest_region[16];
static int64_t s_speedtest_bytes, s_speedtest_started, s_speedtest_elapsed;

/* Only this worker touches its deadline. Cancellation crosses threads under
 * the mutex. FFmpeg polls during connect/read; synchronous DNS can take longer. */
static int speedtest_interrupt(void *opaque)
{
    pthread_mutex_lock(&s_speedtest_mx);
    int cancel = s_speedtest_cancel;
    pthread_mutex_unlock(&s_speedtest_mx);
    return cancel || av_gettime_relative() >= *(int64_t *)opaque;
}

static int speedtest_open(AVIOContext **io, const char *url, int64_t *deadline)
{
    AVDictionary *options = NULL;
    /* Do not use evo_stream_io_apply_network_options: it adds private headers.
     * These are declared options in the pinned FFmpeg HTTP/TCP protocols. */
    av_dict_set(&options, "protocol_whitelist", "https,tls,tcp", 0);
    av_dict_set(&options, "rw_timeout", "5000000", 0);
    av_dict_set(&options, "timeout", "5000000", 0);
    av_dict_set(&options, "seekable", "0", 0);
    av_dict_set(&options, "reconnect", "0", 0);
    av_dict_set(&options, "reconnect_at_eof", "0", 0);
    av_dict_set(&options, "user_agent", "Nuvio-Pro-speedtest", 0);
    AVIOInterruptCB interrupt = {speedtest_interrupt, deadline};
    int rc = avio_open2(io, url, AVIO_FLAG_READ, &interrupt, &options);
    av_dict_free(&options);
    return rc;
}

/* Accept only the public short-test file on TorBox CDN hostnames. Neither the
 * browser nor an addon can supply a URL. Reject credentials, ports and queries. */
static int speedtest_url(const char *url)
{
    if (strncmp(url, "https://", 8)) return 0;
    const char *host = url + 8, *path = strchr(host, '/');
    if (!path || strcmp(path, "/dld/100MB.bin")) return 0;
    size_t size = (size_t)(path - host);
    if (!size || size > 127 || strspn(host, "abcdefghijklmnopqrstuvwxyz0123456789-.") != size) return 0;
    static const char *suffixes[] = {".tb-cdn.io", ".tb-cdn.st", ".tb-cdn.cx",
        ".tb-cdn.earth", ".tb-cdn.pw", ".tb-cdn.to"};
    for (size_t i = 0; i < sizeof suffixes / sizeof *suffixes; ++i) {
        size_t len = strlen(suffixes[i]);
        if (size > len && !memcmp(path - len, suffixes[i], len)) return 1;
    }
    return 0;
}

static int speedtest_discover(char *url, size_t cap, int64_t *deadline)
{
    AVIOContext *io = NULL;
    if (speedtest_open(&io, "https://api.torbox.app/v1/api/speedtest?test_length=short", deadline) < 0) {
        avio_closep(&io);
        return 0;
    }
    char body[16385];
    int used = 0, rc = 0;
    while (used < (int)sizeof body - 1 && !speedtest_interrupt(deadline)) {
        rc = avio_read(io, (unsigned char *)body + used, (int)sizeof body - 1 - used);
        if (rc <= 0) break;
        used += rc;
    }
    avio_closep(&io);
    if (rc != AVERROR_EOF || used == (int)sizeof body - 1 || speedtest_interrupt(deadline)) return 0;
    body[used] = 0;
    cJSON *root = cJSON_ParseWithLength(body, (size_t)used + 1);
    int found = 0;
    if (cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(root, "success"))) {
        const cJSON *item;
        cJSON_ArrayForEach(item, cJSON_GetObjectItemCaseSensitive(root, "data")) {
            if (!cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(item, "closest"))) continue;
            const cJSON *link = cJSON_GetObjectItemCaseSensitive(item, "url");
            const cJSON *region = cJSON_GetObjectItemCaseSensitive(item, "region");
            if (cJSON_IsString(link) && strlen(link->valuestring) < cap && speedtest_url(link->valuestring) &&
                cJSON_IsString(region) && region->valuestring[0] && strlen(region->valuestring) < sizeof s_speedtest_region &&
                strspn(region->valuestring, "abcdefghijklmnopqrstuvwxyz0123456789-") == strlen(region->valuestring)) {
                snprintf(url, cap, "%s", link->valuestring);
                pthread_mutex_lock(&s_speedtest_mx);
                snprintf(s_speedtest_region, sizeof s_speedtest_region, "%s", region->valuestring);
                pthread_mutex_unlock(&s_speedtest_mx);
                found = 1;
            }
            break;
        }
    }
    cJSON_Delete(root);
    return found;
}

static void *speedtest_worker(void *unused)
{
    (void)unused;
    int64_t deadline = av_gettime_relative() + SPEEDTEST_TOTAL_US;
    char url[256];
    const char *error = "Could not find a TorBox test server.";
    AVIOContext *io = NULL;
    if (speedtest_discover(url, sizeof url, &deadline) && !speedtest_interrupt(&deadline)) {
        int64_t start = av_gettime_relative();
        int64_t download_deadline = start + SPEEDTEST_DOWNLOAD_US;
        if (download_deadline < deadline) deadline = download_deadline;
        pthread_mutex_lock(&s_speedtest_mx);
        s_speedtest_started = start;
        s_speedtest_state = "downloading";
        pthread_mutex_unlock(&s_speedtest_mx);
        error = "Could not download the TorBox test file.";
        if (speedtest_open(&io, url, &deadline) >= 0 && avio_size(io) == SPEEDTEST_BYTES) {
            unsigned char buffer[64 * 1024];
            int64_t bytes = 0;
            error = "The TorBox download stopped before the test finished.";
            while (bytes < SPEEDTEST_BYTES && !speedtest_interrupt(&deadline)) {
                int size = SPEEDTEST_BYTES - bytes < (int64_t)sizeof buffer ?
                    (int)(SPEEDTEST_BYTES - bytes) : (int)sizeof buffer;
                int rc = avio_read(io, buffer, size);
                if (rc <= 0) break;
                bytes += rc;
                pthread_mutex_lock(&s_speedtest_mx);
                s_speedtest_bytes = bytes;
                pthread_mutex_unlock(&s_speedtest_mx);
            }
            /* A timed sample is valid, but an early EOF or network error is
             * not. Never turn a failed partial transfer into a success. */
            if (bytes && (bytes == SPEEDTEST_BYTES || av_gettime_relative() >= deadline)) error = "";
        }
    }
    avio_closep(&io);
    pthread_mutex_lock(&s_speedtest_mx);
    s_speedtest_elapsed = s_speedtest_started ? av_gettime_relative() - s_speedtest_started : 0;
    s_speedtest_state = s_speedtest_cancel ? "cancelled" : error[0] ? "error" : "completed";
    s_speedtest_error = s_speedtest_cancel ? "" : error;
    s_speedtest_active = 0;
    pthread_mutex_unlock(&s_speedtest_mx);
    return NULL;
}

static void speedtest_suspend(void)
{
    pthread_mutex_lock(&s_speedtest_mx);
    s_speedtest_blocked = 1;
    s_speedtest_cancel = 1;
    pthread_mutex_unlock(&s_speedtest_mx);
}

static void speedtest_resume(void)
{
    pthread_mutex_lock(&s_speedtest_mx);
    s_speedtest_blocked = 0;
    pthread_mutex_unlock(&s_speedtest_mx);
}

/* Main-thread handoff waits without blocking a frame or freeing worker state. */
static int speedtest_quiet(void)
{
    speedtest_suspend();
    pthread_mutex_lock(&s_speedtest_mx);
    int quiet = !s_speedtest_active;
    pthread_mutex_unlock(&s_speedtest_mx);
    return quiet;
}

static void serve_speedtest(int fd, const char *method, const char *path)
{
    int start = !strcmp(path, "/evo/speedtest/start");
    int cancel = !strcmp(path, "/evo/speedtest/cancel");
    const char *status = "200 OK", *request_error = NULL;
    if (!start && !cancel && strcmp(path, "/evo/speedtest/status")) {
        respond(fd, "404 Not Found", "application/json", "{}", 2);
        return;
    }
    if (strcmp(method, start || cancel ? "POST" : "GET")) {
        respond(fd, "405 Method Not Allowed", "application/json", "{}", 2);
        return;
    }
    pthread_mutex_lock(&s_speedtest_mx);
    if (cancel) s_speedtest_cancel = 1;
    if (start && (s_speedtest_active || s_speedtest_blocked)) {
        status = "409 Conflict";
        request_error = s_speedtest_active ? "A speed test is already running." : "Return to browsing before testing.";
    } else if (start) {
        s_speedtest_cancel = 0;
        s_speedtest_active = 1;
        s_speedtest_state = "discovering";
        s_speedtest_region[0] = 0;
        s_speedtest_error = "";
        s_speedtest_bytes = s_speedtest_started = s_speedtest_elapsed = 0;
        pthread_t thread;
        pthread_attr_t attr;
        pthread_attr_init(&attr);
        pthread_attr_setstacksize(&attr, 256 * 1024);
        pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);
        int rc = pthread_create(&thread, &attr, speedtest_worker, NULL);
        pthread_attr_destroy(&attr);
        if (rc) {
            s_speedtest_active = 0;
            s_speedtest_state = "error";
            s_speedtest_error = "Could not start the speed test.";
            status = "503 Service Unavailable";
        }
    }
    int64_t elapsed = s_speedtest_active && s_speedtest_started ?
        av_gettime_relative() - s_speedtest_started : s_speedtest_elapsed;
    double mbps = elapsed > 0 ? s_speedtest_bytes * 8.0 / elapsed : 0;
    char body[512];
    int size = snprintf(body, sizeof body,
        "{\"state\":\"%s\",\"region\":\"%s\",\"bytes\":%lld,\"elapsedMs\":%.0f,\"mbps\":%.3f,\"error\":\"%s\"}",
        s_speedtest_state, s_speedtest_region, (long long)s_speedtest_bytes, elapsed / 1000.0, mbps,
        request_error ? request_error : s_speedtest_error);
    pthread_mutex_unlock(&s_speedtest_mx);
    respond(fd, status, "application/json", body, (size_t)size);
}
