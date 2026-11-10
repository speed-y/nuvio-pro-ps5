"""Wire the Phase 1 native UI proof into the pinned EVO / hui tree."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
POC = Path(__file__).resolve().parent / 'native_ui_poc'


def replace(path, old, new):
    source = path.read_text()
    if source.count(old) != 1:
        raise RuntimeError('Pinned native UI PoC anchor changed: ' + str(path))
    path.write_text(source.replace(old, new))


def install_sources(app):
    """Copy PoC sources into the unpacked EVO tree."""
    (app / 'ui_kit/include').mkdir(parents=True, exist_ok=True)
    (app / 'ui_kit/src').mkdir(parents=True, exist_ok=True)
    (app / 'core/include/evo/screens').mkdir(parents=True, exist_ok=True)
    (app / 'core/src/screens').mkdir(parents=True, exist_ok=True)
    (app / 'include').mkdir(parents=True, exist_ok=True)

    shutil.copyfile(POC / 'nuvio_poc_params.h', app / 'include/nuvio_poc_params.h')
    shutil.copyfile(POC / 'nuvio_poc_params.h', app / 'ui_kit/include/nuvio_poc_params.h')
    shutil.copyfile(POC / 'evo_hui_nuvio_poc.hpp', app / 'ui_kit/include/evo_hui_nuvio_poc.hpp')
    shutil.copyfile(POC / 'evo_hui_nuvio_poc.cpp', app / 'ui_kit/src/evo_hui_nuvio_poc.cpp')
    shutil.copyfile(POC / 'NuvioPocScreen.hpp', app / 'core/include/evo/screens/NuvioPocScreen.hpp')
    shutil.copyfile(POC / 'NuvioPocScreen.cpp', app / 'core/src/screens/NuvioPocScreen.cpp')
    shutil.copyfile(POC / 'hui_preview_fixture.inc',
                    app.parents[1] / 'tools/hui_preview/nuvio_poc_fixtures.inc')


def patch_screen_id(app):
    common = app / 'core/include/evo/Common.hpp'
    replace(common,
            '    SubtitleFile = 36          /* pick a subtitle file anywhere on the console */\n};',
            '    SubtitleFile = 36,         /* pick a subtitle file anywhere on the console */\n'
            '    NuvioPoc = 37              /* Nuvio native UI proof shelf */\n};')


def patch_makefile(app):
    makefile = app / 'Makefile'
    replace(makefile,
            '                   ui_kit/src/evo_hui_provider.cpp \\\n'
            '                   ui_kit/src/evo_hui_complex.cpp',
            '                   ui_kit/src/evo_hui_provider.cpp \\\n'
            '                   ui_kit/src/evo_hui_nuvio_poc.cpp \\\n'
            '                   ui_kit/src/evo_hui_complex.cpp')
    replace(makefile,
            '    core/src/screens/LaunchScreen.cpp \\\n',
            '    core/src/screens/LaunchScreen.cpp \\\n'
            '    core/src/screens/NuvioPocScreen.cpp \\\n')


def patch_hui_app(app):
    header = app / 'ui_kit/include/evo_hui.h'
    replace(header,
            '#include "evo_rmlui_bridge.h"\n',
            '#include "evo_rmlui_bridge.h"\n#include "nuvio_poc_params.h"\n')
    replace(header,
            'void evo_hui_update_provider(const evo_hui_provider_params_t* params);\n'
            'int  evo_hui_render_provider(int width, int height);',
            'void evo_hui_update_provider(const evo_hui_provider_params_t* params);\n'
            'int  evo_hui_render_provider(int width, int height);\n'
            'void evo_hui_update_nuvio_poc(const nuvio_poc_params_t* params);\n'
            'int  evo_hui_render_nuvio_poc(int width, int height);')

    source = app / 'ui_kit/src/evo_hui_app.cpp'
    replace(source,
            '#include "evo_hui_provider.hpp"\n',
            '#include "evo_hui_provider.hpp"\n#include "evo_hui_nuvio_poc.hpp"\n')
    replace(source,
            '    provider,\n'
            '    dialog, /* overlays from here on */',
            '    provider,\n'
            '    nuvio_poc,\n'
            '    dialog, /* overlays from here on */')
    replace(source,
            '    case Screen::provider:\n'
            '        return "hui_provider";\n'
            '    default:\n'
            '        return "hui";',
            '    case Screen::provider:\n'
            '        return "hui_provider";\n'
            '    case Screen::nuvio_poc:\n'
            '        return "hui_nuvio_poc";\n'
            '    default:\n'
            '        return "hui";')
    replace(source,
            '    evo::kit::ProviderGridScreen provider;\n'
            '    evo::kit::KeyboardOverlay keyboard;',
            '    evo::kit::ProviderGridScreen provider;\n'
            '    evo::kit::NuvioPocScreen nuvio_poc;\n'
            '    evo::kit::KeyboardOverlay keyboard;')
    source.write_text(source.read_text() + r'''

void evo_hui_update_nuvio_poc(const nuvio_poc_params_t *params)
{
    if (params)
        kit().nuvio_poc.set(*params);
}

int evo_hui_render_nuvio_poc(int width, int height)
{
    Kit &k = kit();
    return k.render(Screen::nuvio_poc, width, height,
                    [&](float dt, hui::gfx::DrawList &list, const Context &ctx) {
                        k.nuvio_poc.update(dt);
                        k.nuvio_poc.draw(list, ctx);
                    });
}
''')


def patch_bridge(app):
    bridge_h = app / 'ui_rml/include/evo_rmlui_bridge.h'
    replace(bridge_h,
            'void evo_rmlui_render_launch(uint32_t* framebuffer, int width, int height);',
            'void evo_rmlui_render_launch(uint32_t* framebuffer, int width, int height);\n'
            'void evo_rmlui_update_nuvio_poc(const struct nuvio_poc_params_t* params);\n'
            'void evo_rmlui_render_nuvio_poc(uint32_t* framebuffer, int width, int height);')
    replace(bridge_h,
            '#include <stdint.h>\n#include <stdbool.h>\n',
            '#include <stdint.h>\n#include <stdbool.h>\n#include "nuvio_poc_params.h"\n')

    bridge = app / 'ui_rml/src/evo_rmlui_bridge.cpp'
    # Ensure the kit header is visible where other hui calls already are.
    if 'evo_hui.h' not in bridge.read_text():
        replace(bridge, '#include "evo_rmlui_bridge.h"',
                '#include "evo_rmlui_bridge.h"\n#include "evo_hui.h"')
    bridge.write_text(bridge.read_text() + r'''

extern "C" void evo_rmlui_update_nuvio_poc(const nuvio_poc_params_t* params) {
#if defined(EVO_AGC_DEVICE)
    evo_hui_update_nuvio_poc(params);
#else
    (void)params;
#endif
}

extern "C" void evo_rmlui_render_nuvio_poc(uint32_t* framebuffer, int width, int height) {
#if defined(EVO_AGC_DEVICE)
    if (EvoRmlApp::Instance().GlActive() && evo_hui_render_nuvio_poc(width, height)) {
        EvoRmlApp::Instance().NoteExternalDraw();
        return;
    }
#endif
    (void)framebuffer;
    (void)width;
    (void)height;
}
''')


def patch_application(app):
    application = app / 'core/src/Application.cpp'
    replace(application,
            '#include "evo/screens/LaunchScreen.hpp"\n',
            '#include "evo/screens/LaunchScreen.hpp"\n'
            '#include "evo/screens/NuvioPocScreen.hpp"\n')
    replace(application,
            '    m_screenManager->registerScreen(std::make_unique<LaunchScreen>());\n',
            '    m_screenManager->registerScreen(std::make_unique<LaunchScreen>());\n'
            '    m_screenManager->registerScreen(std::make_unique<NuvioPocScreen>());\n')

    # Keep the browser loading shell, but never cover the native proof screen.
    replace(application,
            '        bool nuvioShell = !isPlayer &&\n'
            '            !(m_playbackController && m_playbackController->isActive()) &&\n'
            '            !evo_webui_native_requested();\n',
            '        const bool onNuvioPoc = m_screenManager &&\n'
            '            m_screenManager->getCurrentScreenId() == ScreenId::NuvioPoc;\n'
            '        bool nuvioShell = !isPlayer &&\n'
            '            !(m_playbackController && m_playbackController->isActive()) &&\n'
            '            !evo_webui_native_requested() &&\n'
            '            !onNuvioPoc;\n')


def patch_boot_flag(app):
    """Prefer the native proof when /data/nuvio/native_ui_poc exists. Keep browser otherwise."""
    application = app / 'core/src/Application.cpp'
    old = '''        /* Nuvio starts once its durable settings are reachable. Existing
         * EVO code owns browser, playback handoff and shutdown lifetimes. */
        static bool nuvio_opened = false;
        if (!nuvio_opened && evo_jailbreak_is_open()) {
            const evo_provider_t *nv = evo_provider_find("nuvio");
            if (nv && nv->is_configured() &&
                evo_webui_open_ex(nv->web_ui_url(), "/", "nuvio") == 0)
                nuvio_opened = true;
        }
        evo_webui_pump();   /* #101: the system browser, when a web UI is open */'''
    new = '''        /* Nuvio starts once its durable settings are reachable. Existing
         * EVO code owns browser, playback handoff and shutdown lifetimes.
         * /data/nuvio/native_ui_poc opts into the Phase 1 native shelf proof
         * without deleting the browser path. */
        static bool nuvio_opened = false;
        if (!nuvio_opened && evo_jailbreak_is_open()) {
            if (access("/data/nuvio/native_ui_poc", F_OK) == 0) {
                if (m_screenManager)
                    m_screenManager->navigateTo(ScreenId::NuvioPoc);
                nuvio_opened = true;
            } else {
                const evo_provider_t *nv = evo_provider_find("nuvio");
                if (nv && nv->is_configured() &&
                    evo_webui_open_ex(nv->web_ui_url(), "/", "nuvio") == 0)
                    nuvio_opened = true;
            }
        }
        evo_webui_pump();   /* #101: the system browser, when a web UI is open */'''
    replace(application, old, new)
    if '#include <unistd.h>' not in application.read_text():
        replace(application, '#include "evo/Application.hpp"\n',
                '#include "evo/Application.hpp"\n#include <unistd.h>\n')


def patch_hui_preview(evo):
    preview = evo / 'tools/hui_preview/hui_preview.cpp'
    replace(preview,
            '#include "evo_hui_provider.hpp"\n'
            '#include "extra_fixtures.inc"\n',
            '#include "evo_hui_provider.hpp"\n'
            '#include "evo_hui_nuvio_poc.hpp"\n'
            '#include "extra_fixtures.inc"\n'
            '#include "nuvio_poc_fixtures.inc"\n')
    replace(preview,
            '    evo_hui_provider_params_t prp{};\n'
            '    std::vector<uint32_t> provider_art;\n',
            '    evo_hui_provider_params_t prp{};\n'
            '    std::vector<uint32_t> provider_art;\n'
            '    nuvio_poc_params_t nuvio_poc_params{};\n'
            '    std::vector<uint32_t> nuvio_poc_hero;\n'
            '    std::vector<std::vector<uint32_t>> nuvio_poc_posters;\n')
    replace(preview,
            '        {"home", 0, [&] { clear_focus(); launch.hero_focused = 1; }},\n',
            '        {"home", 0, [&] { clear_focus(); launch.hero_focused = 1; }},\n'
            '        {"nuvio_poc", 18, [&] {\n'
            '            clear_focus();\n'
            '            fill_nuvio_poc_fixture(nuvio_poc_params, nuvio_poc_hero, nuvio_poc_posters, 1);\n'
            '        }},\n'
            '        {"nuvio_poc_detail", 18, [&] {\n'
            '            clear_focus();\n'
            '            fill_nuvio_poc_detail_fixture(nuvio_poc_params, nuvio_poc_hero, nuvio_poc_posters);\n'
            '        }},\n'
            '        {"nuvio_poc_error", 18, [&] {\n'
            '            clear_focus();\n'
            '            fill_nuvio_poc_error_fixture(nuvio_poc_params, nuvio_poc_hero, nuvio_poc_posters);\n'
            '        }},\n')
    replace(preview,
            '        evo::kit::ProviderGridScreen provider;\n'
            '        f.setup();\n',
            '        evo::kit::ProviderGridScreen provider;\n'
            '        evo::kit::NuvioPocScreen nuvio_poc;\n'
            '        f.setup();\n'
            '        if (f.kind == 18) { nuvio_poc.set(nuvio_poc_params); nuvio_poc.enter(); }\n')
    replace(preview,
            '            else if (f.kind == 17)\n'
            '                provider.update(kDt);\n',
            '            else if (f.kind == 17)\n'
            '                provider.update(kDt);\n'
            '            else if (f.kind == 18)\n'
            '                nuvio_poc.update(kDt);\n')
    replace(preview,
            '        else if (f.kind == 17)\n'
            '            provider.draw(list, ctx);\n'
            '        const bool over_video = (f.kind >= 4 && f.kind <= 6) || f.kind == 11 || f.kind == 12 || f.kind == 15;\n',
            '        else if (f.kind == 17)\n'
            '            provider.draw(list, ctx);\n'
            '        else if (f.kind == 18)\n'
            '            nuvio_poc.draw(list, ctx);\n'
            '        const bool over_video = (f.kind >= 4 && f.kind <= 6) || f.kind == 11 || f.kind == 12 || f.kind == 15;\n')
    replace(preview,
            '        else if (f.kind != 10 && f.kind != 14)\n'
            '        {\n'
            '            rail.draw(list, ctx);\n'
            '        }\n',
            '        else if (f.kind != 10 && f.kind != 14 && f.kind != 18)\n'
            '        {\n'
            '            rail.draw(list, ctx);\n'
            '        }\n')

    script = evo / 'tools/hui_preview.sh'
    text = script.read_text()
    old = '         "${EVO}/ui_kit/src/evo_hui_provider.cpp"\n'
    new = ('         "${EVO}/ui_kit/src/evo_hui_provider.cpp"\n'
           '         "${EVO}/ui_kit/src/evo_hui_nuvio_poc.cpp"\n')
    if old not in text:
        raise RuntimeError('Pinned hui_preview.sh source list changed')
    script.write_text(text.replace(old, new, 1))

    # Allow a host without Docker when EGL is present.
    docker_gate = '''if [[ ! -f /.dockerenv ]]; then
    cd "${ROOT}"
    MSYS_NO_PATHCONV=1 exec docker compose run --rm ps5-dev bash ./tools/hui_preview.sh "$@"
fi
'''
    local_gate = '''if [[ ! -f /.dockerenv ]]; then
    if [[ "${NUVIO_HUI_PREVIEW_LOCAL:-}" == "1" ]]; then
        cd "${ROOT}"
    else
        cd "${ROOT}"
        MSYS_NO_PATHCONV=1 exec docker compose run --rm ps5-dev bash ./tools/hui_preview.sh "$@"
    fi
fi
'''
    if docker_gate not in script.read_text():
        raise RuntimeError('Pinned hui_preview.sh docker gate changed')
    script.write_text(script.read_text().replace(docker_gate, local_gate))


def patch_native(app, evo):
    install_sources(app)
    patch_screen_id(app)
    patch_makefile(app)
    patch_hui_app(app)
    patch_bridge(app)
    patch_application(app)
    patch_boot_flag(app)
    patch_hui_preview(evo)
    assets = app / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    catalog = ROOT / 'scripts/native_ui_poc/poc_catalog.sample.json'
    if catalog.is_file():
        shutil.copyfile(catalog, assets / 'nuvio_poc_catalog.json')
