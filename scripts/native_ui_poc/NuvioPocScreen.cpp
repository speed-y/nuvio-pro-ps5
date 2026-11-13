/*
 * Nuvio native UI proof core screen. GPL-3.0-or-later.
 * Multi-shelf focus, theme presets, metadata pills, and Play handoff.
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

/* Built-in multi-shelf catalogue matching modern Nuvio TV */
void fill_builtin(std::vector<NuvioPocScreen::CatalogShelf> *out)
{
    out->clear();

    /* Shelf 0: Continue Watching */
    {
        NuvioPocScreen::CatalogShelf shelf;
        shelf.title = "Continue Watching";

        struct Seed {
            const char *title;
            const char *sub;
            const char *overview;
            const char *quality;
            const char *rating;
            const char *year;
            const char *duration;
            const char *genres;
            float progress;
            uint32_t a, b;
        };
        static const Seed kCwSeeds[] = {
            {"The Substance", "Movie · 2024",
             "A fading celebrity decides to use a black market drug, a cell-replicating substance that temporarily creates a younger, better version of herself.",
             "4K HDR", "7.5", "2024", "2h 21m", "Horror · Sci-Fi", 0.72f, 0x1f0b24, 0xd16ba5},
            {"Dune: Part Two", "Movie · 2024",
             "Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.",
             "4K HDR", "8.5", "2024", "2h 46m", "Sci-Fi · Adventure", 0.45f, 0x2e1a08, 0xf2a541},
            {"Severance", "Series · S1:E7",
             "Mark leads a team of office workers whose memories have been surgically divided between their work and personal lives.",
             "4K HDR", "8.7", "2024", "55m", "Drama · Sci-Fi", 0.88f, 0x0b1f24, 0x5aa9e6},
            {"Shōgun", "Series · S1:E4",
             "When a mysterious European ship is found marooned in a nearby fishing village, Lord Toranaga discovers secrets that could tip the scales of power.",
             "4K HDR", "8.7", "2024", "1h 00m", "Drama · History", 0.30f, 0x241208, 0x9bd16b},
        };

        for (std::size_t i = 0; i < sizeof(kCwSeeds) / sizeof(kCwSeeds[0]); ++i)
        {
            const auto &s = kCwSeeds[i];
            NuvioPocScreen::CatalogItem it;
            it.title = s.title;
            it.subtitle = s.sub;
            it.overview = s.overview;
            it.quality_badge = s.quality;
            it.rating = s.rating;
            it.year = s.year;
            it.duration = s.duration;
            it.genres = s.genres;
            it.progress = s.progress;
            it.play_url = "/data/nuvio-poc/poc_sample.mp4";
            it.poster_w = 221;
            it.poster_h = 339;
            it.poster = NuvioPocScreen::makePoster(s.a, s.b, static_cast<float>(i) + 0.1f);
            shelf.items.push_back(std::move(it));
        }
        out->push_back(std::move(shelf));
    }

    /* Shelf 1: Popular Movies */
    {
        NuvioPocScreen::CatalogShelf shelf;
        shelf.title = "Popular Movies";

        struct Seed {
            const char *title;
            const char *sub;
            const char *overview;
            const char *quality;
            const char *rating;
            const char *year;
            const char *duration;
            const char *genres;
            uint32_t a, b;
        };
        static const Seed kPopSeeds[] = {
            {"Halloween", "Movie · 1978",
             "Fifteen years after murdering his sister, Michael Myers escapes from a mental hospital and returns to Haddonfield.",
             "4K HDR", "7.8", "1978", "1h 31m", "Horror · Thriller", 0x3a1c0b, 0xf2a541},
            {"Resident Evil", "Movie · 2002",
             "A special military unit fights a powerful, out-of-control supercomputer and hundreds of scientists who have mutated into flesh-eating creatures.",
             "1080p", "6.6", "2002", "1h 40m", "Action · Sci-Fi", 0x1a1040, 0x7b62ff},
            {"Hocus Pocus", "Movie · 1993",
             "A curious youngster moves to Salem, where he struggles to fit in before awakening a trio of diabolical witches that were executed in the 17th century.",
             "4K HDR", "6.9", "1993", "1h 36m", "Comedy · Family", 0x2b1055, 0xd16ba5},
            {"Interstellar", "Movie · 2014",
             "When Earth becomes uninhabitable in the future, a farmer and ex-NASA pilot, Joseph Cooper, is tasked to pilot a spacecraft along with a team of researchers.",
             "4K HDR", "8.7", "2014", "2h 49m", "Sci-Fi · Adventure", 0x081524, 0x4da9ff},
            {"The Dark Knight", "Movie · 2008",
             "When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests.",
             "4K HDR", "9.0", "2008", "2h 32m", "Action · Crime", 0x14181f, 0x7a8b9e},
            {"Alien: Romulus", "Movie · 2024",
             "While scavenging the deep ends of a derelict space station, a group of young space colonizers come face to face with the most terrifying life form in the universe.",
             "4K HDR", "7.2", "2024", "1h 59m", "Sci-Fi · Horror", 0x0d2012, 0x31a86a},
        };

        for (std::size_t i = 0; i < sizeof(kPopSeeds) / sizeof(kPopSeeds[0]); ++i)
        {
            const auto &s = kPopSeeds[i];
            NuvioPocScreen::CatalogItem it;
            it.title = s.title;
            it.subtitle = s.sub;
            it.overview = s.overview;
            it.quality_badge = s.quality;
            it.rating = s.rating;
            it.year = s.year;
            it.duration = s.duration;
            it.genres = s.genres;
            it.progress = 0.0f;
            it.play_url = "/data/nuvio-poc/poc_sample.mp4";
            it.poster_w = 221;
            it.poster_h = 339;
            it.poster = NuvioPocScreen::makePoster(s.a, s.b, static_cast<float>(i) + 1.5f);
            shelf.items.push_back(std::move(it));
        }
        out->push_back(std::move(shelf));
    }

    /* Shelf 2: Trending Series */
    {
        NuvioPocScreen::CatalogShelf shelf;
        shelf.title = "Trending Series";

        struct Seed {
            const char *title;
            const char *sub;
            const char *overview;
            const char *quality;
            const char *rating;
            const char *year;
            const char *duration;
            const char *genres;
            uint32_t a, b;
        };
        static const Seed kSeriesSeeds[] = {
            {"The Penguin", "Series · 2024",
             "Following the events of The Batman, Oz Cobb strives to seize control of the criminal empire left behind by Carmine Falcone.",
             "4K HDR", "8.8", "2024", "1h 05m", "Crime · Drama", 0x1f140d, 0xd47a22},
            {"Arcane", "Series · 2024",
             "Set in the utopian region of Piltover and the oppressed underground of Zaun, the story follows the origins of two iconic League champions.",
             "4K HDR", "9.0", "2024", "42m", "Animation · Action", 0x1f0b24, 0xbf3be8},
            {"House of the Dragon", "Series · 2024",
             "The Targaryen dynasty is at the absolute apex of its power, with more than 15 dragons under their yoke.",
             "4K HDR", "8.4", "2024", "1h 02m", "Fantasy · Drama", 0x2e0808, 0xdb3b3b},
            {"Breaking Bad", "Series · 2008",
             "A chemistry teacher diagnosed with inoperable lung cancer turns to manufacturing and selling methamphetamine.",
             "4K HDR", "9.5", "2008", "47m", "Crime · Drama", 0x142408, 0x82db3b},
            {"Stranger Things", "Series · 2024",
             "When a young boy vanishes, a small town uncovers a mystery involving secret experiments, terrifying supernatural forces and one strange little girl.",
             "4K HDR", "8.7", "2024", "52m", "Sci-Fi · Horror", 0x1f0814, 0xe02d75},
        };

        for (std::size_t i = 0; i < sizeof(kSeriesSeeds) / sizeof(kSeriesSeeds[0]); ++i)
        {
            const auto &s = kSeriesSeeds[i];
            NuvioPocScreen::CatalogItem it;
            it.title = s.title;
            it.subtitle = s.sub;
            it.overview = s.overview;
            it.quality_badge = s.quality;
            it.rating = s.rating;
            it.year = s.year;
            it.duration = s.duration;
            it.genres = s.genres;
            it.progress = 0.0f;
            it.play_url = "/data/nuvio-poc/poc_sample.mp4";
            it.poster_w = 221;
            it.poster_h = 339;
            it.poster = NuvioPocScreen::makePoster(s.a, s.b, static_cast<float>(i) + 2.7f);
            shelf.items.push_back(std::move(it));
        }
        out->push_back(std::move(shelf));
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

int parse_simple_catalog(const std::string &json, std::vector<NuvioPocScreen::CatalogShelf> *out)
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

    NuvioPocScreen::CatalogShelf custom_shelf;
    custom_shelf.title = "Custom Catalogue";

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
            else if (key == "quality")
                item.quality_badge = value;
            else if (key == "rating")
                item.rating = value;
            if (json.find('}', pos) < json.find('"', pos))
                break;
        }
        if (item.title.empty())
            continue;
        item.poster_w = 221;
        item.poster_h = 339;
        const uint32_t a = 0x102030u + static_cast<uint32_t>(custom_shelf.items.size()) * 0x1020u;
        const uint32_t b = 0x60a0c0u + static_cast<uint32_t>(custom_shelf.items.size()) * 0x0810u;
        item.poster = NuvioPocScreen::makePoster(a, b, static_cast<float>(custom_shelf.items.size()) + 1.0f);
        custom_shelf.items.push_back(std::move(item));
        if (custom_shelf.items.size() >= NUVIO_POC_MAX_ITEMS_PER_SHELF)
            break;
    }
    if (!custom_shelf.items.empty())
    {
        out->push_back(std::move(custom_shelf));
        return 0;
    }
    return -1;
}

} // namespace

std::vector<uint32_t> NuvioPocScreen::makePoster(uint32_t a, uint32_t b, float seed)
{
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
    theme_preset_ = static_cast<int>(NUVIO_THEME_ARCTIC_BLUE);
    theme_ = nuvio_poc_get_theme_preset(static_cast<nuvio_theme_preset_t>(theme_preset_));
    hero_w_ = 1280;
    hero_h_ = 720;
    hero_art_.assign(static_cast<std::size_t>(hero_w_ * hero_h_), 0);
    {
        auto full = makePoster(0x0b1424, 0x3185f5, 0.2f);
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
    status_ = "Loading shelves…";
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
    focused_shelf_ = 0;
    focused_area_ = 0;
    hero_button_focus_ = 0;
    if (auto *sfx = Application::getInstance().getSoundEffectEngine())
    {
        sounds_were_enabled_ = sfx->isEnabled();
        sfx->setEnabled(false);
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
    status_ = "Loading shelves…";
    status_is_error_ = 0;
    if (fetch_thread_.joinable())
        fetch_thread_.join();
    fetch_thread_ = std::thread([this]() {
        std::vector<CatalogShelf> loaded;
        std::string status = "Sample shelves";
        int error = 0;

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
            fill_builtin(&loaded);
            if (!error)
                status = "Home";
        }

        {
            std::lock_guard<std::mutex> lock(catalog_mx_);
            pending_shelves_ = std::move(loaded);
            pending_status_ = status;
            pending_error_ = error;
            catalog_ready_.store(1);
        }
        fetch_running_.store(0);
    });
}

void NuvioPocScreen::applyCatalogLocked()
{
    shelves_ = std::move(pending_shelves_);
    status_ = pending_status_;
    status_is_error_ = pending_error_;
    focused_shelf_ = 0;
    focused_area_ = 0;
    hero_button_focus_ = 0;

    /* Populate legacy items list from Shelf 0 for backward compatibility */
    items_.clear();
    if (!shelves_.empty())
    {
        items_ = shelves_[0].items;
        focus_index_ = shelves_[0].focus_index;
        scroll_index_ = shelves_[0].scroll_index;
    }
}

void NuvioPocScreen::moveFocusX(int delta)
{
    if (focused_area_ == 1)
    {
        /* In Hero Actions row: toggle between Play and Details */
        hero_button_focus_ = (hero_button_focus_ == 0) ? 1 : 0;
        return;
    }

    if (shelves_.empty() || focused_shelf_ < 0 || focused_shelf_ >= static_cast<int>(shelves_.size()))
        return;

    CatalogShelf &s = shelves_[static_cast<std::size_t>(focused_shelf_)];
    if (s.items.empty())
        return;

    const int count = static_cast<int>(s.items.size());
    s.focus_index = std::clamp(s.focus_index + delta, 0, count - 1);

    if (s.focus_index > s.scroll_index + kVisible - 2)
        s.scroll_index = std::min(s.focus_index - (kVisible - 2), count - 1);
    if (s.focus_index < s.scroll_index)
        s.scroll_index = s.focus_index;

    /* Update legacy fields if focused on Shelf 0 */
    if (focused_shelf_ == 0)
    {
        focus_index_ = s.focus_index;
        scroll_index_ = s.scroll_index;
    }
}

void NuvioPocScreen::moveFocusY(int delta)
{
    if (focused_area_ == 1)
    {
        /* From Hero Action Buttons, pressing Down returns to Shelf 0 */
        if (delta > 0)
            focused_area_ = 0;
        return;
    }

    if (shelves_.empty())
        return;

    if (delta < 0)
    {
        /* Navigating UP */
        if (focused_shelf_ > 0)
        {
            focused_shelf_--;
        }
        else if (focused_shelf_ == 0)
        {
            /* Move into Hero Action buttons */
            focused_area_ = 1;
            hero_button_focus_ = 0;
        }
    }
    else if (delta > 0)
    {
        /* Navigating DOWN */
        if (focused_shelf_ + 1 < static_cast<int>(shelves_.size()))
        {
            focused_shelf_++;
        }
    }
}

void NuvioPocScreen::cycleTheme()
{
    theme_preset_ = (theme_preset_ + 1) % static_cast<int>(NUVIO_THEME_COUNT);
    theme_ = nuvio_poc_get_theme_preset(static_cast<nuvio_theme_preset_t>(theme_preset_));
}

void NuvioPocScreen::openDetail()
{
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
    if (shelves_.empty())
        return;
    const CatalogShelf &s = shelves_[static_cast<std::size_t>(focused_shelf_)];
    if (s.items.empty())
        return;

    const CatalogItem &it = s.items[static_cast<std::size_t>(s.focus_index)];
    auto *screens = Application::getInstance().getScreenManager();
    auto *playback = Application::getInstance().getPlaybackController();
    if (!screens || !playback)
        return;

    std::string url = it.play_url;
    if (url.empty())
    {
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

    detail_open_ = 0;
    play_focused_ = 0;

    PlaybackSource source;
    source.url = url;
    source.title = it.title;
    source.provider = "nuvio-poc";
    source.item_id = it.title;
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
    params->detail_open = detail_open_;
    params->play_focused = play_focused_;
    params->hero_art = hero_art_.empty() ? nullptr : hero_art_.data();
    params->hero_art_w = hero_w_;
    params->hero_art_h = hero_h_;

    params->focused_shelf = focused_shelf_;
    params->focused_area = focused_area_;
    params->hero_button_focus = hero_button_focus_;
    params->shelf_count = std::min(static_cast<int>(shelves_.size()), static_cast<int>(NUVIO_POC_MAX_SHELVES));

    for (int s = 0; s < params->shelf_count; ++s)
    {
        const CatalogShelf &src_shelf = shelves_[static_cast<std::size_t>(s)];
        nuvio_poc_shelf_t &dst_shelf = params->shelves[s];
        std::snprintf(dst_shelf.title, sizeof(dst_shelf.title), "%s", src_shelf.title.c_str());
        dst_shelf.focus_index = src_shelf.focus_index;
        dst_shelf.scroll_index = src_shelf.scroll_index;
        dst_shelf.item_count = std::min(static_cast<int>(src_shelf.items.size()), static_cast<int>(NUVIO_POC_MAX_ITEMS_PER_SHELF));

        for (int i = 0; i < dst_shelf.item_count; ++i)
        {
            const CatalogItem &it = src_shelf.items[static_cast<std::size_t>(i)];
            auto &dst = dst_shelf.items[i];
            std::snprintf(dst.title, sizeof(dst.title), "%s", it.title.c_str());
            std::snprintf(dst.subtitle, sizeof(dst.subtitle), "%s", it.subtitle.c_str());
            std::snprintf(dst.overview, sizeof(dst.overview), "%s", it.overview.c_str());
            std::snprintf(dst.play_url, sizeof(dst.play_url), "%s", it.play_url.c_str());
            std::snprintf(dst.quality_badge, sizeof(dst.quality_badge), "%s", it.quality_badge.c_str());
            std::snprintf(dst.rating, sizeof(dst.rating), "%s", it.rating.c_str());
            std::snprintf(dst.year, sizeof(dst.year), "%s", it.year.c_str());
            std::snprintf(dst.duration, sizeof(dst.duration), "%s", it.duration.c_str());
            std::snprintf(dst.genres, sizeof(dst.genres), "%s", it.genres.c_str());
            dst.progress = it.progress;
            dst.poster = it.poster.empty() ? nullptr : it.poster.data();
            dst.poster_w = it.poster_w;
            dst.poster_h = it.poster_h;
        }
    }

    /* Set active hero item metadata */
    if (!shelves_.empty())
    {
        const CatalogShelf &active_shelf = shelves_[static_cast<std::size_t>(focused_shelf_)];
        if (!active_shelf.items.empty())
        {
            const CatalogItem &hero = active_shelf.items[static_cast<std::size_t>(active_shelf.focus_index)];
            params->hero_title = hero.title.c_str();
            params->hero_detail = hero.subtitle.c_str();
            params->hero_overview = hero.overview.c_str();
            params->hero_quality = hero.quality_badge.c_str();
            params->hero_rating = hero.rating.c_str();
            params->hero_year = hero.year.c_str();
            params->hero_duration = hero.duration.c_str();
            params->hero_genres = hero.genres.c_str();
        }
    }

    /* Legacy fields populated from current shelf */
    if (!shelves_.empty())
    {
        const CatalogShelf &s0 = shelves_[static_cast<std::size_t>(focused_shelf_)];
        params->focus_index = s0.focus_index;
        params->scroll_index = s0.scroll_index;
        params->item_count = std::min(static_cast<int>(s0.items.size()), static_cast<int>(NUVIO_POC_MAX_ITEMS));
        for (int i = 0; i < params->item_count; ++i)
        {
            const CatalogItem &it = s0.items[static_cast<std::size_t>(i)];
            std::snprintf(params->items[i].title, sizeof(params->items[i].title), "%s", it.title.c_str());
            std::snprintf(params->items[i].subtitle, sizeof(params->items[i].subtitle), "%s", it.subtitle.c_str());
            std::snprintf(params->items[i].overview, sizeof(params->items[i].overview), "%s", it.overview.c_str());
            std::snprintf(params->items[i].play_url, sizeof(params->items[i].play_url), "%s", it.play_url.c_str());
            params->items[i].poster = it.poster.empty() ? nullptr : it.poster.data();
            params->items[i].poster_w = it.poster_w;
            params->items[i].poster_h = it.poster_h;
        }
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
        moveFocusX(-1);
        return true;
    }
    if (pressed & PadButtons::Right)
    {
        if (detail_open_)
            return true;
        moveFocusX(1);
        return true;
    }
    if (pressed & PadButtons::Up)
    {
        if (detail_open_)
        {
            play_focused_ = 1;
            return true;
        }
        moveFocusY(-1);
        return true;
    }
    if (pressed & PadButtons::Down)
    {
        if (detail_open_)
        {
            play_focused_ = 1;
            return true;
        }
        moveFocusY(1);
        return true;
    }
    if (pressed & PadButtons::Square)
    {
        /* DualSense Square: live theme cycle */
        cycleTheme();
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
        if (focused_area_ == 1)
        {
            if (hero_button_focus_ == 0)
                playFocused();
            else
                openDetail();
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
        if (focused_area_ == 1)
        {
            focused_area_ = 0;
            return true;
        }
        return true;
    }
    if (pressed & PadButtons::Options)
    {
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
