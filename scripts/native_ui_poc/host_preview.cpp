/*
 * Host preview for the Nuvio native UI proof.
 * Same DrawList + OpenGL kit path as EVO tools/hui_preview.sh.
 * usage: host_preview <evo-repo-root> <output-dir> [width height [art-dir]]
 * Optional art-dir holds hero_0.jpg, poster_*.jpg and catalog.json from a live Home scrape.
 */
#include "evo_hui_nuvio_poc.hpp"
#include "nuvio_poc_params.h"

#include "core/save_file.hpp"
#include "gfx/gl_program.hpp"
#include "gfx/renderer.hpp"
#include "ui/fonts.hpp"

#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GL/glcorearb.h>

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "third_party/stb/stb_image_write.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace
{

bool open_context()
{
    auto get_platform_display = reinterpret_cast<PFNEGLGETPLATFORMDISPLAYEXTPROC>(
        eglGetProcAddress("eglGetPlatformDisplayEXT"));
    EGLDisplay display =
        get_platform_display != nullptr
            ? get_platform_display(EGL_PLATFORM_SURFACELESS_MESA, EGL_DEFAULT_DISPLAY, nullptr)
            : eglGetDisplay(EGL_DEFAULT_DISPLAY);
    EGLint major = 0, minor = 0;
    if (display == EGL_NO_DISPLAY || !eglInitialize(display, &major, &minor) ||
        !eglBindAPI(EGL_OPENGL_API))
        return false;
    const EGLint attributes[] = {EGL_CONTEXT_MAJOR_VERSION, 4, EGL_CONTEXT_MINOR_VERSION, 5,
                                 EGL_CONTEXT_OPENGL_PROFILE_MASK,
                                 EGL_CONTEXT_OPENGL_CORE_PROFILE_BIT, EGL_NONE};
    EGLContext context = eglCreateContext(display, EGL_NO_CONFIG_KHR, EGL_NO_CONTEXT, attributes);
    return context != EGL_NO_CONTEXT &&
           eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, context);
}

class HostTextures final : public evo::kit::TextureHost
{
  public:
    HostTextures(hui::gfx::Renderer &renderer, std::string assets)
        : renderer_(renderer), assets_(std::move(assets))
    {
    }
    std::uint32_t create_texture(int w, int h, const std::uint8_t *rgba) override
    {
        return renderer_.batch().create_texture(w, h, rgba);
    }
    void release_texture(std::uint32_t handle) override
    {
        GLuint name = handle;
        if (name)
            glDeleteTextures(1, &name);
    }
    bool read_asset(const std::string &path, std::string *bytes) override
    {
        std::string rel = path;
        while (rel.rfind("../", 0) == 0)
            rel = rel.substr(3);
        return hui::save::read_file(assets_ + "/" + rel, bytes);
    }

  private:
    hui::gfx::Renderer &renderer_;
    std::string assets_;
};

std::vector<std::uint32_t> fake_art(int w, int h, std::uint32_t a, std::uint32_t b, float seed)
{
    std::vector<std::uint32_t> px(static_cast<std::size_t>(w * h));
    auto ch = [](std::uint32_t c, int s) { return static_cast<float>((c >> s) & 0xff); };
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x)
        {
            const float u = static_cast<float>(x) / static_cast<float>(w);
            const float v = static_cast<float>(y) / static_cast<float>(h);
            float t = 0.5f * u + 0.5f * v;
            const float dx = u - 0.65f - 0.1f * std::sin(seed), dy = (v - 0.45f) * 0.56f;
            t = std::min(1.0f, t + std::exp(-(dx * dx + dy * dy) * 30.0f) * 0.6f);
            const float r = ch(a, 16) * (1 - t) + ch(b, 16) * t;
            const float g = ch(a, 8) * (1 - t) + ch(b, 8) * t;
            const float bl = ch(a, 0) * (1 - t) + ch(b, 0) * t;
            px[static_cast<std::size_t>(y * w + x)] =
                0xff000000u | (static_cast<std::uint32_t>(bl) << 16) |
                (static_cast<std::uint32_t>(g) << 8) | static_cast<std::uint32_t>(r);
        }
    return px;
}

bool load_jpeg_abgr(const std::string &path, std::vector<std::uint32_t> *out, int *out_w, int *out_h)
{
    int w = 0, h = 0, n = 0;
    unsigned char *rgba = stbi_load(path.c_str(), &w, &h, &n, 4);
    if (!rgba || w <= 0 || h <= 0)
    {
        if (rgba)
            stbi_image_free(rgba);
        return false;
    }
    out->resize(static_cast<std::size_t>(w * h));
    for (int i = 0; i < w * h; ++i)
    {
        const unsigned char *p = rgba + i * 4;
        (*out)[static_cast<std::size_t>(i)] =
            0xff000000u | (static_cast<std::uint32_t>(p[2]) << 16) |
            (static_cast<std::uint32_t>(p[1]) << 8) | static_cast<std::uint32_t>(p[0]);
    }
    stbi_image_free(rgba);
    *out_w = w;
    *out_h = h;
    return true;
}

bool load_art_bundle(const std::string &art_dir, std::vector<std::uint32_t> *hero, int *hero_w,
                     int *hero_h, std::vector<std::vector<std::uint32_t>> *posters, int *poster_w,
                     int *poster_h)
{
    if (art_dir.empty())
        return false;

    /* Catalog order from a live Home Popular - Movie scrape. */
    static const char *poster_names[] = {"poster_0.jpg", "poster_3.jpg", "poster_4.jpg",
                                         "poster_5.jpg", "poster_6.jpg", "poster_7.jpg",
                                         "poster_8.jpg", "poster_9.jpg"};
    static const uint32_t pairs[][2] = {{0x1a1040, 0x7b62ff}, {0x2b1055, 0xd16ba5}, {0x3a1c0b, 0xf2a541},
                                        {0x0b1f3a, 0x5aa9e6}, {0x1e2a12, 0x9bd16b}, {0x331022, 0xff6f91},
                                        {0x102033, 0x6bb6ff}, {0x241018, 0xff8f6b}};
    if (!load_jpeg_abgr(art_dir + "/hero_0.jpg", hero, hero_w, hero_h))
    {
        std::fprintf(stderr, "art: no hero_0.jpg under %s (falling back to fake art)\n",
                     art_dir.c_str());
        return false;
    }

    posters->clear();
    int pw = 300, ph = 450;
    int loaded = 0;
    for (int i = 0; i < 8; ++i)
    {
        std::vector<std::uint32_t> px;
        int w = 0, h = 0;
        if (load_jpeg_abgr(art_dir + "/" + poster_names[i], &px, &w, &h))
        {
            if (loaded == 0)
            {
                pw = w;
                ph = h;
            }
            ++loaded;
        }
        else
        {
            std::fprintf(stderr, "art: missing %s, using synthetic fill\n", poster_names[i]);
            px = fake_art(pw, ph, pairs[i][0], pairs[i][1], static_cast<float>(i));
            w = pw;
            h = ph;
        }
        posters->push_back(std::move(px));
        (void)w;
        (void)h;
    }
    *poster_w = pw;
    *poster_h = ph;
    std::fprintf(stderr, "art: loaded hero %dx%d and %d/%zu real posters from %s\n", *hero_w, *hero_h,
                 loaded, posters->size(), art_dir.c_str());
    return true;
}

bool load_font(hui::gfx::Renderer &renderer, const std::string &path, hui::gfx::Font *font,
               hui::ui::FontRef *ref)
{
    std::string data;
    if (!hui::save::read_file(path, &data) || !font->load(data))
    {
        std::fprintf(stderr, "cannot load font %s\n", path.c_str());
        return false;
    }
    ref->font = font;
    ref->texture = renderer.batch().create_font_texture(*font);
    return true;
}

#include "hui_preview_fixture.inc"

} // namespace

int main(int argc, char **argv)
{
    if (argc < 3)
    {
        std::fprintf(stderr,
                     "usage: %s <evo-repo-root> <output-dir> [width height [art-dir]]\n",
                     argv[0]);
        return 2;
    }
    const std::string root = argv[1];
    const std::string output = argv[2];
    const int width = argc > 4 ? std::atoi(argv[3]) : 1920;
    const int height = argc > 4 ? std::atoi(argv[4]) : 1080;
    std::string art_dir;
    if (argc > 5)
        art_dir = argv[5];
    else if (const char *env = std::getenv("NUVIO_POC_ART"))
        art_dir = env;
    const std::string assets = root + "/projects/evoplayer/assets";
    const std::string fdir = root + "/third_party/ps5-homebrew-ui/assets/fonts/";

    if (!open_context())
    {
        std::fprintf(stderr, "no surfaceless EGL OpenGL 4.5 context\n");
        return 1;
    }
    hui::gfx::set_glsl_prefix("#version 450 core\n");
    hui::gfx::Renderer renderer;
    if (!renderer.init())
        return 1;

    hui::gfx::Font regular, semibold, display, mono;
    hui::ui::Fonts fonts;
    if (!load_font(renderer, fdir + "inter-regular.huifont", &regular, &fonts.regular) ||
        !load_font(renderer, fdir + "inter-semibold.huifont", &semibold, &fonts.semibold) ||
        !load_font(renderer, fdir + "montserrat-medium.huifont", &display, &fonts.display) ||
        !load_font(renderer, fdir + "dejavu-sans-mono.huifont", &mono, &fonts.mono))
        return 1;

    HostTextures host(renderer, assets);
    evo::kit::TextureCache textures(host);
    evo::kit::Palette palette;
    palette.bg_top = hui::gfx::Color::rgb(0x0d0d0d);
    palette.bg_bottom = hui::gfx::Color::rgb(0x0d0d0d);
    palette.accent = hui::gfx::Color::rgb(0x7b62ff);
    palette.text = hui::gfx::Color::rgb(0xffffff);
    palette.text_muted = hui::gfx::Color::rgb(0xb3b3b3);

    std::vector<std::uint32_t> shared_hero;
    std::vector<std::vector<std::uint32_t>> shared_posters;
    int hero_w = 0, hero_h = 0, poster_w = 221, poster_h = 339;
    const bool have_art =
        load_art_bundle(art_dir, &shared_hero, &hero_w, &hero_h, &shared_posters, &poster_w, &poster_h);

    GLuint framebuffer = 0, color = 0;
    glGenFramebuffers(1, &framebuffer);
    glGenRenderbuffers(1, &color);
    glBindRenderbuffer(GL_RENDERBUFFER, color);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, width, height);
    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, color);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
        return 1;
    hui::save::ensure_directory(output);
    stbi_flip_vertically_on_write(1);

    struct Case
    {
        const char *name;
        int which; /* 0 shelf, 1 detail, 2 error */
    };
    const Case cases[] = {{"nuvio_poc", 0}, {"nuvio_poc_detail", 1}, {"nuvio_poc_error", 2}};

    std::vector<unsigned char> pixels(static_cast<std::size_t>(width * height * 4));
    constexpr float kDt = 1.0f / 60.0f;
    for (const Case &c : cases)
    {
        nuvio_poc_params_t params{};
        std::vector<std::uint32_t> hero = have_art ? shared_hero : std::vector<std::uint32_t>{};
        std::vector<std::vector<std::uint32_t>> posters =
            have_art ? shared_posters : std::vector<std::vector<std::uint32_t>>{};
        const int hw = have_art ? hero_w : 1280;
        const int hh = have_art ? hero_h : 720;
        if (c.which == 0)
            fill_nuvio_poc_fixture(params, hero, hw, hh, posters, poster_w, poster_h, 1);
        else if (c.which == 1)
            fill_nuvio_poc_detail_fixture(params, hero, hw, hh, posters, poster_w, poster_h);
        else
            fill_nuvio_poc_error_fixture(params, hero, hw, hh, posters, poster_w, poster_h);

        evo::kit::NuvioPocScreen screen;
        screen.set(params);
        screen.enter();
        hui::gfx::DrawList list;
        float time = 0.0f;
        for (int frame = 0; frame < 90; ++frame)
        {
            screen.update(kDt);
            textures.tick();
            time += kDt;
        }
        evo::kit::Context ctx{fonts, textures, palette, time};
        list.clear();
        screen.draw(list, ctx);
        renderer.begin();
        renderer.draw(list);
        glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
        glClearColor(0, 0, 0, 1);
        glClear(GL_COLOR_BUFFER_BIT);
        renderer.present(framebuffer, width, height);
        glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
        glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
        for (std::size_t i = 3; i < pixels.size(); i += 4)
            pixels[i] = 255;
        const std::string path = output + "/hui_" + c.name + ".png";
        stbi_write_png(path.c_str(), width, height, 4, pixels.data(), width * 4);
        std::fprintf(stderr, "wrote %s\n", path.c_str());
    }
    return 0;
}
