"""Add an independent native HDMI-CEC remote receiver to pinned EVO 0.13.5.

Source: ps5-payload-dev/SDL ee4c47dc0d617b3bc8f35108f9956baf228a1322.
src/joystick/ps5/SDL_ps5joystick.h SHA-256:
16436774be2082a3fa4fd6ca4e9792ce45bbfcac64de676d5a56a7b0e6f1a706
src/video/ps5/SDL_ps5remote.c SHA-256:
d0aac6bf7abc4a970b9199265b86e40d940502f6b10d179f9fc3a9c93bc1d85a
Both files were read at that exact revision, not inferred from symbol names.
The code table is remote_key_map in that SDL file. Indexes SDL marks unknown
stay unmapped. This module does not invent codes.
SDK v0.43 supplies scePadOpen/GetHandle/ReadState/Close link stubs.
The source contract is not evidence of execution on the owner's firmware.
"""
from pathlib import Path


EVO_COMMIT = 'f6e43e6561796630673f1e20eb1eb67d6428514c'
SDL_COMMIT = 'ee4c47dc0d617b3bc8f35108f9956baf228a1322'
LEARN_PATH = '/data/nuvio/remote-learn'
LEARN_USB_PATH = '/mnt/usb0/evo_remote_learn'
MAP_PATH = '/data/nuvio/remote-map'
MENU_HOLD_MS = 700

# status: sourced = SDL names the key. unknown = SDL says the index is unknown.
# action none leaves a sourced key visible to the learner and does not guess.
# player_only matches the transport keys that already stay out of menus.
REMOTE_KEYS = (
    # code, sdl label, status, action, player_only, arg
    (0, 'none', 'unknown', 'none', False, 0),
    (1, '1', 'sourced', 'seek', True, 10),
    (2, '2', 'sourced', 'seek', True, 20),
    (3, '3', 'sourced', 'seek', True, 30),
    (4, '4', 'sourced', 'seek', True, 40),
    (5, '5', 'sourced', 'seek', True, 50),
    (6, '6', 'sourced', 'seek', True, 60),
    (7, '7', 'sourced', 'seek', True, 70),
    (8, '8', 'sourced', 'seek', True, 80),
    (9, '9', 'sourced', 'seek', True, 90),
    (10, '0', 'sourced', 'seek', True, 0),
    (11, '11', 'sourced', 'none', False, 0),
    (12, '12', 'sourced', 'none', False, 0),
    (13, 'return', 'sourced', 'cross', False, 0),
    (14, 'unknown-14', 'unknown', 'none', False, 0),
    (15, 'back', 'sourced', 'circle', False, 0),
    (16, 'unknown-16', 'unknown', 'none', False, 0),
    (17, 'unknown-17', 'unknown', 'none', False, 0),
    (18, 'menu', 'sourced', 'options', False, 0),
    (19, 'unknown-19', 'unknown', 'none', False, 0),
    (20, 'previous', 'sourced', 'l1', True, 0),
    (21, 'next', 'sourced', 'r1', True, 0),
    (22, 'play', 'sourced', 'play', True, 0),
    (23, 'rewind', 'sourced', 'left', True, 0),
    (24, 'fast-forward', 'sourced', 'right', True, 0),
    (25, 'stop', 'sourced', 'circle', True, 0),
    (26, 'pause', 'sourced', 'pause', True, 0),
    (27, 'context-menu', 'sourced', 'options', False, 0),
    (28, 'unknown-28', 'unknown', 'none', False, 0),
    (29, 'unknown-29', 'unknown', 'none', False, 0),
    (30, 'subtitle', 'sourced', 'down', True, 0),
    (31, 'audio', 'sourced', 'r2', True, 0),
    (32, 'camera', 'sourced', 'none', False, 0),
    (33, 'display', 'sourced', 'wake', True, 0),
    (34, 'unknown-34', 'unknown', 'none', False, 0),
    (35, 'unknown-35', 'unknown', 'none', False, 0),
    (36, 'blue', 'sourced', 'r1', True, 0),
    (37, 'red', 'sourced', 'r2', True, 0),
    (38, 'green', 'sourced', 'down', True, 0),
    (39, 'yellow', 'sourced', 'triangle', True, 0),
    (40, 'period', 'sourced', 'none', False, 0),
    (41, 'channel-up', 'sourced', 'r1', False, 0),
    (42, 'channel-down', 'sourced', 'l1', False, 0),
    (43, 'prev', 'sourced', 'circle', False, 0),
    (44, 'guide', 'sourced', 'chapters', True, 0),
    (45, 'play-pause', 'sourced', 'cross', True, 0),
)

# Fallback list for a remote that only has D-pad, OK, Back and Menu.
# Each row reuses a button the player already handles.
MENU_ITEMS = (
    ('Subtitles', 'down'),
    ('Audio', 'r2'),
    ('Skip or view', 'triangle'),
    ('Next', 'r1'),
    ('Previous', 'l1'),
    ('Chapters', 'chapters'),
    ('Media info', 'square'),
    ('Subtitle earlier', 'l2'),
    ('Subtitle later', 'touch-right'),
)

ACTIONS = {
    'none': 0,
    'cross': 1,
    'circle': 2,
    'options': 3,
    'left': 4,
    'right': 5,
    'up': 6,
    'down': 7,
    'l1': 8,
    'r1': 9,
    'l2': 10,
    'r2': 11,
    'triangle': 12,
    'square': 13,
    'r3': 14,
    'touch-right': 15,
    'play': 16,
    'pause': 17,
    'seek': 18,
    'menu': 19,
    'wake': 20,
    'chapters': 21,
}

# Names accepted in /data/nuvio/remote-map. Seek percent is "seek" plus a number.
REMAP_NAMES = (
    ('none', 'none', 0),
    ('ok', 'cross', 0),
    ('back', 'circle', 0),
    ('menu', 'options', 0),
    ('subtitles', 'down', 0),
    ('audio', 'r2', 0),
    ('skip', 'triangle', 0),
    ('next', 'r1', 0),
    ('previous', 'l1', 0),
    ('chapters', 'chapters', 0),
    ('info', 'wake', 0),
    ('play', 'play', 0),
    ('pause', 'pause', 0),
    ('rewind', 'left', 0),
    ('forward', 'right', 0),
    ('earlier', 'l2', 0),
    ('later', 'touch-right', 0),
    ('actions', 'menu', 0),
)


def key_by_code(code):
    row = REMOTE_KEYS[code]
    if row[0] != code:
        raise RuntimeError('Remote table index drifted')
    return row


PAD_TAIL = '''    uint8_t connected;
    uint64_t timestamp;
    uint8_t ext[16];
    uint8_t count;
    uint8_t unknown[15];'''


def _table_cpp():
    lines = []
    for code, label, status, action, player_only, arg in REMOTE_KEYS:
        lines.append(
            '    {%d, %d, %d}, /* %s %s */' % (
                ACTIONS[action], 1 if player_only else 0, arg, label, status))
    return '\n'.join(lines)


def _remap_cpp():
    lines = []
    for name, action, arg in REMAP_NAMES:
        player = 0 if action in ('none', 'cross', 'circle', 'options') else 1
        lines.append('    {"%s", %d, %d, %d},' % (name, ACTIONS[action], arg, player))
    return '\n'.join(lines)


def _menu_cpp():
    lines = []
    for label, action in MENU_ITEMS:
        escaped = label.replace('\\', '\\\\').replace('"', '\\"')
        lines.append('    {%d, "%s"},' % (ACTIONS[action], escaped))
    return '\n'.join(lines)


RECEIVER = r'''
/* Native TV remote contract adapted from ps5-payload-dev/SDL, revision
 * ee4c47dc0d617b3bc8f35108f9956baf228a1322:
 * src/joystick/ps5/SDL_ps5joystick.h and src/video/ps5/SDL_ps5remote.c.
 * This is NOT Remote Play. No browser event is synthesized here.
 * Code indexes are remote_key_map in that file. Unknown indexes are not mapped.
 *
 * Simple DirectMedia Layer
 * Copyright (C) 1997-2024 Sam Lantinga <slouken@libsdl.org>
 *
 * This software is provided 'as-is', without any express or implied
 * warranty. In no event will the authors be held liable for any damages
 * arising from the use of this software.
 *
 * Permission is granted to anyone to use this software for any purpose,
 * including commercial applications, and to alter it and redistribute it
 * freely, subject to the following restrictions:
 * 1. The origin of this software must not be misrepresented; you must not
 *    claim that you wrote the original software. If you use this software
 *    in a product, an acknowledgment in the product documentation would be
 *    appreciated but is not required.
 * 2. Altered source versions must be plainly marked as such, and must not be
 *    misrepresented as being the original software.
 * 3. This notice may not be removed or altered from any source distribution.
 *
 * Altered for Nuvio: independent polling, owned/borrowed handle tracking,
 * browser suspension, failure backoff and native action translation only.
 */
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unistd.h>
#ifndef NUVIO_REMOTE_LEARN_PATH
#define NUVIO_REMOTE_LEARN_PATH "/data/nuvio/remote-learn"
#endif
#ifndef NUVIO_REMOTE_MAP_PATH
#define NUVIO_REMOTE_MAP_PATH "/data/nuvio/remote-map"
#endif
extern "C" int scePadGetHandle(int user_id, int type, int index);
extern "C" int scePadClose(int handle);
void toast(const char *title, const char *msg);
void toast_sticky(const char *title, const char *msg);
void toast_dismiss(void);

class NuvioTvRemote {
    static constexpr int SystemUser = 0xff;
    static constexpr int RemotePort = 16;
    static constexpr unsigned AlreadyOpened = 0x80920004u;
    static constexpr uint32_t WakeBit = 0x01000000u;
    static constexpr int ActPlay = 16;
    static constexpr int ActPause = 17;
    static constexpr int ActSeek = 18;
    static constexpr int ActMenu = 19;
    static constexpr int ActWake = 20;
    static constexpr int ActChapters = 21;
    struct Key { uint8_t act; uint8_t player; uint8_t arg; };
    struct Item { uint8_t act; const char *label; };
    struct Name { const char *name; uint8_t act; uint8_t arg; uint8_t player; };
    struct Saved { uint8_t used; uint8_t act; uint8_t arg; uint8_t player; };
    static const Key kKeys[46];
    static const Item kMenu[9];
    static const Name kNames[];
    static const int kNameCount;
    int handle = -1;
    bool owned = false;
    bool waitNeutral = false;
    uint64_t retryAt = 0;
    uint32_t previous = 0;
    int transport = 0;
    int seekPercent = -1;
    bool learn = false;
    bool learnKnown = false;
    uint64_t learnCheckAt = 0;
    uint8_t shownCode = 0;
    uint32_t shownButtons = 0;
    bool menuOpen = false;
    bool menuDirty = false;
    bool menuIgnoreSelect = false;
    int menuIndex = 0;
    bool holdingMenu = false;
    uint64_t menuDownAt = 0;
    uint32_t menuNav = 0;
    uint8_t bindCode = 0;
    Saved saved[256]{};
    uint64_t mapCheckAt = 0;
    bool openChapters = false;

    void detach() {
        if (owned && handle > 0) scePadClose(handle);
        handle = -1;
        owned = false;
    }

    void refreshLearn(uint64_t now) {
        if (now < learnCheckAt) return;
        learnCheckAt = now + 500;
        const bool on = access(NUVIO_REMOTE_LEARN_PATH, F_OK) == 0 ||
                        access("/mnt/usb0/evo_remote_learn", F_OK) == 0;
        if (learn && !on) toast_dismiss();
        if (on != learn) { shownCode = 0xff; shownButtons = 0xffffffffu; }
        learn = on;
        learnKnown = true;
        loadMap(now);
    }

    const char *nameFor(uint8_t act, uint8_t arg) const {
        if (act == ActSeek) return nullptr;
        for (int i = 0; i < kNameCount; ++i)
            if (kNames[i].act == act && kNames[i].arg == arg) return kNames[i].name;
        return nullptr;
    }

    void loadMap(uint64_t now) {
        if (now < mapCheckAt) return;
        mapCheckAt = now + 500;
        std::memset(saved, 0, sizeof saved);
        std::FILE *file = std::fopen(NUVIO_REMOTE_MAP_PATH, "r");
        if (!file) return;
        char line[64];
        while (std::fgets(line, sizeof line, file)) {
            if (line[0] == '#' || line[0] == '\n') continue;
            unsigned code = 0;
            char name[32] = {};
            if (std::sscanf(line, "%u %31s", &code, name) != 2 || code == 0 || code > 255)
                continue;
            if (std::strncmp(name, "seek", 4) == 0) {
                saved[code].used = 1;
                saved[code].act = ActSeek;
                saved[code].arg = static_cast<uint8_t>(std::atoi(name + 4));
                saved[code].player = 1;
                continue;
            }
            for (int i = 0; i < kNameCount; ++i) {
                if (std::strcmp(kNames[i].name, name) == 0) {
                    saved[code] = {1, kNames[i].act, kNames[i].arg, kNames[i].player};
                    break;
                }
            }
        }
        std::fclose(file);
    }

    void saveBind(uint8_t code, uint8_t act) {
        if (code == 0 || code == 13 || code == 15 || code == 18 || code == 43) return;
        saved[code].used = 1;
        saved[code].act = act;
        saved[code].arg = 0;
        saved[code].player = (act == 1 || act == 2 || act == 3) ? 0 : 1;
        std::FILE *file = std::fopen(NUVIO_REMOTE_MAP_PATH, "w");
        if (!file) return;
        std::fputs("# code action\n", file);
        for (int i = 1; i < 256; ++i) {
            if (!saved[i].used) continue;
            if (saved[i].act == ActSeek)
                std::fprintf(file, "%d seek%d\n", i, saved[i].arg);
            else if (const char *name = nameFor(saved[i].act, saved[i].arg))
                std::fprintf(file, "%d %s\n", i, name);
        }
        std::fclose(file);
        mapCheckAt = 0;
    }

    void showLearn(uint8_t code, uint32_t buttons) {
        if (!learn || menuOpen) return;
        if (code == shownCode && buttons == shownButtons) return;
        shownCode = code;
        shownButtons = buttons;
        char text[64];
        std::snprintf(text, sizeof text, "code %u buttons 0x%08x", code, buttons);
        toast_sticky("REMOTE", text);
    }

    void showMenu(uint8_t code) {
        char text[96];
        const int count = static_cast<int>(sizeof kMenu / sizeof kMenu[0]);
        if (learn)
            std::snprintf(text, sizeof text, "%d/%d %s code %u", menuIndex + 1, count,
                          kMenu[menuIndex].label, code);
        else
            std::snprintf(text, sizeof text, "%d/%d %s", menuIndex + 1, count,
                          kMenu[menuIndex].label);
        toast_sticky("REMOTE", text);
    }

    void openMenu() {
        if (menuOpen) return;
        menuOpen = true;
        menuIndex = 0;
        menuNav = 0;
        menuDirty = true;
        menuIgnoreSelect = true;
    }

    uint32_t maskFor(uint8_t act) const {
        using namespace evo::PadButtons;
        switch (act) {
            case 1: return Cross;
            case 2: return Circle;
            case 3: return Options;
            case 4: return Left;
            case 5: return Right;
            case 6: return Up;
            case 7: return Down;
            case 8: return L1;
            case 9: return R1;
            case 10: return L2;
            case 11: return R2;
            case 12: return Triangle;
            case 13: return Square;
            case 14: return R3;
            case 15: return TouchPadRight;
            case ActWake: return WakeBit;
            default: return 0;
        }
    }

    uint32_t menuFrame(uint8_t code, uint32_t basic) {
        using namespace evo::PadButtons;
        const int count = static_cast<int>(sizeof kMenu / sizeof kMenu[0]);
        const uint32_t nav = basic & (Up | Down | Cross | Circle);
        const uint32_t edge = nav & ~menuNav;
        menuNav = nav;
        if (menuIgnoreSelect && code != 13 && !(basic & Cross)) menuIgnoreSelect = false;
        const bool choose = !menuIgnoreSelect && ((code == 13) || (edge & Cross));
        const bool back = (code == 15) || (code == 43) || (edge & Circle);
        if (choose) {
            const uint8_t act = kMenu[menuIndex].act;
            if (learn) saveBind(bindCode, act);
            menuOpen = false;
            toast_dismiss();
            if (act == ActChapters) { openChapters = true; return previous = 0; }
            if (act == ActMenu) { openMenu(); return previous = 0; }
            return previous = maskFor(act);
        }
        if (back) {
            menuOpen = false;
            toast_dismiss();
            return previous = 0;
        }
        int next = menuIndex;
        if (edge & Up) next = (menuIndex + count - 1) % count;
        if (edge & Down) next = (menuIndex + 1) % count;
        if (next != menuIndex) {
            menuIndex = next;
            menuDirty = true;
        }
        if (menuDirty) {
            menuDirty = false;
            showMenu(code);
        }
        return previous = 0;
    }

public:
    uint32_t buttons() const { return previous; }

    void shutdown() {
        detach();
        previous = 0;
        retryAt = 0;
        transport = 0;
        seekPercent = -1;
        if (menuOpen || learn) toast_dismiss();
        menuOpen = false;
        holdingMenu = false;
        waitNeutral = true;
    }

    void applyPlayer() {
        auto *playback = evo::Application::getInstance().getPlaybackController();
        if (openChapters) {
            openChapters = false;
            auto *meta = evo::Application::getInstance().getMediaMetadataService();
            auto *screens = evo::Application::getInstance().getScreenManager();
            if (meta && screens && meta->getChapterCount() > 0)
                screens->navigateTo(evo::ScreenId::ChapterPicker);
        }
        if (seekPercent >= 0) {
            const int percent = seekPercent;
            seekPercent = -1;
            if (playback && !playback->isLiveSource() && !playback->isScrubbing() &&
                playback->getDurationSeconds() > 0.0)
                playback->seekTo(playback->getDurationSeconds() * (percent / 100.0));
        }
        if (!transport || !playback) { transport = 0; return; }
        const int request = transport;
        transport = 0;
        if (request == 1 && playback->isPaused()) {
            playback->setPaused(false);
            toast("PLAYBACK", "RESUMED");
        } else if (request == 2 && !playback->isPaused()) {
            playback->setPaused(true);
            toast("PLAYBACK", "PAUSED");
        }
    }

    uint32_t poll(bool browserOwnsInput, bool player, uint64_t now) {
        if (browserOwnsInput) {
            shutdown();
            return 0;
        }
        refreshLearn(now);
        if (handle <= 0) {
            if (now < retryAt) return previous = 0;
            int next = scePadOpen(SystemUser, RemotePort, 0, nullptr);
            const bool borrowed = static_cast<unsigned>(next) == AlreadyOpened;
            if (borrowed) next = scePadGetHandle(SystemUser, RemotePort, 0);
            if (next <= 0) {
                retryAt = now + 1000;
                waitNeutral = true;
                return previous = 0;
            }
            handle = next;
            owned = !borrowed;
        }

        PS5_PadData state{};
        if (scePadReadState(handle, &state) != 0) {
            detach();
            retryAt = now + 1000;
            waitNeutral = true;
            return previous = 0;
        }
        if (!state.connected) {
            waitNeutral = true;
            return previous = 0;
        }
        using namespace evo::PadButtons;
        uint32_t basic = state.buttons & (Up | Down | Left | Right | Cross | Circle | Options);
        const uint8_t code = state.unknown[3];
        if (code != 0 && code != 13 && code != 15 && code != 18 && code != 43)
            bindCode = code;
        showLearn(code, state.buttons);
        if (waitNeutral) {
            if (!basic && !code) waitNeutral = false;
            return previous = 0;
        }
        const bool menuKey = code == 18 || code == 13 || (state.buttons & (Options | Cross));
        if (player && menuKey && !menuOpen) {
            if (!holdingMenu) { holdingMenu = true; menuDownAt = now; }
            if (now - menuDownAt >= 700) {
                openMenu();
                holdingMenu = false;
                menuDownAt = now;
            }
        } else if (!menuKey) {
            holdingMenu = false;
        }
        uint8_t act = 0, arg = 0, playerOnly = 1;
        if (code < 46) {
            act = kKeys[code].act;
            arg = kKeys[code].arg;
            playerOnly = kKeys[code].player;
        }
        if (saved[code].used) {
            act = saved[code].act;
            arg = saved[code].arg;
            playerOnly = saved[code].player;
        }
        if (player && act == ActMenu) openMenu();
        if (menuOpen) return menuFrame(code, basic);
        if (!playerOnly || player) {
            if (act == ActPlay) transport = 1;
            else if (act == ActPause) transport = 2;
            else if (act == ActSeek) seekPercent = arg;
            else if (act == ActChapters) openChapters = true;
            else basic |= maskFor(act);
        }
        return previous = basic;
    }
};

const NuvioTvRemote::Key NuvioTvRemote::kKeys[46] = {
''' + _table_cpp() + r'''
};

const NuvioTvRemote::Item NuvioTvRemote::kMenu[9] = {
''' + _menu_cpp() + r'''
};
const NuvioTvRemote::Name NuvioTvRemote::kNames[] = {
''' + _remap_cpp() + r'''
};
const int NuvioTvRemote::kNameCount = sizeof(NuvioTvRemote::kNames) / sizeof(NuvioTvRemote::kNames[0]);
static NuvioTvRemote s_nuvioRemote;

'''

INPUT_GATE = '''        // Read the remote independently, even without a DualSense handle.
        const uint32_t previousRemote = s_nuvioRemote.buttons();
        const uint32_t remoteButtons = s_nuvioRemote.poll(evo_webui_active(),
            !evo_keyboard_is_open() && m_screenManager &&
                m_screenManager->getCurrentScreenId() == ScreenId::Player,
            static_cast<uint64_t>(now_ms()));
        s_nuvioRemote.applyPlayer();
        const bool controllerRead = m_padHandle >= 0 && scePadReadState(m_padHandle, &padData) == 0;
        if (!controllerRead) {
            // Failed reads may partially fill the struct. Neutralize every
            // non-button input: zero sticks would synthesize Up/Left forever.
            std::memset(&padData, 0, sizeof(padData));
            padData.leftStick.x = padData.leftStick.y = 128;
            padData.rightStick.x = padData.rightStick.y = 128;
        }
        // Merge before EVO computes edges/repeats, not by a second dispatch.
        // Same-button overlap stays held until BOTH devices release it.
        padData.buttons |= remoteButtons;
        if (controllerRead || remoteButtons || previousRemote) {'''


def adapt_application(source):
    """Fail closed on changed anchors; preserve the existing dispatch body."""
    def replace(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise RuntimeError('Pinned native TV remote anchor changed: ' + old[:90])
        source = source.replace(old, new)

    replace('    uint8_t rest[72];\n} PS5_PadData;', PAD_TAIL + '\n} PS5_PadData;')
    replace('#ifndef EVO_PLAYER_VERSION',
            RECEIVER + '#ifndef EVO_PLAYER_VERSION')
    replace('        if (m_padHandle >= 0 && scePadReadState(m_padHandle, &padData) == 0) {', INPUT_GATE)
    replace('    m_shutdownDone = true;\n', '    m_shutdownDone = true;\n    s_nuvioRemote.shutdown();\n')
    replace('                m_softClosed = true;\n',
            '                s_nuvioRemote.shutdown();\n                m_softClosed = true;\n')
    return source


def patch_native(app):
    """Call once after polish.apply(), with EVO's projects/evoplayer Path."""
    path = Path(app) / 'core/src/Application.cpp'
    source = path.read_text()
    path.write_text(adapt_application(source))
