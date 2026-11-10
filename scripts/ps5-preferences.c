/* Source/session-owned preferences. The browser import runs before playback;
 * selectors run on the existing playback worker, not the UI/download thread. */
#include "ps5-preferences.h"
#include "evo_langpref.h"
#include "evo_subtitle.h"
#include "evo_online_subs.h"
#include <ctype.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>

static nuvio_preferences_t policy;
static char policy_key[80];
static int candidate_forced[EVO_OSUB_MAX];

static int decode_targets(const cJSON *object, const char *name, char out[2][16], int *count)
{
    const cJSON *array = cJSON_GetObjectItemCaseSensitive(object, name);
    if (!cJSON_IsArray(array) || cJSON_GetArraySize(array) > 2) return 0;
    *count = cJSON_GetArraySize(array);
    for (int i = 0; i < *count; ++i) {
        const cJSON *v = cJSON_GetArrayItem(array, i);
        if (!cJSON_IsString(v) || !v->valuestring) return 0;
        const char *s = v->valuestring;
        size_t n = strlen(s), base = strcspn(s, "-");
        if (!n) continue; /* Unresolvable target, preserving primary/secondary order. */
        if (n >= 16 || base < 2 || base > 3) return 0;
        for (size_t j = 0; j < n; ++j) {
            unsigned char c = (unsigned char)s[j];
            if (j < base ? !isalpha(c) : !(isalnum(c) || c == '-')) return 0;
            if (c >= 128) return 0;
        }
        for (size_t j = base; j < n;) {
            size_t start = ++j;
            while (j < n && s[j] != '-') ++j;
            if (j - start < 2 || j - start > 8) return 0;
        }
        strcpy(out[i], s);
    }
    return 1;
}

int nuvio_preferences_decode(const cJSON *object, nuvio_preferences_t *out)
{
    memset(out, 0, sizeof *out);
    if (!object) return 1; /* Older sender: keep the native policy unchanged. */
    if (!cJSON_IsObject(object)) return 0;
    const cJSON *mode = cJSON_GetObjectItemCaseSensitive(object, "mode");
    if (!cJSON_IsString(mode) || !mode->valuestring) return 0;
    if (!strcmp(mode->valuestring, "off")) out->mode = 0;
    else if (!strcmp(mode->valuestring, "language")) out->mode = 1;
    else if (!strcmp(mode->valuestring, "audio-forced")) out->mode = 2;
    else return 0;
    if (!decode_targets(object, "audio", out->audio, &out->audio_count) ||
        !decode_targets(object, "subtitle", out->subtitle, &out->subtitle_count)) return 0;
    out->valid = 1;
    return 1;
}

void nuvio_preferences_import(const char *session, const nuvio_preferences_t *p,
                              const int *forced, int count)
{
    policy = *p;
    snprintf(policy_key, sizeof policy_key, "web:%s", session);
    memset(candidate_forced, 0, sizeof candidate_forced);
    for (int i = 0; i < count && i < EVO_OSUB_MAX; ++i) candidate_forced[i] = !!forced[i];
}

int nuvio_preferences_active(const char *provider, const char *key)
{
    return policy.valid && policy_key[4] && !strcmp(provider, "web") && !strcmp(key, policy_key);
}

/* Reuse EVO's language aliases, but retain regions: ordinary matching allows
 * base-language fallback; forced matching must not cross sibling regions. */
static int language_match(const char *tag, const char *target, int forced)
{
    if (!tag || !target || !tag[0] || !target[0]) return 0;
    char a[4], b[4];
    if (!evo_lang_normalize(tag, a) || !evo_lang_normalize(target, b)) {
        /* Unknown-to-EVO language codes can still match exactly, not English. */
        return !strcmp(tag, target) ? 2 : 0;
    }
    if (strcmp(a, b)) return 0;
    const char *ar = strpbrk(tag, "-_"), *br = strpbrk(target, "-_");
    if (!ar && !br) return 2;
    if (ar && br) {
        ++ar; ++br;
        while (*ar && *br && tolower((unsigned char)*ar) == tolower((unsigned char)*br)) { ++ar; ++br; }
        if (!*ar && !*br) return 2;
        if (forced) return 0;
    }
    return 1;
}

static const char *stream_language(AVStream *stream)
{
    const AVDictionaryEntry *lang = av_dict_get(stream->metadata, "language", NULL, 0);
    return lang ? lang->value : "";
}

static int decodable_audio(AVFormatContext *format, int index)
{
    if (index < 0 || index >= (int)format->nb_streams) return 0;
    AVStream *st = format->streams[index];
    return st && st->codecpar && st->codecpar->codec_type == AVMEDIA_TYPE_AUDIO &&
           avcodec_find_decoder(st->codecpar->codec_id);
}

static int in_program(AVFormatContext *format, int program, int index)
{
    if (program < 0) return 1;
    if (program >= (int)format->nb_programs) return 0;
    const AVProgram *p = format->programs[program];
    for (unsigned i = 0; p && i < p->nb_stream_indexes; ++i)
        if (p->stream_index[i] == (unsigned)index) return 1;
    return 0;
}

static int commentary(AVStream *st)
{
    const AVDictionaryEntry *title = av_dict_get(st->metadata, "title", NULL, 0);
    return (st->disposition & AV_DISPOSITION_COMMENT) ||
        (title && (strstr(title->value, "omment") || strstr(title->value, "OMMENT")));
}

int nuvio_preferences_audio(AVFormatContext *format, int fallback, int program,
                            const nuvio_preferences_snapshot *reopen)
{
    if (reopen->valid && decodable_audio(format, reopen->audio)) return reopen->audio;
    for (int t = 0; t < policy.audio_count; ++t) {
        int best = -1, score = -1;
        for (unsigned i = 0; i < format->nb_streams; ++i) {
            if (!decodable_audio(format, (int)i) || !in_program(format, program, (int)i)) continue;
            AVStream *st = format->streams[i];
            int match = language_match(stream_language(st), policy.audio[t], 0);
            if (!match) continue;
            int rank = match * 100 + 10 + ((st->disposition & AV_DISPOSITION_DEFAULT) ? 5 : 0) -
                       (commentary(st) ? 9 : 0);
            if (rank > score) { best = (int)i; score = rank; }
        }
        if (best >= 0) return best;
    }
    return fallback; /* No invented English/unrelated-language preference. */
}

static int usable_subtitle(AVStream *st)
{
    if (!st || !st->codecpar || st->codecpar->codec_type != AVMEDIA_TYPE_SUBTITLE) return 0;
    enum AVCodecID id = st->codecpar->codec_id;
    return (prospero_embedded_subtitle_supported(id) || prospero_embedded_subtitle_is_bitmap(id)) &&
           (id == AV_CODEC_ID_SUBRIP || avcodec_find_decoder(id));
}

/* Same conditional as applyStartupSubtitlePreference: forced-only applies
 * when the selected native audio matches; foreign audio uses normal subtitles. */
static int subtitle_targets(AVFormatContext *format, int audio, const char **targets, int *forced)
{
    *forced = 0;
    const char *lang = decodable_audio(format, audio) ? stream_language(format->streams[audio]) : "";
    if (!policy.mode) return 0;
    if (policy.mode == 2) {
        if (policy.subtitle_count && language_match(lang, policy.subtitle[0], 1)) {
            targets[0] = policy.subtitle[0]; *forced = 1; return 1;
        }
        if (!policy.subtitle_count) {
            for (int i = 0; i < policy.audio_count; ++i) {
                if (language_match(lang, policy.audio[i], 0)) {
                    targets[0] = lang; *forced = 1; return 1;
                }
            }
        }
    }
    for (int i = 0; i < policy.subtitle_count; ++i) targets[i] = policy.subtitle[i];
    return policy.subtitle_count;
}

static int open_subtitle(AVFormatContext *format, int index)
{
    prospero_subtitle_requested_stream = index;
    if (!prospero_embedded_subtitle_open(format)) return 0;
    prospero_subtitle_use_external = 0;
    prospero_subtitle_enabled = 1;
    return 1;
}

void nuvio_preferences_subtitles(AVFormatContext *format, int audio,
                                 const nuvio_preferences_snapshot *reopen)
{
    prospero_embedded_subtitle_close();
    prospero_subtitle_clear();
    prospero_subtitle_enabled = 0;
    prospero_subtitle_use_external = 0;
    if (reopen->valid) {
        if (reopen->path[0] && prospero_subtitle_load_file_quiet(reopen->path) > 0)
            snprintf(prospero_subtitle_external_label, sizeof prospero_subtitle_external_label,
                     "%s", reopen->label);
        if (reopen->external && prospero_subtitle_count > 0) {
            prospero_subtitle_use_external = 1;
            prospero_subtitle_requested_stream = -1;
        } else if (reopen->subtitle >= 0 && reopen->subtitle < (int)format->nb_streams &&
                   !reopen->external && usable_subtitle(format->streams[reopen->subtitle])) {
            open_subtitle(format, reopen->subtitle);
        }
        prospero_subtitle_enabled = reopen->enabled;
        return; /* Including explicit OFF. Never re-run auto selection here. */
    }
    /* Secondary language is a fallback, not a request for a second caption.
     * Never carry a prior session's manual secondary index into this file. */
    prospero_secondary_subtitle_requested = PROSPERO_SECONDARY_NONE;
    const char *targets[2];
    int forced;
    int count = subtitle_targets(format, audio, targets, &forced);
    char key[80];
    evo_osubs_key(key, sizeof key);
    for (int t = 0; t < count; ++t) {
        int upper = INT_MAX, after = -1;
        for (;;) {
            int best = -1, score = INT_MIN;
            for (unsigned i = 0; i < format->nb_streams; ++i) {
                AVStream *st = format->streams[i];
                if (!usable_subtitle(st) || !!prospero_subtitle_stream_is_forced(st) != forced) continue;
                int match = language_match(stream_language(st), targets[t], forced);
                if (!match) continue;
                int cues = prospero_subtitle_declared_cues(st);
                int rank = match * 100 + 10 + ((st->disposition & AV_DISPOSITION_DEFAULT) ? 5 : 0) -
                           (commentary(st) ? 9 : 0);
                if (!forced && cues >= 0 && cues < PROSPERO_SUBTITLE_MIN_USEFUL_CUES) rank -= 1000;
                if (rank > upper || (rank == upper && (int)i <= after)) continue;
                if (rank > score) { best = (int)i; score = rank; }
            }
            if (best < 0) break;
            if (open_subtitle(format, best)) return;
            /* Retry the next ranked embedded decoder before addon fallback. */
            upper = score;
            after = best;
        }
        /* A decoder can exist but fail to open; try the supported addon path
         * too. Actual parsing, not a URL suffix, decides SRT/VTT support. */
        if (strcmp(key, policy_key)) continue;
        for (int i = 0; i < evo_osubs_count() && i < EVO_OSUB_MAX; ++i) {
            evo_osub_t entry;
            if (!evo_osubs_get(i, &entry) || candidate_forced[i] != forced ||
                !language_match(entry.lang_tag, targets[t], forced)) continue;
            const char *path = evo_osubs_fetch_sync(i);
            if (!path || prospero_subtitle_load_file_quiet(path) <= 0) continue;
            char label[96];
            evo_osubs_label(i, label, sizeof label);
            snprintf(prospero_subtitle_external_label, sizeof prospero_subtitle_external_label, "%s", label);
            prospero_subtitle_use_external = 1;
            prospero_subtitle_enabled = 1;
            prospero_subtitle_requested_stream = -1;
            evo_osubs_set_active(i);
            evo_osubs_remember(path, label);
            return;
        }
    }
    prospero_subtitle_requested_stream = -2;
}
