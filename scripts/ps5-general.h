#ifndef NUVIO_PRESENTATION_H
#define NUVIO_PRESENTATION_H
#include <stddef.h>
#include <stdint.h>

/* Session-scoped presentation, prepared by Nuvio before browser closure.
 * Native playback receives text/policy only, never recommendation URLs. */
typedef struct {
    int active, loading, loading_detail, pause, clock, utc_offset_minutes;
    int movie, recommendation_enabled, threshold_minutes, episode_threshold_minutes;
    int pause_delay_ms, recommendation_count;
    double threshold, episode_threshold, credits_start, credits_end, post_credits_end;
    char description[801], parental[801];
    struct { char title[161], description[401]; } recommendations[3];
} nuvio_presentation_t;

typedef struct { int pause, parental, recommendation; } nuvio_presentation_view_t;
#ifdef __cplusplus
extern "C" {
#endif
const nuvio_presentation_t *evo_webui_presentation(void);
void evo_webui_presentation_started(void);
void evo_webui_recommendation_selected(int index);
nuvio_presentation_view_t evo_webui_presentation_update(double position, double duration,
    uint64_t now, int ready, int paused, int blocked, int ended);
void evo_webui_presentation_action(int action); /* 1 cycle, 2 keep watching */
void evo_webui_presentation_clock(double position, double duration, char *out, size_t size);
#ifdef __cplusplus
}
#endif
#endif
