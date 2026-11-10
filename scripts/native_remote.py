"""Add an independent native HDMI-CEC remote receiver to pinned EVO 0.13.5.

Source: ps5-payload-dev/SDL ee4c47dc0d617b3bc8f35108f9956baf228a1322.
src/joystick/ps5/SDL_ps5joystick.h SHA-256:
16436774be2082a3fa4fd6ca4e9792ce45bbfcac64de676d5a56a7b0e6f1a706
src/video/ps5/SDL_ps5remote.c SHA-256:
d0aac6bf7abc4a970b9199265b86e40d940502f6b10d179f9fc3a9c93bc1d85a
Both files were read at that exact revision, not inferred from symbol names.
SDK v0.43 supplies scePadOpen/GetHandle/ReadState/Close link stubs.
The source contract is not evidence of execution on the owner's firmware.
"""
from pathlib import Path


EVO_COMMIT = 'f6e43e6561796630673f1e20eb1eb67d6428514c'
SDL_COMMIT = 'ee4c47dc0d617b3bc8f35108f9956baf228a1322'

# Typed tail from SDL's complete PS5_PadData declaration. Keep EVO's existing
# touch declaration and assertions; never subscript its old opaque rest[72].
PAD_TAIL = '''    uint8_t connected;
    uint64_t timestamp;
    uint8_t ext[16];
    uint8_t count;
    uint8_t unknown[15];'''

RECEIVER = r'''
/* Native TV remote contract adapted from ps5-payload-dev/SDL, revision
 * ee4c47dc0d617b3bc8f35108f9956baf228a1322:
 * src/joystick/ps5/SDL_ps5joystick.h and src/video/ps5/SDL_ps5remote.c.
 * This is NOT Remote Play. No browser event is synthesized here.
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
extern "C" int scePadGetHandle(int user_id, int type, int index);
extern "C" int scePadClose(int handle);

class NuvioTvRemote {
    static constexpr int SystemUser = 0xff;
    static constexpr int RemotePort = 16;
    static constexpr unsigned AlreadyOpened = 0x80920004u;
    int handle = -1;
    bool owned = false;
    bool waitNeutral = false;
    uint64_t retryAt = 0;
    uint32_t previous = 0;

    void detach() {
        // GetHandle borrows an existing handle. Never close another owner's.
        if (owned && handle > 0) scePadClose(handle);
        handle = -1;
        owned = false;
    }

public:
    uint32_t buttons() const { return previous; }

    void shutdown() {
        detach();
        previous = 0;
        retryAt = 0;
        waitNeutral = true;
    }

    uint32_t poll(bool browserOwnsInput, bool player, uint64_t now) {
        if (browserOwnsInput) {
            // Do not retain our port, poll or replay input across the browser.
            shutdown();
            return 0;
        }
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
        // Only the seven basic button meanings explicitly mapped by SDL.
        using namespace evo::PadButtons;
        uint32_t buttons = state.buttons & (Up | Down | Left | Right | Cross | Circle | Options);
        // SDL names this member index PS5_REMOTE_KEY_OFFSET. These are PS5
        // remote codes, NOT DOM keycodes or guessed HDMI wire opcodes.
        const uint8_t code = state.unknown[3];
        if (waitNeutral) {
            if (!buttons && !code) waitNeutral = false;
            return previous = 0;
        }
        switch (code) {
            case 13: buttons |= Cross; break;              // Enter / OK
            case 15: case 43: buttons |= Circle; break;    // Back / previous
            case 18: case 27: buttons |= Options; break;   // Menu / context menu
            // Reuse the player's own action priorities, including skip/next
            // prompts. Transport keys do not navigate unrelated menus/IME.
            case 20: if (player) buttons |= L1; break;     // Previous track
            case 21: if (player) buttons |= R1; break;     // Next track
            case 23: if (player) buttons |= Left; break;   // Rewind
            case 24: if (player) buttons |= Right; break;  // Fast forward
            case 25: if (player) buttons |= Circle; break; // Stop via native Back
            case 45: if (player) buttons |= Cross; break;  // Play/pause
            // Dedicated Play/Pause are not toggles. Leave them unbound rather
            // than reverse their intent by fabricating a Cross press.
            default: break;
        }
        return previous = buttons;
    }
};
static NuvioTvRemote s_nuvioRemote;

'''

INPUT_GATE = '''        // Read the remote independently, even without a DualSense handle.
        const uint32_t previousRemote = s_nuvioRemote.buttons();
        const uint32_t remoteButtons = s_nuvioRemote.poll(evo_webui_active(),
            !evo_keyboard_is_open() && m_screenManager &&
                m_screenManager->getCurrentScreenId() == ScreenId::Player,
            static_cast<uint64_t>(now_ms()));
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
    replace('#ifndef EVO_PLAYER_VERSION', RECEIVER + '#ifndef EVO_PLAYER_VERSION')
    replace('        if (m_padHandle >= 0 && scePadReadState(m_padHandle, &padData) == 0) {', INPUT_GATE)
    replace('    m_shutdownDone = true;\n', '    m_shutdownDone = true;\n    s_nuvioRemote.shutdown();\n')
    replace('                m_softClosed = true;\n',
            '                s_nuvioRemote.shutdown();\n                m_softClosed = true;\n')
    return source


def patch_native(app):
    """Call once after polish.apply(), with EVO's projects/evoplayer Path."""
    path = Path(app) / 'core/src/Application.cpp'
    source = path.read_text()
    updated = adapt_application(source)
    path.write_text(updated)
