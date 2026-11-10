"""Port-owned playback lifetime fixes, applied after the EVO shell adapters."""
from pathlib import Path
import re

HERE = Path(__file__).parent


def patch_native(app):
    from polish import replace
    audio = app/'media/src/evo_audio_out.c'
    text = audio.read_text()
    # One iteration owns every packet/frame it pops and frees. The seek cannot
    # reset its decoder, resampler, ring or clock until that iteration exits.
    start = text.index('void *audio_decode_thread_func(void *arg) {')
    body = text.index('    while (audio_decode_thread_running) {', start)
    end = text.index('\n    av_frame_free(&af);', body)
    step = text[body + len('    while (audio_decode_thread_running) {'):end]
    if not step.endswith('    }\n') or step.count('continue;') != 5:
        raise RuntimeError('Pinned audio decode iteration changed')
    step = step[:-len('    }\n')].replace('continue;', 'return;')
    step = step.replace('while (audio_decode_thread_running && audio_queue_count > 10)',
        'while (audio_decode_thread_running && !atomic_load(&s_audio_seek_hold) && audio_queue_count > 10)')
    step = step.replace('        AVPacket *pkt = packet_queue_pop(&audio_packet_queue);',
        '        if (atomic_load(&s_audio_seek_hold)) return;\n        AVPacket *pkt = packet_queue_pop(&audio_packet_queue);')
    step = step.replace('while (audio_decode_thread_running && evo_pt_queued_grains() > 64)',
        'while (audio_decode_thread_running && !atomic_load(&s_audio_seek_hold) && evo_pt_queued_grains() > 64)')
    anchor = '\n            if (pkt->pts != AV_NOPTS_VALUE && play_fmt && audio_stream_index >= 0) {'
    # This indentation uniquely identifies the passthrough path.
    if step.count(anchor) != 1: raise RuntimeError('Pinned passthrough packet ownership changed')
    step = step.replace(anchor,
        '\n            if (atomic_load(&s_audio_seek_hold)) { av_packet_free(&pkt); return; }'+anchor)
    step = step.replace('while (audio_decode_thread_running && avcodec_receive_frame(audio_ctx, af) == 0)',
        'while (audio_decode_thread_running && !atomic_load(&s_audio_seek_hold) && avcodec_receive_frame(audio_ctx, af) == 0)')
    # Valid negative PTS is preroll, not a missing timestamp.
    step = step.replace('            double pkt_seconds = -1.0;',
        '            const int has_pts = pkt->pts != AV_NOPTS_VALUE && play_fmt && audio_stream_index >= 0;\n            double pkt_seconds = 0.0;')
    step = step.replace('            if (pkt_seconds >= 0.0) {', '            if (has_pts) {')
    text = text[:start] + '''static void audio_decode_step(AVFrame *af) {'''+step+'''}

void *audio_decode_thread_func(void *arg) {
    (void)arg;
    AVFrame *af = av_frame_alloc();
    if (!af) return NULL;
    while (audio_decode_thread_running) {
        if (atomic_load(&s_audio_seek_hold)) { usleep(1000); continue; }
        pthread_mutex_lock(&s_audio_decode_mx);
        if (!atomic_load(&s_audio_seek_hold)) audio_decode_step(af);
        pthread_mutex_unlock(&s_audio_decode_mx);
    }
''' + text[end:]
    start = text.index('void *audio_output_thread(void *arg) {')
    body = text.index('    while (audio_thread_running) {', start)
    end = text.index('\n    return NULL;\n}', body) + len('\n    return NULL;\n}')
    step = text[body + len('    while (audio_thread_running) {'):end - len('\n    return NULL;\n}')]
    if not step.endswith('    }') or step.count('continue;') != 3:
        raise RuntimeError('Pinned audio output iteration changed')
    step = step[:-len('    }')].replace('continue;', 'return;')
    step = re.sub(r'\b(video_rel_at_wait|video_stuck_iters)\b', r'(*\1)', step)
    text = text[:start] + '''static void audio_output_step(double *video_rel_at_wait, int *video_stuck_iters) {
    static int16_t silence[AUDIO_BLOCK_SAMPLES * EVO_AUDIO_MAX_CH];
''' + step + '''}

void *audio_output_thread(void *arg) {
    (void)arg;
    double video_rel_at_wait = -1.0;
    int video_stuck_iters = 0;
    while (audio_thread_running) {
        if (atomic_load(&s_audio_seek_hold)) { usleep(1000); continue; }
        pthread_mutex_lock(&s_audio_output_mx);
        if (!atomic_load(&s_audio_seek_hold))
            audio_output_step(&video_rel_at_wait, &video_stuck_iters);
        pthread_mutex_unlock(&s_audio_output_mx);
    }
    return NULL;
}''' + text[end:]
    audio.write_text(text)
    replace(audio, 'int audio_handle = -1;',
        (HERE/'ps5-audio-seek.c').read_text() + '\nint audio_handle = -1;')
    replace(audio, 'while (index < converted && audio_decode_thread_running)',
        'while (index < converted && audio_decode_thread_running && !atomic_load(&s_audio_seek_hold))')
    replace(audio, '''                    audio_decode_thread_running &&
                    audio_queue_count >=''', '''                    audio_decode_thread_running && !atomic_load(&s_audio_seek_hold) &&
                    audio_queue_count >=''')
    replace(audio, '                if (!audio_decode_thread_running) {',
        '                if (!audio_decode_thread_running || atomic_load(&s_audio_seek_hold)) {')
    replace(app/'media/include/evo_audio_out.h', 'void *audio_output_thread(void *arg);',
        '''/* Successful begin holds both workers until end; failure changes no queues. */
int evo_audio_seek_begin(void);
void evo_audio_seek_end(void);
void *audio_output_thread(void *arg);''')
    demux = app/'media/src/evo_demux.c'
    replace(demux, '''    /*
     * Clear EOF immediately.''', '''    /* Never flush a live decoder or reset a live output completion. */
    if ((video_thread_running && !video_decode_parked) || !evo_audio_seek_begin()) {
        pp_stage_bc("SEEK_PARK", "worker timeout; seek cancelled before reset");
        prospero_seek_in_progress = 0;
        video_decode_hold = 0;
        pp_playback_notify_seek_end(&g_pp_pb, 0, 0, 0);
        if (!restore_paused) pp_playback_resume(&g_pp_pb);
        player_paused = restore_paused ? 1 : 0;
        return 0;
    }
    /*
     * Clear EOF immediately.''')
    replace(demux, '''        if (target_seconds > 0.05)
            audio_seek_discard_until = target_seconds;
        else
            audio_seek_discard_until = -1.0;''',
        '        audio_seek_discard_until = target_seconds;')
    replace(demux, '    prospero_seek_in_progress = 0;\n    video_decode_hold = 0;',
        '    prospero_seek_in_progress = 0;\n    evo_audio_seek_end();\n    video_decode_hold = 0;')
    replace(app/'core/src/services/PlaybackController.cpp',
        '''    m_resumeBaseOffset = targetSeconds;
    resume_base_offset_seconds = targetSeconds;

    int64_t targetUs''',
        '''    // The demuxer publishes the base only after a successful seek.
    // A refused request or worker timeout must retain the measured position.
    int64_t targetUs''')
    patch_worker_start(app)
    patch_track_reopen(app)


def patch_track_reopen(app):
    """Keep temporary decoder teardown inside the current browser session."""
    from polish import replace
    replace(app/'core/include/evo/screens/AudioTrackPickerScreen.hpp',
        '    void onExit() override;', '''    void onExit() override;
    // Main-thread ownership lasts until update/onExit joins the reopen worker.
    bool isSwitchingTracks() const { return m_threadLive; }''')
    replace(app/'core/src/Application.cpp',
        '''        IPlaybackController* pb = app.getPlaybackController();
        bool active = pb && pb->isActive();''',
        '''        IPlaybackController* pb = app.getPlaybackController();
        // An audio/quality reopen temporarily stops the decoder, not the session.
        // Do not read its changing clocks or reopen the browser until joined.
        if (auto* sm = app.getScreenManager()) {
            if (sm->getCurrentScreenId() == ScreenId::AudioTrackPicker &&
                static_cast<AudioTrackPickerScreen*>(sm->getCurrentScreen())->isSwitchingTracks())
                return;
        }
        bool active = pb && pb->isActive();''')


def patch_worker_start(app):
    """Unwind only successfully created workers when a partial start fails."""
    controller = app/'core/src/services/PlaybackController.cpp'
    text = controller.read_text()
    start = text.index('    // Start background worker threads')
    end = text.index('\n    m_playbackFsm.postEvent(PlaybackEvent::Play);', start)
    block = '''    // Running flags double as join ownership: never mark an uncreated worker.
    demux_thread_running = video_thread_running = 0;
    audio_decode_thread_running = audio_thread_running = 0;
'''
    for name, function, condition in (
        ('demux', 'demux_thread_func', 'true'),
        ('video', 'video_decode_thread_func', 'video_stream_index >= 0'),
        ('audio_decode', 'audio_decode_thread_func', 'audio_ctx != nullptr'),
        ('audio', 'audio_output_thread', 'audio_handle >= 1')):
        block += f'''    if ({condition}) {{
        {name}_thread_running = 1;
'''
        if name == 'video': block += '        video_thread_exited = 0;\n'
        block += f'''        const int rc = evo_thread_create(&{name}_thread, {function}, nullptr);
        evo_boot_log("playback worker start: kind={name} rc=%d", rc);
        if (rc != 0) {{
            {name}_thread_running = 0;
            stopPlayback();
            return false;
        }}
    }}
'''
    controller.write_text(text[:start] + block + text[end:])
