/* Included in evo_webui.c. Identity stays in the saved browser snapshot; the
 * native side only holds an opaque session and measured playback times. */
static char s_h_progress_session[64], s_play_progress_session[64];
static char s_progress_session[64];
static double s_progress_position, s_progress_duration;
static int s_progress_finished;
static int s_progress_next_episode; /* Live return only, never a recovery checkpoint. */
static int s_progress_return_detail; /* Explicit Circle action, not crash recovery. */
static int s_progress_played, s_progress_recommendation;
static uint64_t s_progress_revision;
static pthread_mutex_t s_progress_disk_mx = PTHREAD_MUTEX_INITIALIZER;

/* Two checksummed slots retain the preceding checkpoint if a write tears.
 * Never modify the browser's profile/context snapshot while it is closed. */
static uint32_t playback_progress_checksum(const char *data, size_t size)
{
    uint32_t hash = 2166136261u;
    for (size_t i = 0; i < size; ++i) hash = (hash ^ (unsigned char)data[i]) * 16777619u;
    return hash;
}

static void playback_progress_path(char *path, size_t size, int slot)
{
    pthread_mutex_lock(&s_store_mx);
    snprintf(path, size, "%s.progress.%d", s_store_path, slot);
    if (strncmp(s_store_path, "/data/", 6)) path[0] = 0;
    pthread_mutex_unlock(&s_store_mx);
}

/* Called only by the existing HTTP accept thread, never by playback/rendering.
 * Failed writes retry at the same bounded rate. Finishing requests a final save. */
static void playback_progress_checkpoint(void)
{
    static uint64_t saved_revision, sequence, last_attempt;
    static char last_session[64];
    static int last_finished;
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) return;
    uint64_t ms = (uint64_t)now.tv_sec * 1000 + (uint64_t)now.tv_nsec / 1000000;
    char session[64];
    pthread_mutex_lock(&s_mx);
    snprintf(session, sizeof session, "%s", s_progress_session);
    double position = s_progress_position, duration = s_progress_duration;
    int finished = s_progress_finished;
    uint64_t revision = s_progress_revision;
    pthread_mutex_unlock(&s_mx);
    if (!session[0] || (position <= 0.0 && duration <= 0.0) || revision == saved_revision) return;
    int changed_session = strcmp(session, last_session) != 0;
    if (!changed_session && !(finished && !last_finished) && ms - last_attempt < 30000) return;
    snprintf(last_session, sizeof last_session, "%s", session);
    last_finished = finished;
    last_attempt = ms;

    char path[600], body[256];
    unsigned long long generation = (unsigned long long)(sequence + 1);
    int size = snprintf(body, sizeof body, "NUVIO1 %llu %s %.0f %.0f ",
        generation, session, position * 1000.0, duration * 1000.0);
    if (size < 0 || (size_t)size >= sizeof body - 12) return;
    uint32_t checksum = playback_progress_checksum(body, (size_t)size);
    size += snprintf(body + size, sizeof body - (size_t)size, "%u\n", checksum);
    playback_progress_path(path, sizeof path, (int)(generation % 2));
    if (!path[0]) return;
    pthread_mutex_lock(&s_progress_disk_mx);
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_SYNC, 0600);
    int ok = 0;
    if (fd >= 0) {
        ok = write(fd, body, (size_t)size) == size;
        if (close(fd)) ok = 0;
    }
    pthread_mutex_unlock(&s_progress_disk_mx);
    if (ok) {
        saved_revision = revision;
        sequence = generation;
    }
}

static int playback_progress_recover(const char *session, double *position, double *duration)
{
    unsigned long long newest = 0;
    int io_error = 0;
    pthread_mutex_lock(&s_progress_disk_mx);
    for (int slot = 0; slot < 2; ++slot) {
        char path[600], body[256], saved_session[64];
        playback_progress_path(path, sizeof path, slot);
        FILE *file = path[0] ? fopen(path, "rb") : NULL;
        if (!file) {
            if (path[0] && errno != ENOENT) io_error = 1;
            continue;
        }
        size_t size = fread(body, 1, sizeof body - 1, file);
        if (ferror(file)) io_error = 1;
        int complete = feof(file) && !ferror(file);
        fclose(file);
        body[size] = 0;
        unsigned long long sequence;
        unsigned checksum;
        double pos, dur;
        int prefix = 0, end = 0;
        if (!complete || sscanf(body, "NUVIO1 %llu %63s %lf %lf %n%u%n",
            &sequence, saved_session, &pos, &dur, &prefix, &checksum, &end) != 5 ||
            end + 1 != (int)size || body[end] != '\n' ||
            checksum != playback_progress_checksum(body, (size_t)prefix) ||
            strcmp(session, saved_session) || sequence <= newest ||
            !isfinite(pos) || pos < 0.0 || !isfinite(dur) || dur < 0.0) continue;
        newest = sequence;
        *position = pos / 1000.0;
        *duration = dur / 1000.0;
    }
    pthread_mutex_unlock(&s_progress_disk_mx);
    return newest ? 1 : io_error ? -1 : 0;
}

void evo_webui_progress_sample(double position, double duration)
{
    pthread_mutex_lock(&s_mx);
    if (s_progress_session[0] && !s_progress_finished) {
        double previous_position = s_progress_position, previous_duration = s_progress_duration;
        /* Active playback can seek to zero. Teardown also resets position, but
         * clears duration: do not replace a real sample with that reset. */
        if (isfinite(position) && (position > 0.0 ||
            (position == 0.0 && isfinite(duration) && duration > 0.0)))
            s_progress_position = position;
        if (isfinite(duration) && duration > 0.0) s_progress_duration = duration;
        if (s_progress_position != previous_position || s_progress_duration != previous_duration)
            ++s_progress_revision;
    }
    pthread_mutex_unlock(&s_mx);
}

void evo_webui_return_to_nuvio(void)
{
    pthread_mutex_lock(&s_mx);
    s_progress_return_detail = 1;
    s_progress_next_episode = 0;
    pthread_mutex_unlock(&s_mx);
}

static void playback_progress_serve(int fd, const char *path)
{
    char session[64], body[160];
    query_param(path, "session", session, sizeof session);
    pthread_mutex_lock(&s_mx);
    int matches = session[0] && !strcmp(session, s_progress_session);
    int finished = s_progress_finished;
    int next_episode = matches ? s_progress_next_episode : 0;
    int return_detail = matches ? s_progress_return_detail : 0;
    int played = matches ? s_progress_played : 0;
    int recommendation = matches ? s_progress_recommendation : 0;
    double position = s_progress_position, duration = s_progress_duration;
    pthread_mutex_unlock(&s_mx);
    if (!matches && session[0]) {
        int recovered = playback_progress_recover(session, &position, &duration);
        if (recovered < 0) {
            respond(fd, "503 Service Unavailable", "text/plain", "", 0);
            return;
        }
        matches = recovered;
        finished = 1;
    }
    if (!matches) {
        respond(fd, "404 Not Found", "text/plain", "", 0);
    } else if (!finished) {
        respond(fd, "409 Conflict", "text/plain", "", 0);
    } else if (position <= 0.0 && !return_detail) {
        respond(fd, "204 No Content", "text/plain", "", 0);
    } else {
        int size = snprintf(body, sizeof body,
            "{\"positionMs\":%.0f,\"durationMs\":%.0f",
            position * 1000.0, duration * 1000.0);
        if (next_episode)
            size += snprintf(body + size, sizeof body - (size_t)size, ",\"nextEpisode\":%d", next_episode);
        if (return_detail)
            size += snprintf(body + size, sizeof body - (size_t)size, ",\"returnToDetail\":true");
        if (played)
            size += snprintf(body + size, sizeof body - (size_t)size, ",\"played\":true");
        if (recommendation)
            size += snprintf(body + size, sizeof body - (size_t)size, ",\"recommendation\":%d", recommendation);
        body[size++] = '}';
        respond(fd, "200 OK", "application/json", body, (size_t)size);
    }
}
