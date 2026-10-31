/* Included in evo_webui.c. Identity stays in the saved browser snapshot; the
 * native side only holds an opaque session and measured playback times. */
static char s_h_progress_session[64], s_play_progress_session[64];
static char s_progress_session[64];
static double s_progress_position, s_progress_duration;
static int s_progress_finished;

void evo_webui_progress_sample(double position, double duration)
{
    pthread_mutex_lock(&s_mx);
    if (s_progress_session[0] && !s_progress_finished) {
        /* Active playback can seek to zero. Teardown also resets position, but
         * clears duration: do not replace a real sample with that reset. */
        if (isfinite(position) && (position > 0.0 ||
            (position == 0.0 && isfinite(duration) && duration > 0.0)))
            s_progress_position = position;
        if (isfinite(duration) && duration > 0.0) s_progress_duration = duration;
    }
    pthread_mutex_unlock(&s_mx);
}

static void playback_progress_serve(int fd, const char *path)
{
    char session[64], body[160];
    query_param(path, "session", session, sizeof session);
    pthread_mutex_lock(&s_mx);
    int matches = session[0] && !strcmp(session, s_progress_session);
    int finished = s_progress_finished;
    double position = s_progress_position, duration = s_progress_duration;
    pthread_mutex_unlock(&s_mx);
    if (!matches) {
        respond(fd, "404 Not Found", "text/plain", "", 0);
    } else if (!finished) {
        respond(fd, "409 Conflict", "text/plain", "", 0);
    } else if (position <= 0.0) {
        respond(fd, "204 No Content", "text/plain", "", 0);
    } else {
        int size = snprintf(body, sizeof body,
            "{\"positionMs\":%.0f,\"durationMs\":%.0f}",
            position * 1000.0, duration * 1000.0);
        respond(fd, "200 OK", "application/json", body, (size_t)size);
    }
}
