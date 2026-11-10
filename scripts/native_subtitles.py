"""Bounded subtitle fixes, applied after the existing EVO adapters.

Browser addon handoff is deliberately not implemented here: the current media
handoff precedes asynchronous subtitle discovery/selection, and browser embedded
track indices are not a native selection contract. Do not infer a choice from
stale DOM tracks or silently change subtitle-off into automatic selection.
"""


TIMING_PARSER = r'''/* External SRT and WebVTT share cues, but VTT permits MM:SS.mmm.
 * Parse each endpoint independently: a cue can cross the one-hour boundary.
 * Missing timestamps and malformed fractions must not become time zero. */
static int prospero_subtitle_parse_timestamp(const char **cursor, double *seconds) {
    const char *p = *cursor;
    unsigned first = 0;
    int digits = 0;
    while (*p >= '0' && *p <= '9') {
        if (++digits > 6) return 0;
        first = first * 10 + (unsigned)(*p++ - '0');
    }
    if (digits < 1 || *p++ != ':') return 0;
    if (p[0] < '0' || p[0] > '9' || p[1] < '0' || p[1] > '9') return 0;
    unsigned middle = (unsigned)(p[0] - '0') * 10 + (unsigned)(p[1] - '0');
    p += 2;
    unsigned hour = 0, minute = first, second = middle;
    if (*p == ':') {
        p++;
        if (p[0] < '0' || p[0] > '9' || p[1] < '0' || p[1] > '9') return 0;
        hour = first;
        minute = middle;
        second = (unsigned)(p[0] - '0') * 10 + (unsigned)(p[1] - '0');
        p += 2;
    } else if (digits != 2) {
        return 0;
    }
    if (minute > 59 || second > 59 || (*p != '.' && *p != ',')) return 0;
    p++;
    unsigned millisecond = 0;
    for (int i = 0; i < 3; i++) {
        if (*p < '0' || *p > '9') return 0;
        millisecond = millisecond * 10 + (unsigned)(*p++ - '0');
    }
    if (*p && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n') return 0;
    *seconds = hour * 3600.0 + minute * 60.0 + second + millisecond / 1000.0;
    *cursor = p;
    return 1;
}

static int prospero_subtitle_parse_timing(
    const char *line,
    double *start_seconds,
    double *end_seconds
) {
    const char *p = line;
    while (*p == ' ' || *p == '\t') p++;
    if (!prospero_subtitle_parse_timestamp(&p, start_seconds)) return 0;
    while (*p == ' ' || *p == '\t') p++;
    if (strncmp(p, "-->", 3)) return 0;
    p += 3;
    while (*p == ' ' || *p == '\t') p++;
    if (!prospero_subtitle_parse_timestamp(&p, end_seconds)) return 0;
    /* WebVTT cue settings may follow the end timestamp. */
    return *end_seconds >= *start_seconds;
}


'''

SIDECAR_SELECTION = '''    /* A matching .srt next to the file is the track to show, when the user
     * asked for subtitles on their own (Settings > Auto Subtitles) and did not
     * just pick an embedded track. The setting was saved but never applied, so
     * a sidecar loaded and stayed off. */
    if (prospero_subtitle_count > 0 && prospero_subtitle_requested_stream < 0) {
        auto settings = Application::getInstance().getSettingsService();
        if (!settings || settings->isAutoSubtitlesEnabled()) {
            prospero_subtitle_select_primary(-1);
            EVO_LOGI("subtitles", "sidecar on: %d cues", prospero_subtitle_count);
        }
    }
'''

REMOTE_WRITE = '''                std::fwrite(body, 1, blen, f);
                std::fclose(f);
                prospero_subtitle_load_external(tmp);'''

REMOTE_WRITE_CHECKED = '''                const bool complete = std::fwrite(body, 1, blen, f) == blen;
                const bool closed = std::fclose(f) == 0;
                if (complete && closed)
                    prospero_subtitle_load_external(tmp);'''


def _replace(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError('Pinned external subtitle anchor changed')
    return source.replace(old, new)


def patch_primary_selection(source):
    """Refill a newly opened primary through the existing single-reader seek."""
    source = _replace(source, '#include "evo_subtitle.h"',
                      '#include "evo_subtitle.h"\n#include "evo_demux.h"\n#include "evo_playback.h"')
    start = 'static int prospero_sub_slot_start(\n'
    end = 'int prospero_embedded_subtitle_open(\n'
    if source.count(start) != 1 or source.count(end) != 1:
        raise RuntimeError('Pinned subtitle slot anchors changed')
    before, tail = source.split(start)
    slot, after = tail.split(end)
    # Prepare the replacement decoder without disturbing the working track.
    # A missing decoder / invalid codec parameters must not clear its cues or
    # discard a secondary that the primary intended to take over.
    slot = _replace(slot, '''    prospero_sub_slot_close(slot);

    pthread_mutex_lock(
        &slot->state_mutex
    );

    *slot->stream_index = stream_index;
    slot->codec_id = codec_id;

    if (slot == SUB_PRIMARY) {
        dbg_sub_cid = (int)codec_id;
    }
''', '    AVCodecContext *context = NULL;\n')
    slot = _replace(slot, '        AVCodecContext *context = NULL;\n', '')
    slot = _replace(slot, '''            *slot->stream_index = -1;
            slot->codec_id = AV_CODEC_ID_NONE;

            pthread_mutex_unlock(
                &slot->state_mutex
            );

''', '')
    slot = _replace(slot, '''        *slot->ctx = context;
    }

    pthread_mutex_unlock(
        &slot->state_mutex
    );
''', '''    }

    /* Commit only after decoder preparation succeeds. */
    prospero_sub_slot_close(slot);
    pthread_mutex_lock(&slot->state_mutex);
    *slot->ctx = context;
    *slot->stream_index = stream_index;
    slot->codec_id = codec_id;
    if (slot == SUB_PRIMARY) dbg_sub_cid = (int)codec_id;
    pthread_mutex_unlock(&slot->state_mutex);
''')
    source = before + start + slot + end + after
    source = _replace(source, ' * decoder its codec needs and start following the stream. Returns 1, or 0 with\n * the slot left closed. `title` heads the toast.',
                      ' * decoder its codec needs and start following the stream. Returns 1, or 0 with\n * the previous slot unchanged. `title` heads the toast.')
    source = _replace(source, ''' * index. In place, exactly as the secondary switches: the demuxer already
 * delivers every subtitle stream, and the decoder for the new track's codec
 * is opened under the slot's lock.''', ''' * index. The demuxer decodes only selected streams and may be minutes ahead
 * of presentation. After opening a different embedded track, ask that same
 * reader to seek to the presentation clock so its current cues are reread.
 * Decoder replacement is committed under the slot's lock.''')
    start = 'int prospero_subtitle_select_primary(int track) {\n'
    end = '/* PROSPERO_SECONDARY_SUBTITLE_END */'
    if source.count(start) != 1 or source.count(end) != 1:
        raise RuntimeError('Pinned primary subtitle anchors changed')
    before, tail = source.split(start)
    selection, after = tail.split(end)
    selection = _replace(selection, '''        prospero_subtitle_use_external = 1;
        prospero_subtitle_enabled = 1;
''', '''        prospero_subtitle_use_external = 1;
        prospero_subtitle_enabled = 1;
        prospero_subtitle_requested_stream = -1;
''')
    selection = _replace(selection, '''    if (track == prospero_secondary_subtitle_stream_index) {
        prospero_secondary_drop();
    }

    prospero_subtitle_use_external = 0;
    prospero_subtitle_enabled = 1;

    if (track == prospero_embedded_subtitle_stream_index) {
        return 1;
    }

    return prospero_sub_slot_start(
        SUB_PRIMARY,
        play_fmt,
        track,
        "EMBEDDED SUBTITLES"
    );
''', '''    const int changed = track != prospero_embedded_subtitle_stream_index;
    if (changed && !prospero_sub_slot_start(
            SUB_PRIMARY, play_fmt, track, "EMBEDDED SUBTITLES")) {
        return 0;
    }

    if (track == prospero_secondary_subtitle_stream_index) {
        prospero_secondary_drop();
    }

    prospero_subtitle_use_external = 0;
    prospero_subtitle_enabled = 1;
    prospero_subtitle_requested_stream = track;

    /* An unchanged slot retains its cues, even when returning from external.
     * Capture pause before the request: queuing a seek itself pauses playback.
     * The clock is relative to the last seek/resume, but the request is absolute.
     * The demuxer owns the seek/reset/refill and restores this pause state. */
    if (changed) {
        const int restore_paused = player_paused;
        return prospero_request_inplace_seek(
            resume_base_offset_seconds + evo_pb_position_s(), restore_paused);
    }
    return 1;
''')
    return before + start + selection + end + after


def patch_subtitle_source(source):
    """Fix primary selection and external timing; keep the real loaders."""
    source = patch_primary_selection(source)
    start = 'static int prospero_subtitle_parse_timing(\n'
    end = 'static void prospero_subtitle_clean_line(\n'
    if source.count(start) != 1 or source.count(end) != 1:
        raise RuntimeError('Pinned external subtitle parser changed')
    before, tail = source.split(start)
    old, after = tail.split(end)
    if '"%d:%d:%d%c%d --> %d:%d:%d%c%d"' not in old:
        raise RuntimeError('Pinned external subtitle timing format changed')
    return before + TIMING_PARSER + end + after


def patch_controller_source(source):
    """Apply the existing auto/embedded policy after both sidecar load paths."""
    source = _replace(source, SIDECAR_SELECTION, '')
    source = _replace(source, REMOTE_WRITE, REMOTE_WRITE_CHECKED)
    anchor = '    /*\n     * AUTO SUBTITLES: a new file starts with subtitles on or off as the\n'
    selection = SIDECAR_SELECTION.replace(
        'A matching .srt next to the file is the track to show',
        'A successfully loaded local or remote sidecar is the track to show')
    return _replace(source, anchor, selection + anchor)


def patch_native(app):
    """Invoke after polish.apply; app is EVO's projects/evoplayer directory."""
    subtitle = app / 'media/src/evo_subtitle.c'
    controller = app / 'core/src/services/PlaybackController.cpp'
    # Validate both transformations before writing either generated source.
    subtitle_text = patch_subtitle_source(subtitle.read_text())
    controller_text = patch_controller_source(controller.read_text())
    subtitle.write_text(subtitle_text)
    controller.write_text(controller_text)
