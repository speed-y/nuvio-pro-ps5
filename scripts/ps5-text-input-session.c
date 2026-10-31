/* Browser/native keyboard session. Included after ps5-text-input.c.
 * Keep the loopback server alive, but never overlap the two system dialogs.
 * No query text enters the diagnostic log. */
#include <time.h>
#include "evo_ime_dialog.h"

static void open_dialog(const char *url);
static void read_result(void);
static int s_text_phase;
static struct timespec s_text_started;

static long text_input_elapsed(void)
{
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (now.tv_sec - s_text_started.tv_sec) * 1000L +
           (now.tv_nsec - s_text_started.tv_nsec) / 1000000L;
}

static void text_input_phase(int phase)
{
    s_text_phase = phase;
    clock_gettime(CLOCK_MONOTONIC, &s_text_started);
    tlog("Search keyboard: phase=%d", phase);
}

/* True consumes this frame and suppresses the normal browser state machine.
 * Phases: 1 closing browser, 2 keyboard, 4 cleanup, 5 blocked.
 * Only closure/cleanup have deadlines. Typing never has a timeout. */
static int text_input_session_pump(void)
{
    pthread_mutex_lock(&s_mx);
    int state = s_text_state;
    char initial[1024];
    snprintf(initial, sizeof initial, "%s", s_text_value);
    pthread_mutex_unlock(&s_mx);
    if (!s_text_phase) {
        if (state != 1) return 0;
        if (s_state != P_RUN || strcmp(s_hook_profile, "nuvio")) {
            pthread_mutex_lock(&s_mx);
            s_text_state = 5;
            pthread_mutex_unlock(&s_mx);
            return 1;
        }
        int rc = sceWebBrowserDialogClose();
        tlog("Search keyboard: browser Close rc=0x%08x", (unsigned)rc);
        if (rc != 0) {
            pthread_mutex_lock(&s_mx);
            s_text_state = 5;
            pthread_mutex_unlock(&s_mx);
            return 1;
        }
        s_closed_by_evo = 1;
        s_state = P_CLOSING;
        text_input_phase(1);
        return 1;
    }
    if (s_text_phase == 1) {
        int status = sceWebBrowserDialogUpdateStatus();
        if (status == CDLG_STATUS_FINISHED || status == CDLG_STATUS_NONE ||
            status == CDLG_STATUS_INITIALIZED) {
            tlog("Search keyboard: browser closed status=%d", status);
            if (status == CDLG_STATUS_FINISHED) read_result();
            s_state = P_PLAYING; /* Reserve the session without starting playback. */
            int opened = evo_keyboard_open_native("Search movies & series", initial, 255,
                                                   text_input_submit, NULL);
            pthread_mutex_lock(&s_mx);
            s_text_state = opened ? 2 : 5;
            pthread_mutex_unlock(&s_mx);
            tlog("Search keyboard: native open=%d", opened);
            text_input_phase(opened ? 2 : 4);
        } else if (text_input_elapsed() >= 10000) {
            tlog("Search keyboard: browser closure unconfirmed status=%d; stopping", status);
            text_input_phase(5);
        }
    } else if (s_text_phase == 2) {
        evo_keyboard_update();
        if (!evo_keyboard_is_open()) {
            pthread_mutex_lock(&s_mx);
            if (s_text_state == 2) s_text_state = 4;
            pthread_mutex_unlock(&s_mx);
            text_input_phase(4);
        }
    } else if (s_text_phase == 4) {
        int status = sceImeDialogGetStatus();
        if (status == SCE_IME_DIALOG_STATUS_NONE) {
            tlog("Search keyboard: native cleanup confirmed; reopening Search");
            char url[sizeof s_reopen_url];
            int n = snprintf(url, sizeof url, "%s%cnuvioPlaybackReturn=1&nuvioKeyboardReturn=1",
                             s_open_url, strchr(s_open_url, '?') ? '&' : '?');
            if (n < 0 || (size_t)n >= sizeof url) {
                text_input_phase(5);
                return 1;
            }
            snprintf(s_reopen_url, sizeof s_reopen_url, "%s", url);
            s_text_phase = 0;
            open_dialog(s_reopen_url);
        } else if (text_input_elapsed() >= 10000) {
            tlog("Search keyboard: native cleanup unconfirmed status=%d; stopping", status);
            text_input_phase(5);
        }
    }
    return 1;
}
