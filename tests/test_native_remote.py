"""Execute the adapted EVO input block and real PlayerScreen handler on a host.

Only Sce I/O and service side effects are faked. No console/network access.
Pinned upstream files come from the existing verified source archive, not a
generated working tree. Missing source archive is an explicit skipped check.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import native_remote


def function(source, signature):
    start = source.index(signature)
    body = source.index('{', start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


PREAMBLE = r'''
#include <cassert>
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <cstdlib>
#include <string>
#include <vector>
#include <algorithm>
#include "evo_input.h"
static uint64_t clockMs = 1000;
long long now_ms() { return clockMs; }
uint64_t NowMs() { return clockMs; }
static bool browser = false, keyboard = false;
bool evo_webui_active() { return browser; }
bool evo_keyboard_is_open() { return keyboard; }
static int keyboardCalls = 0, keyboardUpdates = 0;
void evo_keyboard_update() { ++keyboardUpdates; }
void evo_keyboard_handle_input(uint32_t) { ++keyboardCalls; }
bool evo_keyboard_wants_r3() { return false; }
uint32_t evo_usb_remote_take_buttons() { return 0; }
template<class... T> void toast(T...) {}
template<class... T> void EVO_LOGI(T...) {}
template<class... T> void evo_boot_log(T...) {}
void evo_boot_log_flush() {}
void evo_feedback(int) {}
enum { EVO_FB_CONFIRM, EVO_FB_CANCEL, EVO_FB_BOUNDARY, EVO_FB_MOVE };
bool evo_capture_screenshot(std::string&) { assert(false); return false; }
void notifyOnScreen(const char*) { assert(false); }
bool g_upd_card_wanted = false;
bool toast_is_sticky() { return false; }
void toast_dismiss() {}
void evo_updater_download() { assert(false); }
void settingsFocusUpdateRow() {}
namespace evo { namespace animation {
struct AnimationManager {
    static AnimationManager& getInstance() { static AnimationManager a; return a; }
    void triggerTransition(double) {}
};
}}
'''

MOCKS = r'''
static PS5_PadData controllerState{}, remoteState{};
static bool controllerOk = true, remoteOk = true;
static int opens = 0, gets = 0, remoteReads = 0, controllerReads = 0, closes = 0;
static int openResult = 2, getResult = 2;
extern "C" int scePadOpen(int user, int port, int index, void* arg) {
    assert(user == 0xff && port == 16 && index == 0 && !arg); ++opens; return openResult;
}
extern "C" int scePadGetHandle(int user, int port, int index) {
    assert(user == 0xff && port == 16 && index == 0); ++gets; return getResult;
}
extern "C" int scePadClose(int handle) { assert(handle == 2); ++closes; return 0; }
extern "C" int scePadReadState(int handle, PS5_PadData* state) {
    if (handle == 1) {
        ++controllerReads; *state = controllerState;
        return controllerOk ? 0 : -1;
    }
    assert(handle == 2); ++remoteReads; *state = remoteState; return remoteOk ? 0 : -1;
}
namespace evo {
enum class ScreenId { Player, Browser, ExitConfirm, MediaInfo, ChapterPicker,
                      SubtitlePicker, AudioTrackPicker, SettingsSystem };
enum class ViewMode { Fit, Fill, Stretch };
struct Playback {
    int toggles = 0, chapters = 0, seeks = 0, holdUpdates = 0;
    uint32_t lastHold = 0;
    bool paused = false, live = false;
    double scrub = 0;
    void updateScrubHold(uint32_t held) { ++holdUpdates; lastHold = held; }
    void togglePause() { ++toggles; paused = !paused; }
    bool isPaused() { return paused; }
    bool isLiveSource() { return live; }
    bool isScrubbing() { return false; }
    void jumpChapter(int n) { chapters += n; }
    void moveScrub(double n) { ++seeks; scrub += n; }
    int getSource() { return 0; }
    void cycleViewMode() {}
    ViewMode getViewMode() { return ViewMode::Fit; }
};
struct Metadata { int getChapterCount() { return 0; } };
struct PlayerScreen {
    uint64_t m_controlsLastUsedMs = 0, m_lastPlayPauseToggleMs = 0;
    bool m_showStatsForNerds = false;
    void toggleStatsForNerds() { m_showStatsForNerds = !m_showStatsForNerds; }
    bool handleInput(uint32_t pressed, uint32_t held, uint32_t released);
};
struct ScreenManager {
    ScreenId id = ScreenId::Player, navigated = ScreenId::Player;
    PlayerScreen player;
    int calls = 0;
    uint32_t lastPressed = 0, lastHeld = 0, lastReleased = 0;
    ScreenId getCurrentScreenId() { return id; }
    void navigateTo(ScreenId value) { navigated = value; }
    void handleInput(uint32_t p, uint32_t h, uint32_t r) {
        ++calls; lastPressed = p; lastHeld = h; lastReleased = r;
        if (id == ScreenId::Player) player.handleInput(p, h, r);
    }
};
static Playback playback;
static ScreenManager manager;
static Metadata metadata;
struct Application {
    static Application& getInstance() { static Application app; return app; }
    Playback* getPlaybackController() { return &playback; }
    ScreenManager* getScreenManager() { return &manager; }
    Metadata* getMediaMetadataService() { return &metadata; }
};
}
static int subtitleToggles = 0, prospero_subtitle_enabled = 0;
void prospero_subtitle_toggle() { ++subtitleToggles; }
void prospero_subtitle_nudge_delay(int) {}
bool skip_press(evo::Playback*, int, uint64_t) { return false; }
evo_input evo_pad_state{};
'''

CASES = r'''
using namespace evo;
using namespace evo::PadButtons;
static bool useBaseline = false;
struct Fixture {
    PS5_PadData padData{};
    uint32_t lastButtons = 0, m_padButtons = 0;
    int m_padHandle = 1;
    bool m_touchActive = false;
    float m_touchX = 0, m_touchY = 0;
    float m_leftStickX = 0, m_leftStickY = 0, m_rightStickX = 0, m_rightStickY = 0;
    ScreenManager* m_screenManager = &manager;
    Metadata* m_mediaMetadataService = &metadata;
    Fixture() {
        controllerState.leftStick.x = controllerState.leftStick.y = 128;
        controllerState.rightStick.x = controllerState.rightStick.y = 128;
        remoteState.connected = 1;
    }
    void frame(uint64_t now);
    void baselineFrame(uint64_t now);
};

void baseline_remote_only() {
    Fixture f; f.m_padHandle = -1;
    remoteState.buttons = Cross; f.baselineFrame(1000);
    remoteState.buttons = Right; f.baselineFrame(1300);
    assert(playback.toggles == 0 && playback.seeks == 0 && manager.calls == 0 && remoteReads == 0);
    // Even a working, idle DualSense does not make the baseline poll CEC.
    f.m_padHandle = 1; remoteState.buttons = Cross; f.baselineFrame(1500);
    assert(playback.toggles == 0 && manager.calls == 0 && remoteReads == 0 && controllerReads == 1);
}

void remote_only() {
    Fixture f; f.m_padHandle = -1;
    remoteState.buttons = Cross; f.frame(1000);
    assert(playback.toggles == 1 && manager.calls == 1 && controllerReads == 0 && remoteReads == 1);
    assert(manager.lastPressed == Cross && f.m_leftStickX == 0 && f.m_rightStickY == 0 && !f.m_touchActive);
    f.frame(1200); assert(playback.toggles == 1);
    remoteState.buttons = 0; f.frame(1210); assert(manager.lastReleased == Cross);
    remoteState.buttons = Right; f.frame(1300);
    assert(playback.seeks == 1 && playback.scrub == 10);
    f.frame(1519); assert(playback.seeks == 1);
    f.frame(1520); assert(playback.seeks == 2); // Actual EVO 220 ms repeat boundary.
    remoteState.buttons = Circle; f.frame(1600);
    assert(manager.navigated == ScreenId::ExitConfirm);
}

void failed_controller() {
    Fixture f; controllerOk = false;
    // A failing Sce read may still scribble data; it must not leak into input.
    controllerState.buttons = L3; controllerState.touchData.touchNum = 1;
    controllerState.leftStick.x = controllerState.leftStick.y = 0;
    remoteState.buttons = Cross; f.frame(1000);
    assert(playback.toggles == 1 && manager.lastPressed == Cross && !f.m_touchActive);
    assert(f.m_leftStickX == 0 && f.m_leftStickY == 0 && f.m_rightStickX == 0 && f.m_rightStickY == 0);
}

void overlap() {
    Fixture f;
    controllerState.buttons = Cross; remoteState.buttons = Cross; f.frame(1000);
    assert(playback.toggles == 1 && manager.calls == 1);
    controllerState.buttons = 0; f.frame(1200);
    assert(playback.toggles == 1 && f.lastButtons == Cross);
    controllerState.buttons = Cross; remoteState.buttons = 0; f.frame(1400);
    assert(playback.toggles == 1 && f.lastButtons == Cross);
    controllerState.buttons = 0; f.frame(1500); assert(manager.lastReleased == Cross);
    remoteState.buttons = Cross; f.frame(1700); assert(playback.toggles == 2);
}

void asymmetric_directions() {
    Fixture f; manager.id = ScreenId::Browser;
    controllerState.buttons = Up; f.frame(1000);
    assert(manager.lastPressed == Up);
    remoteState.buttons = Right; f.frame(1100);
    assert(manager.lastPressed == Right && manager.lastHeld == (Up | Right));
    f.frame(1220); assert(manager.lastPressed == Up);
    f.frame(1320); assert(manager.lastPressed == (Up | Right));
    remoteState.buttons = 0; f.frame(1330);
    assert(manager.lastReleased == Right && manager.lastHeld == Up);
    controllerState.buttons = 0; f.frame(1340); assert(manager.lastReleased == Up);
}

void disconnect() {
    Fixture f; remoteState.buttons = Right; f.frame(1000);
    assert(playback.seeks == 1);
    remoteState.connected = 0; f.frame(1100);
    assert(manager.lastReleased == Right && f.lastButtons == 0);
    remoteState.connected = 1; f.frame(1400); // Still held on reconnection: no ghost action.
    assert(playback.seeks == 1);
    remoteState.buttons = 0; f.frame(1410);
    remoteState.buttons = Right; f.frame(1420); assert(playback.seeks == 2);
    remoteOk = false; f.frame(1430);
    assert(closes == 1 && manager.lastReleased == Right);
    const int reads = remoteReads; f.frame(2000);
    assert(opens == 1 && remoteReads == reads);
    remoteOk = true; remoteState.buttons = 0; f.frame(2430); assert(opens == 2);
    remoteState.buttons = Cross; f.frame(2600); assert(playback.toggles == 1);
}

void acquisition() {
    Fixture f; openResult = -123;
    controllerState.buttons = Cross; f.frame(1000);
    assert(playback.toggles == 1 && opens == 1 && gets == 0 && remoteReads == 0);
    f.frame(1999); assert(opens == 1);
    openResult = static_cast<int>(0x80920004u); getResult = -1; f.frame(2000);
    assert(opens == 2 && gets == 1 && closes == 0);
    getResult = 2; f.frame(3000); assert(opens == 3 && gets == 2 && remoteReads == 1);
    s_nuvioRemote.shutdown(); s_nuvioRemote.shutdown(); assert(closes == 0);
}

void browser_ownership() {
    Fixture f; remoteState.buttons = Cross; f.frame(1000);
    assert(playback.toggles == 1);
    const int reads = remoteReads;
    browser = true; f.frame(1100); f.frame(1500);
    assert(closes == 1 && remoteReads == reads && opens == 1 && playback.toggles == 1);
    // Ordinary controller is still read and remains browser-owned.
    controllerState.buttons = Cross; f.frame(1700);
    assert(playback.toggles == 1 && controllerReads == 4);
    controllerState.buttons = 0; browser = false; f.frame(1900);
    assert(opens == 2 && playback.toggles == 1); // Held across browser return is suppressed.
    remoteState.buttons = 0; f.frame(1910);
    remoteState.buttons = Cross; f.frame(2100); assert(playback.toggles == 2);
    s_nuvioRemote.shutdown(); s_nuvioRemote.shutdown(); assert(closes == 2);
}

void remote_codes() {
    Fixture f; f.m_padHandle = -1;
    remoteState.unknown[3] = 45; f.frame(1000); assert(playback.toggles == 1);
    f.frame(1400); assert(playback.toggles == 1);
    remoteState.unknown[3] = 0; f.frame(1410);
    remoteState.unknown[3] = 23; f.frame(1500); assert(playback.scrub == -10);
    remoteState.unknown[3] = 24; f.frame(1600); assert(playback.scrub == 0);
    remoteState.unknown[3] = 20; f.frame(1700); assert(playback.chapters == -1);
    remoteState.unknown[3] = 21; f.frame(1800); assert(playback.chapters == 0);
    remoteState.unknown[3] = 25; f.frame(1900); assert(manager.navigated == ScreenId::ExitConfirm);
    remoteState.unknown[3] = 0; f.frame(1910);
    remoteState.unknown[3] = 18; f.frame(2000); assert(manager.player.m_showStatsForNerds);
    remoteState.unknown[3] = 0; f.frame(2010);
    remoteState.unknown[3] = 13; f.frame(2200); assert(playback.toggles == 2);
    remoteState.unknown[3] = 15; f.frame(2300); assert(manager.lastPressed == Circle);
    remoteState.unknown[3] = 0; f.frame(2310);
    const int calls = manager.calls;
    for (int code : {22, 26, 255}) { remoteState.unknown[3] = code; f.frame(2500 + code); }
    remoteState.buttons = L3 | R3 | Triangle; f.frame(3000);
    assert(manager.calls == calls); // No guessed mappings or screenshot bits.
}

void keyboard_and_nonplayer() {
    Fixture f; keyboard = true;
    remoteState.unknown[3] = 45; f.frame(1000); assert(keyboardCalls == 0);
    remoteState.unknown[3] = 13; f.frame(1100);
    assert(keyboardCalls == 1 && playback.toggles == 0);
    keyboard = false; remoteState.unknown[3] = 0; f.frame(1200);
    manager.id = ScreenId::Browser;
    remoteState.unknown[3] = 23; f.frame(1300);
    assert(manager.lastPressed != Left && playback.seeks == 0);
    remoteState.unknown[3] = 43; f.frame(1400); assert(manager.lastPressed == Circle);
}

void controller_unchanged() {
    Fixture f;
    controllerState.buttons = Right; f.frame(1000); assert(playback.scrub == 10);
    f.frame(1219); assert(playback.scrub == 10);
    f.frame(1220); assert(playback.scrub == 20);
    controllerState.buttons = 0; f.frame(1250); assert(manager.lastReleased == Right);
    controllerState.buttons = Cross; f.frame(1300); assert(playback.toggles == 1);
    f.frame(1800); assert(playback.toggles == 1);
    assert(opens == (useBaseline ? 0 : 1) && remoteReads == (useBaseline ? 0 : 6) && controllerReads == 6);
}
'''


class NativeRemoteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pin = next(p for p in json.loads((ROOT / 'deps.lock').read_text())['artifacts']
                   if p['id'] == 'evo-player-nuvio-source')
        archive = ROOT / '.cache' / pin['cache_file']
        if not archive.exists():
            raise unittest.SkipTest('Pinned EVO source archive absent; no network fetch during tests')
        if pin['commit'] != native_remote.EVO_COMMIT:
            raise AssertionError('Native remote adapter requires review for the changed EVO pin')
        if hashlib.sha256(archive.read_bytes()).hexdigest() != pin['sha256']:
            raise AssertionError('Pinned EVO source archive checksum mismatch')
        with tarfile.open(archive) as tar:
            def read(path):
                matches = [name for name in tar.getnames() if name.endswith('/projects/evoplayer/' + path)]
                if len(matches) != 1:
                    raise AssertionError(path)
                return tar.extractfile(matches[0]).read().decode()
            application = read('core/src/Application.cpp')
            common = read('core/include/evo/Common.hpp')
            player = read('core/src/screens/PlayerScreen.cpp')
            input_h = read('ui/include/evo_input.h')
            input_c = read('ui/src/evo_input.c')
        cls.application = application
        adapted = native_remote.adapt_application(application)
        # Execute exactly the adapted input block, including all original
        # controller synthesis, repeat, ownership checks and screen dispatch.
        start = adapted.index('        // 1. Controller input & auto-repeat')
        end = adapted.index('\n\n        /*\n         * 2. Update animation engine', start)
        block = adapted[start:end]
        baseline_start = application.index('        // 1. Controller input & auto-repeat')
        baseline_end = application.index('\n\n        /*\n         * 2. Update animation engine', baseline_start)
        baseline_block = application[baseline_start:baseline_end]
        abi = adapted[adapted.index('typedef struct PS5_PadTouch {'):
                      adapted.index('\nextern pp_playback g_pp_pb;')]
        masks = function(common, 'namespace PadButtons {')
        handler = function(player, 'bool PlayerScreen::handleInput(')
        source = (PREAMBLE + '\nnamespace evo {\n' + masks + '\n}\nextern "C" {\n' + abi + '\n}\n' +
                  MOCKS + native_remote.RECEIVER + '\nnamespace evo {\n' + handler + '\n}\n' + CASES +
                  '\nvoid Fixture::frame(uint64_t now) {\n'
                  'if (useBaseline) { baselineFrame(now); return; }\nclockMs = now;\n' + block + '\n}\n' +
                  '\nvoid Fixture::baselineFrame(uint64_t now) { clockMs = now;\n' + baseline_block + '\n}\n' +
                  '''int main(int argc, char** argv) {
    assert(argc == 2);
    const std::string name = argv[1];
    if (name == "controller_baseline") {
        useBaseline = true; controller_unchanged(); puts("controller_baseline: passed"); return 0;
    }
''' + '\n'.join(f'    if (name == "{name}") {{ {name}(); puts("{name}: passed"); return 0; }}'
                 for name in ('baseline_remote_only', 'remote_only', 'failed_controller', 'overlap', 'asymmetric_directions',
                              'disconnect', 'acquisition', 'browser_ownership', 'remote_codes',
                              'keyboard_and_nonplayer', 'controller_unchanged')) + '\n    return 2;\n}\n')
        # The orb's target Clang lacks host ASan runtimes. GCC ships them.
        compiler = shutil.which('g++') or shutil.which('clang++') or shutil.which('c++')
        if not compiler:
            raise unittest.SkipTest('C++ compiler unavailable')
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        directory = Path(cls.temp.name)
        (directory / 'evo_input.h').write_text(input_h)
        (directory / 'evo_input.cpp').write_text(input_c)
        (directory / 'test.cpp').write_text(source)
        cls.binary = directory / 'test'
        result = subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                 '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                                 '-I' + str(directory), str(directory / 'test.cpp'),
                                 str(directory / 'evo_input.cpp'), '-o', str(cls.binary)],
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def run_case(self, name):
        result = subprocess.run([str(self.binary), name], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(name + ': passed', result.stdout)

    def test_remote_only_reaches_actual_player_pause_seek_back_and_repeat(self):
        self.run_case('baseline_remote_only')
        self.run_case('remote_only')

    def test_failed_partial_controller_read_is_neutral(self):
        self.run_case('failed_controller')

    def test_same_button_overlap_has_one_edge_until_both_release(self):
        self.run_case('overlap')

    def test_asymmetric_controller_remote_directions_repeat_and_release(self):
        self.run_case('asymmetric_directions')

    def test_disconnect_and_read_failure_release_and_recover(self):
        self.run_case('disconnect')

    def test_acquisition_backoff_borrowed_handle_and_controller_independence(self):
        self.run_case('acquisition')

    def test_browser_retains_ownership_and_held_keys_are_not_replayed(self):
        self.run_case('browser_ownership')

    def test_source_backed_remote_codes_reuse_player_actions(self):
        self.run_case('remote_codes')

    def test_keyboard_navigation_and_transport_scope(self):
        self.run_case('keyboard_and_nonplayer')

    def test_ordinary_controller_edges_and_repeat_remain_unchanged(self):
        self.run_case('controller_baseline')
        self.run_case('controller_unchanged')

    def test_patch_fails_closed_and_writes_nothing_on_drift(self):
        adapted = native_remote.adapt_application(self.application)
        with self.assertRaises(RuntimeError):
            native_remote.adapt_application(adapted)
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)
            path = app / 'core/src/Application.cpp'
            path.parent.mkdir(parents=True)
            drifted = self.application.replace('    m_shutdownDone = true;', '    changed();')
            path.write_text(drifted)
            with self.assertRaises(RuntimeError):
                native_remote.patch_native(app)
            self.assertEqual(path.read_text(), drifted)
            path.write_text(self.application)
            native_remote.patch_native(app)
            self.assertEqual(path.read_text(), adapted)


if __name__ == '__main__':
    unittest.main()
