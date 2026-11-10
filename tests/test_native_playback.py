"""Execute the pinned playback startup code with controlled creation failures."""
from pathlib import Path
import sys
import tempfile
import unittest

from tests.test_native_subtitles import compile_run, source_file

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import native_playback
import polish


class NativePlaybackTests(unittest.TestCase):
    def test_track_reopen_preserves_browser_session_until_worker_is_joined(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            for relative in ('src/evo_webui.c', 'include/evo_webui.h', 'core/src/Application.cpp',
                             'core/src/services/PlaybackController.cpp',
                             'core/include/evo/screens/AudioTrackPickerScreen.hpp'):
                path = app / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source_file(relative))
            polish.patch_playback_start(app)
            polish.patch_playback_progress(app)
            native_playback.patch_track_reopen(app)
            application = (app / 'core/src/Application.cpp').read_text()
            header = (app / 'core/include/evo/screens/AudioTrackPickerScreen.hpp').read_text()
            busy = next(line for line in header.splitlines() if 'bool isSwitchingTracks()' in line)
        start = application.index('    } else {\n        IPlaybackController* pb = app.getPlaybackController();',
                                  application.index('void webui_playback_pump() {'))
        body = application[start + len('    } else {\n'):].split('\n    }\n}', 1)[0]
        harness = r'''
#include <atomic>
#include <cassert>
#include <initializer_list>
static int ended, sampled, phase = 2, frames;
static bool seen_active = true;
struct IPlaybackController {
    bool active = true;
    bool isActive() const { return active; }
    bool isScrubbing() const { return false; }
    double getPositionSeconds() const { return 1112.963; }
    double getDurationSeconds() const { return 2000; }
};
enum class ScreenId { Player, AudioTrackPicker };
struct AudioTrackPickerScreen {
    bool m_threadLive = false;
    std::atomic<int> m_switchState{0};
''' + busy + r'''
};
struct ScreenManager {
    ScreenId current = ScreenId::AudioTrackPicker;
    AudioTrackPickerScreen picker;
    ScreenId getCurrentScreenId() const { return current; }
    AudioTrackPickerScreen* getCurrentScreen() { return &picker; }
};
struct Application {
    ScreenManager screens;
    IPlaybackController playback;
    ScreenManager* getScreenManager() { return &screens; }
    IPlaybackController* getPlaybackController() { return &playback; }
};
static struct { bool on = true; double lastPos = 1112.963; int frames = 0; } g_web_rep;
static void web_report(const char*, double) {}
static void evo_webui_progress_sample(double position, double duration) {
    assert(position == 1112.963 && duration == 2000); ++sampled;
}
static void evo_webui_playback_ended(int played) { assert(played); ++ended; }
static void pump(Application& app) {
''' + body + r'''
}
int main() {
    for (int result : {2, 3}) {
        Application app;
        phase = 2; frames = ended = sampled = 0; seen_active = true;
        g_web_rep.on = true;
        // The real picker marks the worker owned before the next main-loop pump.
        app.screens.picker.m_threadLive = true;
        app.screens.picker.m_switchState = 1;
        for (bool active : {false, true, false, true}) {
            app.playback.active = active;
            for (int i = 0; i < 650; ++i) pump(app);
            assert(ended == 0 && sampled == 0 && phase == 2 && g_web_rep.on);
        }
        // Worker completion is not enough: wait for the UI to join it as well.
        app.playback.active = result == 2;
        app.screens.picker.m_switchState = result;
        pump(app);
        assert(ended == 0 && sampled == 0 && phase == 2);
        app.screens.picker.m_threadLive = false;
        app.screens.current = ScreenId::Player;
        pump(app);
        if (result == 2) {
            assert(ended == 0 && sampled == 1 && phase == 2 && g_web_rep.on);
            app.playback.active = false; // An ordinary later stop still returns.
            pump(app);
        }
        assert(ended == 1 && phase == 0 && !g_web_rep.on);
    }
    // Merely opening the picker must not mask an ordinary playback stop.
    Application app;
    app.playback.active = false;
    phase = 2; ended = 0;
    pump(app);
    assert(ended == 1 && phase == 0);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            compile_run(harness, tmp, cpp=True)

    def test_next_episode_policy_does_not_outlive_browser_playback(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            for relative in ('src/evo_webui.c', 'include/evo_webui.h', 'core/src/Application.cpp',
                             'core/src/services/PlaybackController.cpp', 'core/src/screens/PlayerScreen.cpp',
                             'core/include/evo/screens/PlayerScreen.hpp', 'ui_rml/include/evo_rmlui_bridge.h',
                             'ui_rml/include/evo_rmlui_app.h', 'ui_rml/src/evo_rmlui_bridge.cpp',
                             'ui_rml/src/evo_rmlui_app.cpp', 'assets/rml/playback.rml', 'assets/rml/playback.rcss'):
                path = app / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source_file(relative))
            polish.patch_playback_start(app)
            polish.patch_playback_progress(app)
            polish.patch_playback_skip(app)
            polish.patch_next_episode(app)
            web = (app / 'src/evo_webui.c').read_text()
            ended = web.split('void evo_webui_playback_ended(int played)\n{', 1)[1].split('\n}', 1)[0]
            player = (app / 'core/src/screens/PlayerScreen.cpp').read_text()
            wrapper = player.split('int PlayerScreen::nextEpisode(int action) const {', 1)[1].split('\n}', 1)[0]
            harness = r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <pthread.h>
#define LOG(...) ((void)0)
#define P_PLAYING 1
#define P_WAIT 2
#define OPEN_DELAY_FRAMES 120
using std::isfinite;
static int s_state = P_PLAYING, s_frames, s_progress_finished;
static uint64_t s_progress_revision;
static pthread_mutex_t s_mx = PTHREAD_MUTEX_INITIALIZER;
static int s_progress_next_episode, s_progress_return_detail;
static struct { int type; double start, end; } s_skip[4];
static void query_param(const char *p, const char*, char *out, size_t cap) { snprintf(out,cap,"%s",p); }
''' + (native_playback.HERE / 'ps5-next.c').read_text() + r'''
static void evo_webui_playback_ended(int played) {
    (void)played;
''' + ended + r'''
}
struct Playback {
    bool isActive() const { return true; }
    bool isMusicMode() const { return false; }
    bool isLiveSource() const { return false; }
    bool isScrubbing() const { return false; }
    bool isPaused() const { return false; }
    double getPositionSeconds() const { return 995; }
    double getDurationSeconds() const { return 1000; }
};
struct Application {
    static Application& getInstance() { static Application app; return app; }
    Playback* getPlaybackController() { static Playback playback; return &playback; }
};
static int native_requested;
static struct { int seek_discarding; } g_pp_pb;
static int video_frame_loaded = 1, pb_prebuffer_hold;
static int evo_webui_native_requested() { return native_requested; }
static int evo_pb_is_eof() { return 0; }
static int evo_pb_decode_fatal() { return 0; }
static int evo_pb_is_paused() { return 0; }
static uint64_t NowMs() { return 1000; }
struct PlayerScreen {
    bool m_showStatsForNerds = false;
    bool readerStalled() const { return false; }
    int nextEpisode(int action = 0) const {
''' + wrapper + r'''
    }
};
int main() {
    PlayerScreen player;
    assert(!evo_webui_native_requested());
    for (int launch : {0, 1}) {
        native_requested = 0;
        playback_next_parse("1,0,p,0.99"); s_play_next = s_h_next; playback_next_begin();
        if (launch) assert(player.nextEpisode() == -2);
        evo_webui_playback_ended(1);
        // No new browser handoff: a native source must not inherit actions.
        assert(evo_webui_next_episode(995,1000,5000,1,1,0) == 0);
        native_requested = 1;
        assert(player.nextEpisode() == 0);
    }
    // Native exclusion also applies before an explicit teardown reset.
    playback_next_parse("1,0,p,0.99"); s_play_next = s_h_next; playback_next_begin();
    assert(player.nextEpisode() == 0);
    native_requested = 0;
    assert(player.nextEpisode() == -2); // New Nuvio policy remains functional.
}
'''
            compile_run('#include <initializer_list>\n' + harness, tmp, cpp=True, extra_flags=['-pthread'])

    def test_rejected_or_cancelled_seek_preserves_measured_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            for relative in ('media/src/evo_audio_out.c', 'media/include/evo_audio_out.h',
                             'media/src/evo_demux.c', 'core/src/services/PlaybackController.cpp',
                             'core/src/Application.cpp', 'core/include/evo/screens/AudioTrackPickerScreen.hpp'):
                path = app / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source_file(relative))
            native_playback.patch_native(app)
            controller = (app / 'core/src/services/PlaybackController.cpp').read_text()
            getter = controller.split('double PlaybackController::getPositionSeconds() const {', 1)[1].split('\n}', 1)[0]
            seek = controller.split('void PlaybackController::seekTo(double targetSeconds) {', 1)[1].split('\n}', 1)[0]
            demux = (app / 'media/src/evo_demux.c').read_text()
            cancel = demux.split('    /* Never flush a live decoder', 1)[1].split('    /*\n     * Clear EOF', 1)[0]
            cancel = '    /* Never flush a live decoder' + cancel
            commit = demux.split('        resume_base_offset_seconds =\n', 1)[1].split('\n\n', 1)[0]
            commit = '        resume_base_offset_seconds =\n' + commit
            harness = r'''
#include <cassert>
#include <cstdint>
static double resume_base_offset_seconds, resume_base_anchor_pending, elapsed;
static int g_pp_pb, accepted, audio_parked, video_thread_running, video_decode_parked;
static int prospero_seek_in_progress, video_decode_hold, player_paused;
static double evo_pb_position_s() { return elapsed; }
static int prospero_request_inplace_seek(double, int) { return accepted; }
static int evo_audio_seek_begin() { return audio_parked; }
static void evo_boot_log(const char*, ...) {}
static void pp_stage_bc(const char*, const char*) {}
static void pp_playback_resume(int*) {}
static void pp_playback_notify_seek_begin(int*, int64_t) {}
static void pp_playback_notify_seek_end(int*, int, int, int) {}
struct PlaybackController {
    double m_resumeBaseOffset = 0, m_scrubTargetSeconds = 0;
    bool isActive() const { return true; }
    bool isScrubbing() const { return false; }
    double getPositionSeconds() const {
''' + getter + r'''
    }
    void seekTo(double targetSeconds) {
''' + seek + r'''
    }
};
static int process(double target_seconds, int restore_paused) {
''' + cancel + commit + r'''
    elapsed = 0; // The successful reset starts a new relative clock.
    return 1;
}
int main() {
    PlaybackController player;
    for (double target : {200.0, 1500.0}) {
        resume_base_offset_seconds = 1000; elapsed = 80;
        accepted = 0;
        player.seekTo(target);
        assert(player.getPositionSeconds() == 1080); // Request rejected.
        accepted = 1;
        for (int video : {0, 1}) for (int paused : {0, 1}) {
            video_thread_running = 1; video_decode_parked = video;
            audio_parked = 0;
            player.seekTo(target);
            assert(!process(target, paused)); // Video or audio worker timeout.
            assert(player.getPositionSeconds() == 1080);
            assert(player_paused == paused);
        }
        audio_parked = video_decode_parked = 1;
        player.seekTo(target);
        assert(process(target, 0));
        assert(player.getPositionSeconds() == target);
        elapsed = 7;
        assert(player.getPositionSeconds() == target + 7);
    }
}
'''
            compile_run('#include <initializer_list>\n' + harness, tmp, cpp=True)

    def test_worker_creation_failure_unwinds_and_allows_retry(self):
        original = source_file('core/src/services/PlaybackController.cpp')
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp)
            controller = app / 'core/src/services/PlaybackController.cpp'
            controller.parent.mkdir(parents=True)
            controller.write_text(original)
            native_playback.patch_worker_start(app)
            adapted = controller.read_text()
            start = adapted.index('    // Running flags double as join ownership:')
            end = adapted.index('\n    m_playbackFsm.postEvent(PlaybackEvent::Play);', start)
            block = adapted[start:end]
            harness = r'''
#include <cassert>
#include <cerrno>
#include <cstdarg>
#include <set>
static int demux_thread_running, video_thread_running;
static int audio_decode_thread_running, audio_thread_running, video_thread_exited;
static int demux_thread, video_thread, audio_decode_thread, audio_thread;
static int video_stream_index=0, audio_handle=1;
static void *audio_ctx=(void*)1;
static int attempt, fail_at, next_id;
static std::set<int> live;
static void *demux_thread_func(void*) {return nullptr;}
static void *video_decode_thread_func(void*) {return nullptr;}
static void *audio_decode_thread_func(void*) {return nullptr;}
static void *audio_output_thread(void*) {return nullptr;}
static int evo_thread_create(int *id, void *(*)(void*), void*) {
    if (++attempt==fail_at) return EAGAIN;
    *id=++next_id;
    live.insert(*id);
    return 0;
}
static void evo_boot_log(const char*, ...) {}
static void stopPlayback() {
    // Model joinable resource ownership, including invalid/double joins.
    for(auto pair : {std::pair<int*,int>{&demux_thread_running,demux_thread},
                    {&video_thread_running,video_thread},
                    {&audio_decode_thread_running,audio_decode_thread},
                    {&audio_thread_running,audio_thread}}) {
        if (*pair.first) {assert(live.erase(pair.second)==1); *pair.first=0;}
    }
}
static bool startPlayback() {
''' + block + r'''
    return true;
}
int main() {
    for(int failure=1; failure<=4; ++failure) {
        attempt=0; fail_at=failure;
        assert(!startPlayback());
        assert(live.empty());
        // The same controller must support opening another stream after error.
        attempt=0; fail_at=0;
        assert(startPlayback());
        assert(live.size()==4);
        stopPlayback(); assert(live.empty());
    }
    // Missing streams must not leave an uncreated worker marked joinable.
    for(int streams : {0,1,2,3}) {
        video_stream_index=(streams & 1) ? 0 : -1;
        audio_ctx=(streams & 2) ? (void*)1 : nullptr;
        audio_handle=(streams & 2) ? 1 : -1;
        attempt=0; assert(startPlayback());
        assert(live.size()==1u+((streams & 1) ? 1u : 0u)+((streams & 2) ? 2u : 0u));
        stopPlayback(); assert(live.empty());
    }
}
'''
            compile_run(harness, tmp, cpp=True)


if __name__ == '__main__':
    unittest.main()
