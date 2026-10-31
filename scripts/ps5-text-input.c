/* Included in evo_webui.c. Only the main-thread session calls the existing IME.
 * The server thread queues requests and returns text, without logging it.
 * State: 0 idle, 1 queued, 2 open, 3 accepted, 4 cancelled, 5 unavailable. */
static int s_text_state;
static char s_text_value[1024];

static void text_input_submit(const char *text, void *unused)
{
    (void)unused;
    pthread_mutex_lock(&s_mx);
    snprintf(s_text_value, sizeof s_text_value, "%s", text);
    s_text_state = 3;
    pthread_mutex_unlock(&s_mx);
}

static void text_input_serve(int fd, const char *path)
{
    char value[1024];
    int opening = query_param(path, "open", value, sizeof value);
    pthread_mutex_lock(&s_mx);
    if (opening && (s_text_state == 1 || s_text_state == 2)) {
        pthread_mutex_unlock(&s_mx);
        respond(fd, "409 Conflict", "text/plain", "", 0);
        return;
    }
    if (opening) {
        snprintf(s_text_value, sizeof s_text_value, "%s", value);
        s_text_state = 1;
    }
    int state = s_text_state;
    snprintf(value, sizeof value, "%s", s_text_value);
    pthread_mutex_unlock(&s_mx);
    const char *status = state == 1 || state == 2 ? "202 Accepted" :
        state == 3 ? "200 OK" : state == 4 ? "204 No Content" : "503 Service Unavailable";
    respond(fd, status, "text/plain; charset=utf-8", state == 3 ? value : "", state == 3 ? strlen(value) : 0);
}
