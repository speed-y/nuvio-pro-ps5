/* Ephemeral browser profile policy. Never changes native SettingsService. */
#ifndef NUVIO_PREFERENCES_H
#define NUVIO_PREFERENCES_H
#ifdef __cplusplus
extern "C" {
#endif
#include <libavformat/avformat.h>
#include "cJSON.h"

typedef struct {
    int valid;
    int mode; /* 0 off, 1 language, 2 audio-forced (resolved after native audio selection) */
    int audio_count, subtitle_count;
    char audio[2][16], subtitle[2][16];
} nuvio_preferences_t;

/* Stack-owned before stopPlayback clears subtitle cues. Indices are reused
 * ONLY for an exact same provider/session/source reopen, never another file. */
typedef struct {
    int valid, audio, enabled, external, subtitle;
    char path[512], label[96];
} nuvio_preferences_snapshot;

int nuvio_preferences_decode(const cJSON *object, nuvio_preferences_t *out);
void nuvio_preferences_import(const char *session, const nuvio_preferences_t *policy,
                              const int *forced, int count);
int nuvio_preferences_active(const char *provider, const char *key);
int nuvio_preferences_audio(AVFormatContext *format, int fallback, int program,
                            const nuvio_preferences_snapshot *reopen);
void nuvio_preferences_subtitles(AVFormatContext *format, int audio,
                                 const nuvio_preferences_snapshot *reopen);
void nuvio_preferences_capture(nuvio_preferences_snapshot *out, int audio);

#ifdef __cplusplus
}
#endif
#endif
