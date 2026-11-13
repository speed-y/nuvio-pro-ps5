/*
 * Nuvio native UI proof core screen. GPL-3.0-or-later.
 */
#include "evo/screens/NuvioPocScreen.hpp"

#include "evo/Application.hpp"
#include "evo/Common.hpp"
#include "evo/interfaces/IPlaybackController.hpp"
#include "evo/services/SoundEffectEngine.hpp"
#include "nuvio_poc_params.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <unistd.h>

namespace evo
{
namespace
{

constexpr int kVisible = 6;

/* Tiny built-in catalogue so the proof can open without a network host. */
void fill_builtin(std::vector<NuvioPocScreen::CatalogItem> *out)
{
    struct Seed
    {
        const char *title;
        const char *subtitle;
        const char *overview;
        const char *url;
        uint32_t a;
        uint32_t b;
    };
    /* Titles mirror a live Home Popular - Movie row for the one-screen proof. */
    static const Seed kSeeds[] = {
        {"Resident Evil", "Movie · Action · 1h 34m",
         "Follows a hapless courier tasked with delivering a package to a remote hospital.",
         "", 0x1a1040, 0x7b62ff},
        {"Hocus Pocus", "Movie · 1993",
         "A teenage boy and his younger sister face three witches raised from the dead on Halloween.",
         "", 0x2b1055, 0xd16ba5},
        {"Halloween", "Movie · 1978",
         "Fifteen years after murdering his sister, Michael Myers escapes from a mental hospital.",
         "", 0x3a1c0b, 0xf2a541},
        {"Primetime", "Movie · 2026",
         "A tense thriller set behind the cameras of a live broadcast.", "", 0x0b1f3a, 0x5aa9e6},
        {"Obsession", "Movie · Horror", "A chilling tale of desire that turns deadly.", "", 0x1e2a12,
         0x9bd16b},
        {"A Dog's Perfect Christmas", "Movie · 2026",
         "A holiday story about family and a loyal dog.", "", 0x331022, 0xff6f91},
        {"Verity", "Movie · 2026",
         "A ghostwriter discovers a manuscript that may not be fiction.", "", 0x102033, 0x6bb6ff},
        {"The Nightmare Before Christmas", "Movie · 1993",
         "Jack Skellington discovers Christmas Town and tries to take over the holiday.", "",
         0x241018, 0xff8f6b},
    };
    out->clear();
    for (const Seed &seed : kSeeds)
    {
        NuvioPocScreen::CatalogItem item;
        item.title = seed.title;
        item.subtitle = seed.subtitle;
        item.overview = seed.overview;
        item.play_url = seed.url;
        item.poster_w = 221;
        item.poster_h = 339;
        item.poster = NuvioPocScreen::makePoster(seed.a, seed.b, static_cast<float>(out->size()));
        out->push_back(std::move(item));
    }
}

int read_file(const char *path, std::string *out)
{
    std::ifstream in(path, std::ios::binary);
    if (!in)
        return -1;
    out->assign(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
    return 0;
}

/* Accept a tiny JSON array of {title,subtitle,overview,play_url}. No nested objects. */
int parse_simple_catalog(const std::string &json, std::vector<NuvioPocScreen::CatalogItem> *out)
{
    out->clear();
    std::size_t pos = 0;
    auto next_string = [&](std::string *value) -> bool {
        const std::size_t a = json.find('"', pos);
        if (a == std::string::npos)
            return false;
        const std::size_t b = json.find('"', a + 1);
        if (b == std::string::npos)
            return false;
        *value = json.substr(a + 1, b - a - 1);
        pos = b + 1;
        return true;
    };
    while (true)
    {
        const std::size_t obj = json.find('{', pos);
        if (obj == std::string::npos)
            break;
        pos = obj + 1;
        NuvioPocScreen::CatalogItem item;
        std::string key;
        while (next_string(&key))
        {
            const std::size_t colon = json.find(':', pos);
            if (colon == std::string::npos)
                break;
            pos = colon + 1;
            std::string value;
            if (!next_string(&value))
                break;
            if (key == "title")
                item.title = value;
            else if (key == "subtitle")
                item.subtitle = value;
            else if (key == "overview")
                item.overview = value;
            else if (key == "play_url")
                item.play_url = value;
            if (json.find('}', pos) < json.find('"', pos))
                break;
        }
        if (item.title.empty())
            continue;
        item.poster_w = 221;
        item.poster_h = 339;
        const uint32_t a = 0x102030u + static_cast<uint32_t>(out->size()) * 0x1020u;
        const uint32_t b = 0x60a0c0u + static_cast<uint32_t>(out->size()) * 0x0810u;
        item.poster = NuvioPocScreen::makePoster(a, b, static_cast<float>(out->size()) + 1.0f);
        out->push_back(std::move(item));
        if (out->size() >= NUVIO_POC_MAX_ITEMS)
            break;
    }
    return out->empty() ? -1 : 0;
}

} // namespace

std::vector<uint32_t> NuvioPocScreen::makePoster(uint32_t a, uint32_t b, float seed)
{
    /* Measured browser Home poster cell is ~221x339. */
    const int w = 221;
    const int h = 339;
    std::vector<uint32_t> px(static_cast<std::size_t>(w * h));
    auto ch = [](uint32_t c, int s) { return static_cast<float>((c >> s) & 0xff); };
    for (int y = 0; y < h; ++y)
    {
        for (int x = 0; x < w; ++x)
        {
            const float u = static_cast<float>(x) / static_cast<float>(w);
            const float v = static_cast<float>(y) / static_cast<float>(h);
            float t = 0.45f * u + 0.55f * v;
            const float dx = u - 0.62f - 0.08f * std::sin(seed);
            const float dy = (v - 0.38f) * 0.7f;
            t = std::min(1.0f, t + std::exp(-(dx * dx + dy * dy) * 26.0f) * 0.55f);
            const int r = static_cast<int>(ch(a, 16) * (1.0f - t) + ch(b, 16) * t);
            const int g = static_cast<int>(ch(a, 8) * (1.0f - t) + ch(b, 8) * t);
            const int bl = static_cast<int>(ch(a, 0) * (1.0f - t) + ch(b, 0) * t);
            px[static_cast<std::size_t>(y * w + x)] =
                0xff000000u | (static_cast<uint32_t>(bl) << 16) | (static_cast<uint32_t>(g) << 8) |
                static_cast<uint32_t>(r);
        }
    }
    return px;
}

NuvioPocScreen::NuvioPocScreen() : StatefulScreen("NuvioPocScreen")
{
    theme_ = nuvio_poc_default_theme();
    hero_w_ = 1280;
    hero_h_ = 720;
    hero_art_.assign(static_cast<std::size_t>(hero_w_ * hero_h_), 0);
    {
        auto full = makePoster(0x101820, 0x7b62ff, 0.2f);
        for (int y = 0; y < hero_h_; ++y)
        {
            for (int x = 0; x < hero_w_; ++x)
            {
                const int sx = x * 221 / hero_w_;
                const int sy = y * 339 / hero_h_;
                hero_art_[static_cast<std::size_t>(y * hero_w_ + x)] =
                    full[static_cast<std::size_t>(sy * 221 + sx)];
            }
        }
    }
    status_ = "Loading shelf…";
}

NuvioPocScreen::~NuvioPocScreen()
{
    if (fetch_thread_.joinable())
        fetch_thread_.join();
}

void NuvioPocScreen::onEnter()
{
    StatefulScreen::onEnter();
    detail_open_ = 0;
    play_focused_ = 0;
    if (auto *sfx = Application::getInstance().getSoundEffectEngine())
    {
        sounds_were_enabled_ = sfx->isEnabled();
        sfx->setEnabled(false); /* UI sound off for the proof */
    }
    startMetadataFetch();
}

void NuvioPocScreen::onExit()
{
    if (auto *sfx = Application::getInstance().getSoundEffectEngine())
        sfx->setEnabled(sounds_were_enabled_);
    StatefulScreen::onExit();
}

void NuvioPocScreen::startMetadataFetch()
{
    if (fetch_running_.exchange(1))
        return;
    status_ = "Loading shelf…";
    status_is_error_ = 0;
    if (fetch_thread_.joinable())
        fetch_thread_.join();
    fetch_thread_ = std::thread([this]() {
        std::vector<CatalogItem> loaded;
        std::string status = "Sample shelf";
        int error = 0;

        /* Optional console file. Missing or bad JSON must not freeze the UI. */
        std::string body;
        const char *paths[] = {"/data/nuvio-poc/poc_catalog.json", "/app0/assets/nuvio_poc_catalog.json"};
        int got = -1;
        for (const char *path : paths)
        {
            if (read_file(path, &body) == 0)
            {
                got = parse_simple_catalog(body, &loaded);
                if (got == 0)
                {
                    status = "Loaded catalogue";
                    break;
                }
                error = 1;
                status = "Catalogue parse failed";
            }
        }
        if (got != 0)
        {
            /* Intentional fail path: ask for a missing remote hint file. */
            std::string hint;
            if (read_file("/data/nuvio-poc/poc_catalog.remote", &hint) == 0)
            {
                error = 1;
                status = "Remote metadata unavailable";
                loaded.clear();
            }
            else
            {
                fill_builtin(&loaded);
                if (error)
                    status = "Using sample shelf";
                error = 0;
            }
        }

        {
            std::lock_guard<std::mutex> lock(catalog_mx_);
            pending_items_ = std::move(loaded);
            pending_status_ = status;
            pending_error_ = error;
        }
        catalog_ready_.store(1);
        fetch_running_.store(0);
    });
}

void NuvioPocScreen::applyCatalogLocked()
{
    items_ = pending_items_;
    status_ = pending_status_;
    status_is_error_ = pending_error_;
    if (items_.empty())
    {
        focus_index_ = 0;
        scroll_index_ = 0;
    }
    else
    {
        focus_index_ = std::min(focus_index_, static_cast<int>(items_.size()) - 1);
        scroll_index_ = std::min(scroll_index_, focus_index_);
    }
}

void NuvioPocScreen::moveFocus(int delta)
{
    if (items_.empty())
        return;
    focus_index_ = std::clamp(focus_index_ + delta, 0, static_cast<int>(items_.size()) - 1);
    if (focus_index_ < scroll_index_)
        scroll_index_ = focus_index_;
    if (focus_index_ >= scroll_index_ + kVisible)
        scroll_index_ = focus_index_ - kVisible + 1;
}

void NuvioPocScreen::openDetail()
{
    if (items_.empty())
        return;
    detail_open_ = 1;
    play_focused_ = 1;
}

void NuvioPocScreen::closeDetail()
{
    detail_open_ = 0;
    play_focused_ = 0;
}

void NuvioPocScreen::playFocused()
{
    if (items_.empty())
        return;
    const CatalogItem &item = items_[static_cast<std::size_t>(focus_index_)];
    auto *playback = Application::getInstance().getPlaybackController();
    auto *screens = Application::getInstance().getScreenManager();
    if (!playback || !screens)
        return;

    std::string url = item.play_url;
    if (url.empty())
    {
        /* Prefer an owner-provided clip for console proof installs. */
        if (access("/data/nuvio-poc/poc_sample.mp4", R_OK) == 0)
            url = "/data/nuvio-poc/poc_sample.mp4";
        else if (access("/data/nuvio-poc/poc_sample.mkv", R_OK) == 0)
            url = "/data/nuvio-poc/poc_sample.mkv";
    }
    if (url.empty())
    {
        status_ = "No playable URL for this card";
        status_is_error_ = 1;
        return;
    }

    PlaybackSource source;
    source.url = url;
    source.title = item.title;
    source.provider = "nuvio-poc";
    source.item_id = item.title;
    if (!playback->startPlaybackSource(source, 0.0))
    {
        status_ = "Playback failed to start";
        status_is_error_ = 1;
        return;
    }
    status_ = "Playing";
    status_is_error_ = 0;
    screens->navigateTo(ScreenId::Player);
}

void NuvioPocScreen::fillParams(nuvio_poc_params_t *params) const
{
    std::memset(params, 0, sizeof(*params));
    params->theme = theme_;
    params->brand = "Nuvio";
    params->shelf_title = "Popular - Movie";
    params->status = status_.c_str();
    params->status_is_error = status_is_error_;
    params->focus_index = focus_index_;
    params->scroll_index = scroll_index_;
    params->detail_open = detail_open_;
    params->play_focused = play_focused_;
    params->hero_art = hero_art_.empty() ? nullptr : hero_art_.data();
    params->hero_art_w = hero_w_;
    params->hero_art_h = hero_h_;
    if (!items_.empty())
    {
        const CatalogItem &hero = items_[static_cast<std::size_t>(focus_index_)];
        params->hero_title = hero.title.c_str();
        params->hero_detail = hero.subtitle.c_str();
        params->hero_overview = hero.overview.c_str();
    }
    else
    {
        params->hero_title = "Nuvio";
        params->hero_detail = status_.c_str();
        params->hero_overview = "";
    }
    params->item_count = std::min(static_cast<int>(items_.size()), static_cast<int>(NUVIO_POC_MAX_ITEMS));
    for (int i = 0; i < params->item_count; ++i)
    {
        const CatalogItem &item = items_[static_cast<std::size_t>(i)];
        std::snprintf(params->items[i].title, sizeof params->items[i].title, "%s", item.title.c_str());
        std::snprintf(params->items[i].subtitle, sizeof params->items[i].subtitle, "%s",
                      item.subtitle.c_str());
        std::snprintf(params->items[i].overview, sizeof params->items[i].overview, "%s",
                      item.overview.c_str());
        std::snprintf(params->items[i].play_url, sizeof params->items[i].play_url, "%s",
                      item.play_url.c_str());
        params->items[i].poster = item.poster.empty() ? nullptr : item.poster.data();
        params->items[i].poster_w = item.poster_w;
        params->items[i].poster_h = item.poster_h;
    }
}

bool NuvioPocScreen::handleInput(uint32_t pressed, uint32_t held, uint32_t released)
{
    (void)held;
    (void)released;

    if (pressed & PadButtons::Left)
    {
        if (detail_open_)
            return true;
        moveFocus(-1);
        return true;
    }
    if (pressed & PadButtons::Right)
    {
        if (detail_open_)
            return true;
        moveFocus(1);
        return true;
    }
    if (pressed & PadButtons::Up)
    {
        if (detail_open_)
        {
            play_focused_ = 1;
            return true;
        }
        return true;
    }
    if (pressed & PadButtons::Down)
    {
        if (detail_open_)
        {
            play_focused_ = 1;
            return true;
        }
        return true;
    }
    if (pressed & PadButtons::Cross)
    {
        if (detail_open_)
        {
            if (play_focused_)
                playFocused();
            return true;
        }
        openDetail();
        return true;
    }
    if (pressed & PadButtons::Circle)
    {
        if (detail_open_)
        {
            closeDetail();
            return true;
        }
        return true;
    }
    if (pressed & PadButtons::Options)
    {
        /* Re-run the small metadata fetch, including the intentional fail path. */
        startMetadataFetch();
        return true;
    }
    return false;
}

void NuvioPocScreen::update(double deltaMs)
{
    (void)deltaMs;
    if (catalog_ready_.exchange(0))
    {
        std::lock_guard<std::mutex> lock(catalog_mx_);
        applyCatalogLocked();
    }
}

void NuvioPocScreen::render(uint32_t *framebuffer, int width, int height)
{
    nuvio_poc_params_t params;
    fillParams(&params);
    evo_rmlui_update_nuvio_poc(&params);
    evo_rmlui_render_nuvio_poc(framebuffer, width, height);
}

} // namespace evo
