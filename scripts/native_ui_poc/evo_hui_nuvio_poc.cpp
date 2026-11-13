/*
 * Nuvio native UI proof draw path. GPL-3.0-or-later.
 * Multi-shelf layout, themes, metadata pills, and detail view.
 */
#include "evo_hui_nuvio_poc.hpp"

#include "ui/fonts.hpp"
#include "ui/glyphs.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <functional>

namespace evo::kit
{
namespace
{

using hui::gfx::Align;
using hui::gfx::Color;
using hui::gfx::DrawList;
using hui::gfx::Rect;
namespace ui = hui::ui;

constexpr float kShelfStrideY = 420.0f;
constexpr float kBaseShelvesY = 500.0f;

Color hex(uint32_t rgb, float a = 1.0f)
{
    return Color::rgb(rgb, a);
}

} // namespace

float NuvioPocScreen::content_x() const
{
    return theme_.content_x > 1.0f ? theme_.content_x : 168.0f;
}

float NuvioPocScreen::card_gap() const
{
    return theme_.card_gap > 1.0f ? theme_.card_gap : 16.0f;
}

void NuvioPocScreen::set(const nuvio_poc_params_t &params)
{
    theme_ = params.theme.poster_w > 1.0f ? params.theme : nuvio_poc_default_theme();
    brand_ = params.brand ? params.brand : "Nuvio";
    hero_title_ = params.hero_title ? params.hero_title : "";
    hero_detail_ = params.hero_detail ? params.hero_detail : "";
    hero_overview_ = params.hero_overview ? params.hero_overview : "";
    hero_quality_ = params.hero_quality ? params.hero_quality : "";
    hero_rating_ = params.hero_rating ? params.hero_rating : "";
    hero_year_ = params.hero_year ? params.hero_year : "";
    hero_duration_ = params.hero_duration ? params.hero_duration : "";
    hero_genres_ = params.hero_genres ? params.hero_genres : "";
    status_ = params.status ? params.status : "";
    status_is_error_ = params.status_is_error;

    focused_shelf_ = std::max(0, params.focused_shelf);
    focused_area_ = params.focused_area;
    hero_button_focus_ = params.hero_button_focus;

    detail_open_ = params.detail_open ? 1 : 0;
    play_focused_ = params.play_focused ? 1 : 0;
    hero_art_ = params.hero_art;
    hero_art_w_ = params.hero_art_w;
    hero_art_h_ = params.hero_art_h;

    shelves_.clear();
    if (params.shelf_count > 0)
    {
        const int s_count = std::min(params.shelf_count, static_cast<int>(NUVIO_POC_MAX_SHELVES));
        shelves_.reserve(static_cast<std::size_t>(s_count));
        for (int s = 0; s < s_count; ++s)
        {
            Shelf shelf;
            shelf.title = params.shelves[s].title;
            shelf.focus_index = std::max(0, params.shelves[s].focus_index);
            shelf.scroll_index = std::max(0, params.shelves[s].scroll_index);
            const int count = std::min(params.shelves[s].item_count, static_cast<int>(NUVIO_POC_MAX_ITEMS_PER_SHELF));
            shelf.items.reserve(static_cast<std::size_t>(count));
            for (int i = 0; i < count; ++i)
            {
                const auto &src = params.shelves[s].items[i];
                Item item;
                item.title = src.title;
                item.subtitle = src.subtitle;
                item.overview = src.overview;
                item.quality_badge = src.quality_badge;
                item.rating = src.rating;
                item.year = src.year;
                item.duration = src.duration;
                item.genres = src.genres;
                item.progress = src.progress;
                item.poster = src.poster;
                item.poster_w = src.poster_w;
                item.poster_h = src.poster_h;
                shelf.items.push_back(std::move(item));
            }
            if (!shelf.items.empty())
                shelf.focus_index = std::min(shelf.focus_index, static_cast<int>(shelf.items.size()) - 1);
            shelves_.push_back(std::move(shelf));
        }
    }
    else
    {
        /* Legacy single shelf compatibility */
        Shelf shelf;
        shelf.title = params.shelf_title ? params.shelf_title : "Popular - Movie";
        shelf.focus_index = std::max(0, params.focus_index);
        shelf.scroll_index = std::max(0, params.scroll_index);
        const int count = std::min(params.item_count, static_cast<int>(NUVIO_POC_MAX_ITEMS));
        for (int i = 0; i < count; ++i)
        {
            const auto &src = params.items[i];
            Item item;
            item.title = src.title;
            item.subtitle = src.subtitle;
            item.overview = src.overview;
            item.poster = src.poster;
            item.poster_w = src.poster_w;
            item.poster_h = src.poster_h;
            shelf.items.push_back(std::move(item));
        }
        if (!shelf.items.empty())
            shelf.focus_index = std::min(shelf.focus_index, static_cast<int>(shelf.items.size()) - 1);
        shelves_.push_back(std::move(shelf));
    }

    if (!shelves_.empty())
        focused_shelf_ = std::min(focused_shelf_, static_cast<int>(shelves_.size()) - 1);
}

void NuvioPocScreen::enter()
{
    age_ = 0.0f;
    ring_snapped_ = false;
    scroll_y_ = 0.0f;
    for (int s = 0; s < NUVIO_POC_MAX_SHELVES; ++s)
        scroll_x_[s] = 0.0f;
}

void NuvioPocScreen::update(float dt)
{
    age_ += dt;

    /* Smooth vertical camera scrolling */
    float target_y = 0.0f;
    if (focused_area_ == 0 && focused_shelf_ > 0)
        target_y = static_cast<float>(focused_shelf_) * kShelfStrideY;
    scroll_y_ += (target_y - scroll_y_) * std::min(1.0f, dt * 11.0f);

    /* Smooth horizontal camera scrolling per shelf */
    for (std::size_t s = 0; s < shelves_.size() && s < NUVIO_POC_MAX_SHELVES; ++s)
    {
        const float target_x = static_cast<float>(shelves_[s].scroll_index);
        scroll_x_[s] += (target_x - scroll_x_[s]) * std::min(1.0f, dt * 14.0f);
    }

    const Rect target_ring = focus_rect();
    if (!ring_snapped_ && target_ring.w > 0.0f)
    {
        ring_.snap(target_ring);
        ring_snapped_ = true;
    }
    else if (target_ring.w > 0.0f)
    {
        ring_.target(target_ring);
    }
    ring_.update(dt, 24.0f);
}

Rect NuvioPocScreen::poster_rect(int shelf_idx, int item_idx) const
{
    const float stride = theme_.poster_w + card_gap();
    const float sx = (shelf_idx >= 0 && shelf_idx < NUVIO_POC_MAX_SHELVES) ? scroll_x_[shelf_idx] : 0.0f;
    const float x = content_x() + (static_cast<float>(item_idx) - sx) * stride;
    const float y = kBaseShelvesY + static_cast<float>(shelf_idx) * kShelfStrideY - scroll_y_ + 44.0f;
    return {x, y, theme_.poster_w, theme_.poster_h};
}

Rect NuvioPocScreen::focus_rect() const
{
    if (detail_open_)
    {
        if (play_focused_)
        {
            const float text_x = content_x() + 48.0f + theme_.poster_w + 48.0f;
            return {text_x, 180.0f + 470.0f, 220.0f, 64.0f};
        }
        return {content_x(), 180.0f, 1920.0f - content_x() - 48.0f, 720.0f};
    }
    if (focused_area_ == 1)
    {
        const float btn_y = 410.0f - scroll_y_;
        if (hero_button_focus_ == 0)
            return {content_x() + 8.0f, btn_y, 180.0f, 48.0f};
        else
            return {content_x() + 8.0f + 196.0f, btn_y, 150.0f, 48.0f};
    }
    if (shelves_.empty() || focused_shelf_ < 0 || focused_shelf_ >= static_cast<int>(shelves_.size()))
        return {content_x(), kBaseShelvesY + 44.0f, theme_.poster_w, theme_.poster_h};
    const Shelf &shelf = shelves_[static_cast<std::size_t>(focused_shelf_)];
    if (shelf.items.empty())
        return {content_x(), kBaseShelvesY + static_cast<float>(focused_shelf_) * kShelfStrideY - scroll_y_ + 44.0f,
                theme_.poster_w, theme_.poster_h};
    return poster_rect(focused_shelf_, shelf.focus_index);
}

std::uint32_t NuvioPocScreen::art_texture(const Context &ctx, const std::uint32_t *art, int w, int h,
                                          const std::string &tag) const
{
    if (!art || w <= 0 || h <= 0)
        return 0;
    return ctx.textures.pixels(art, w, h, static_cast<std::uint64_t>(std::hash<std::string>{}(tag)));
}

void NuvioPocScreen::draw_sidebar(DrawList &list, const Context &ctx) const
{
    const float w = theme_.sidebar_w > 1.0f ? theme_.sidebar_w : 144.0f;
    const Color rail = hex(0x111111);
    const Color well = hex(0x1a1a1a);
    const Color accent = hex(theme_.accent);
    const Color muted = hex(theme_.text_muted);
    list.rounded_rect({0, 0, w, 1080}, 0, rail);

    const char *labels[] = {"Home", "Search", "Library", "Settings"};
    for (int i = 0; i < 4; ++i)
    {
        const float y = 120.0f + static_cast<float>(i) * 110.0f;
        const Rect icon{w * 0.5f - 28.0f, y, 56.0f, 56.0f};
        const bool active = (i == 0);
        list.rounded_rect(icon, 16.0f, active ? accent.with_alpha(0.24f) : well);
        if (active)
            list.bordered_rect(icon, 16.0f, Color::rgb(0x000000, 0.0f), 2.0f, accent);
        ui::text(list, ctx.fonts.regular, labels[i], w * 0.5f, y + 78.0f, 14.0f,
                 active ? hex(theme_.text) : muted, Align::center);
    }
}

void NuvioPocScreen::draw_hero(DrawList &list, const Context &ctx) const
{
    const auto &fonts = ctx.fonts;
    const Color text = hex(theme_.text);
    const Color muted = hex(theme_.text_muted);
    const Color accent = hex(theme_.accent);
    const float left = content_x();

    /* Fade hero out when scrolled deep into shelves */
    const float hero_alpha = std::clamp(1.0f - (scroll_y_ / 320.0f), 0.0f, 1.0f);
    if (hero_alpha <= 0.01f)
        return;

    list.push_opacity(hero_alpha);

    /* Subtle backdrop art on the right half, fading cleanly into pure dark on the left and bottom */
    const Rect hero_rect{740.0f, 0.0f, 1180.0f, 560.0f};
    if (hero_art_ && hero_art_w_ > 0 && hero_art_h_ > 0)
    {
        const std::uint32_t tex = art_texture(ctx, hero_art_, hero_art_w_, hero_art_h_, "poc-hero");
        if (tex)
            list.image(tex, hero_rect, ::hui::gfx::kFullUv, Color::rgb(0xffffff, 0.65f));
    }
    /* Left dark fade over backdrop so text is crystal clear */
    list.gradient_rect_h({640.0f, 0.0f, 480.0f, 560.0f}, 0, hex(theme_.bg_top, 1.0f), hex(theme_.bg_top, 0.0f));
    /* Bottom fade into the shelf area */
    list.gradient_rect({740.0f, 380.0f, 1180.0f, 180.0f}, 0, hex(theme_.bg_bottom, 0.0f), hex(theme_.bg_bottom, 1.0f));

    /* Brand mark & Theme name */
    ui::text(list, fonts.semibold, brand_, left + 8.0f, 56.0f, 22.0f, text);
    if (theme_.name && theme_.name[0])
    {
        const float theme_pill_x = left + 92.0f;
        const Rect theme_pill{theme_pill_x, 40.0f, 110.0f, 24.0f};
        list.bordered_rect(theme_pill, 12.0f, accent.with_alpha(0.12f), 1.0f, accent.with_alpha(0.5f));
        ui::text(list, fonts.regular, theme_.name, theme_pill.cx(), 56.0f, 12.0f, accent, Align::center);
    }

    /* Active title */
    std::string title = hero_title_;
    std::string detail = hero_detail_;
    std::string overview = hero_overview_;
    std::string quality = hero_quality_.empty() ? "4K HDR" : hero_quality_;
    std::string rating = hero_rating_.empty() ? "7.8" : hero_rating_;
    std::string duration = hero_duration_;
    std::string genres = hero_genres_;

    if (title.empty() && !shelves_.empty())
    {
        const Shelf &s = shelves_[static_cast<std::size_t>(focused_shelf_)];
        if (!s.items.empty())
        {
            const Item &it = s.items[static_cast<std::size_t>(s.focus_index)];
            title = it.title;
            detail = it.subtitle;
            overview = it.overview;
            if (!it.quality_badge.empty()) quality = it.quality_badge;
            if (!it.rating.empty()) rating = it.rating;
            if (!it.duration.empty()) duration = it.duration;
            if (!it.genres.empty()) genres = it.genres;
        }
    }

    /* Headline */
    ui::text(list, fonts.display, fonts.display.font->fit(title, 48.0f, 820.0f), left + 8.0f, 190.0f, 48.0f, text);

    /* Metadata Badges / Pills row */
    float pill_x = left + 8.0f;
    const float pill_y = 208.0f;
    const float pill_h = 24.0f;

    auto draw_pill = [&](const std::string &txt, Color border_col, Color txt_col) {
        if (txt.empty()) return;
        const float txt_w = fonts.regular.font->measure(txt, 12.0f);
        const float pill_w = txt_w + 16.0f;
        const Rect r{pill_x, pill_y, pill_w, pill_h};
        list.bordered_rect(r, 6.0f, hex(0x1a1a1a, 0.7f), 1.0f, border_col);
        ui::text(list, fonts.regular, txt, r.cx(), pill_y + 16.0f, 12.0f, txt_col, Align::center);
        pill_x += pill_w + 8.0f;
    };

    draw_pill(quality, accent, accent);
    draw_pill("★ " + rating, hex(0xe8a91c), hex(0xffd45c));
    if (!duration.empty())
        draw_pill(duration, hex(0x444444), muted);
    if (!genres.empty())
        draw_pill(genres, hex(0x444444), muted);
    else if (!detail.empty())
        draw_pill(detail, hex(0x444444), muted);

    /* Multiline synopsis */
    if (!overview.empty())
        ui::paragraph(list, fonts.regular, overview, left + 8.0f, 260.0f, 17.0f, 760.0f, 25.0f, muted, 4);

    /* Hero Action Buttons */
    const float btn_y = 390.0f;
    const Rect btn_play{left + 8.0f, btn_y, 180.0f, 48.0f};
    const Rect btn_details{left + 8.0f + 196.0f, btn_y, 150.0f, 48.0f};

    const bool play_active = (focused_area_ == 1 && hero_button_focus_ == 0);
    const bool details_active = (focused_area_ == 1 && hero_button_focus_ == 1);

    list.rounded_rect(btn_play, 24.0f, play_active ? hex(theme_.focus_bg) : hex(theme_.surface));
    list.bordered_rect(btn_play, 24.0f, Color::rgb(0, 0), play_active ? 2.5f : 1.0f,
                       play_active ? hex(theme_.focus_color) : hex(theme_.border_color));
    ui::text(list, fonts.semibold, "▶  Watch Now", btn_play.cx(), btn_play.cy() + 6.0f, 16.0f,
             play_active ? hex(theme_.focus_color) : text, Align::center);

    list.rounded_rect(btn_details, 24.0f, details_active ? hex(theme_.focus_bg) : hex(theme_.surface));
    list.bordered_rect(btn_details, 24.0f, Color::rgb(0, 0), details_active ? 2.5f : 1.0f,
                       details_active ? hex(theme_.focus_color) : hex(theme_.border_color));
    ui::text(list, fonts.semibold, "+  Details", btn_details.cx(), btn_details.cy() + 6.0f, 16.0f,
             details_active ? hex(theme_.focus_color) : muted, Align::center);

    if (!status_.empty())
    {
        const Color status_color = status_is_error_ ? Color::rgb(0xff7a7a) : muted;
        ui::text(list, fonts.semibold, status_, 1920.0f - 48.0f, 56.0f, 16.0f, status_color, Align::right);
    }

    list.pop_opacity();
}

void NuvioPocScreen::draw_shelves(DrawList &list, const Context &ctx) const
{
    const auto &fonts = ctx.fonts;
    const Color text = hex(theme_.text);
    const Color muted = hex(theme_.text_muted);
    const Color surface = hex(theme_.surface);
    const Color accent = hex(theme_.accent);
    const float left = content_x();
    const float stride = theme_.poster_w + card_gap();

    for (std::size_t s = 0; s < shelves_.size(); ++s)
    {
        const Shelf &shelf = shelves_[s];
        const float row_base_y = kBaseShelvesY + static_cast<float>(s) * kShelfStrideY - scroll_y_;
        if (row_base_y + kShelfStrideY < 0.0f || row_base_y > 1080.0f)
            continue; /* Offscreen */

        /* Shelf Title */
        const bool shelf_focused = (focused_area_ == 0 && static_cast<int>(s) == focused_shelf_);
        ui::text(list, fonts.display, shelf.title, left, row_base_y + 24.0f, 26.0f,
                 shelf_focused ? text : muted);

        if (shelf.items.empty())
        {
            const Rect empty{left, row_base_y + 44.0f, 500.0f, theme_.poster_h};
            list.rounded_rect(empty, theme_.poster_radius, surface);
            ui::text(list, fonts.regular, "No items available", empty.cx(), empty.cy(), 18.0f, muted, Align::center);
            continue;
        }

        /* Poster cards */
        for (std::size_t i = 0; i < shelf.items.size(); ++i)
        {
            const Rect poster = poster_rect(static_cast<int>(s), static_cast<int>(i));
            if (poster.x > 1920.0f || poster.x + poster.w < left - stride)
                continue;

            const Item &item = shelf.items[i];
            list.shadow(poster, theme_.poster_radius, 14.0f, Color::rgb(0x000000, 0.5f));

            const std::uint32_t tex =
                art_texture(ctx, item.poster, item.poster_w, item.poster_h, "shelf-" + std::to_string(s) + "-" + std::to_string(i));
            if (tex)
            {
                list.image(tex, poster, ::hui::gfx::kFullUv, Color::rgb(0xffffff));
            }
            else
            {
                list.gradient_rect(poster, theme_.poster_radius, surface, hex(theme_.bg_bottom));
                /* Subtle title label at bottom of card */
                list.gradient_rect({poster.x, poster.y + poster.h - 90.0f, poster.w, 90.0f},
                                   theme_.poster_radius, Color::rgb(0x000000, 0.0f), hex(0x000000, 0.85f));
                ui::text(list, fonts.semibold, fonts.semibold.font->fit(item.title, 16.0f, poster.w - 24.0f),
                         poster.x + 12.0f, poster.y + poster.h - 32.0f, 16.0f, text);
                if (!item.subtitle.empty())
                    ui::text(list, fonts.regular, fonts.regular.font->fit(item.subtitle, 12.0f, poster.w - 24.0f),
                             poster.x + 12.0f, poster.y + poster.h - 14.0f, 12.0f, muted);
            }

            /* Progress bar for Continue Watching items */
            if (item.progress > 0.01f)
            {
                const float bar_y = poster.y + poster.h - 8.0f;
                const float bar_w = poster.w - 20.0f;
                const Rect track{poster.x + 10.0f, bar_y, bar_w, 4.0f};
                list.rounded_rect(track, 2.0f, hex(0x2a2a2a, 0.9f));
                const Rect fill{poster.x + 10.0f, bar_y, bar_w * std::clamp(item.progress, 0.0f, 1.0f), 4.0f};
                list.rounded_rect(fill, 2.0f, accent);
            }
        }
    }

    /* Active Focus Ring with subtle outer glow */
    if (!detail_open_)
    {
        const Rect ring = ring_.value();
        if (ring.w > 0.0f)
        {
            list.bordered_rect(ring.inset(-theme_.focus_ring), theme_.poster_radius + theme_.focus_ring,
                               Color::rgb(0x000000, 0.0f), theme_.focus_ring, hex(theme_.focus_color, 0.95f));
            list.glow(ring, theme_.poster_radius, 12.0f, hex(theme_.focus_color, 0.35f));
        }
    }
}

void NuvioPocScreen::draw_detail(DrawList &list, const Context &ctx) const
{
    if (!detail_open_)
        return;

    const auto &fonts = ctx.fonts;
    const Color text = hex(theme_.text);
    const Color muted = hex(theme_.text_muted);
    const Color surface = hex(theme_.surface);
    const Color accent = hex(theme_.accent);
    const Color focus_col = hex(theme_.focus_color);
    const float left = content_x();

    /* Dim background */
    list.rounded_rect({0, 0, 1920, 1080}, 0, Color::rgb(0x000000, 0.82f));

    /* Detail Modal Card */
    const Rect card{left, 160.0f, 1920.0f - left - 64.0f, 720.0f};
    list.shadow(card, 20.0f, 24.0f, Color::rgb(0x000000, 0.7f));
    list.rounded_rect(card, 20.0f, surface);
    list.bordered_rect(card, 20.0f, Color::rgb(0, 0), 1.0f, hex(theme_.border_color));

    /* Selected Item Data */
    std::string title = "Title";
    std::string detail = "Details";
    std::string overview = "Overview";
    const uint32_t *poster_data = nullptr;
    int poster_w = 0, poster_h = 0;

    if (!shelves_.empty())
    {
        const Shelf &s = shelves_[static_cast<std::size_t>(focused_shelf_)];
        if (!s.items.empty())
        {
            const Item &it = s.items[static_cast<std::size_t>(s.focus_index)];
            title = it.title;
            detail = it.subtitle;
            overview = it.overview;
            poster_data = it.poster;
            poster_w = it.poster_w;
            poster_h = it.poster_h;
        }
    }

    /* Big Poster on left */
    const Rect poster{left + 48.0f, 208.0f, theme_.poster_w * 1.15f, theme_.poster_h * 1.15f};
    list.shadow(poster, theme_.poster_radius, 16.0f, Color::rgb(0x000000, 0.5f));
    const std::uint32_t tex = art_texture(ctx, poster_data, poster_w, poster_h, "detail-poster");
    if (tex)
        list.image(tex, poster, ::hui::gfx::kFullUv, Color::rgb(0xffffff));
    else
        list.gradient_rect(poster, theme_.poster_radius, hex(theme_.surface), hex(theme_.bg_bottom));

    /* Detail text on right */
    const float text_x = poster.x + poster.w + 48.0f;
    ui::text(list, fonts.display, fonts.display.font->fit(title, 44.0f, 960.0f), text_x, 260.0f, 44.0f, text);
    ui::text(list, fonts.regular, fonts.regular.font->fit(detail, 20.0f, 960.0f), text_x, 308.0f, 20.0f, accent);
    ui::paragraph(list, fonts.regular, overview, text_x, 350.0f, 18.0f, 960.0f, 28.0f, muted, 8);

    /* Play Button */
    const Rect btn_play{text_x, 180.0f + 470.0f, 220.0f, 64.0f};
    list.rounded_rect(btn_play, 32.0f, play_focused_ ? hex(theme_.focus_bg) : accent);
    if (play_focused_)
        list.bordered_rect(btn_play, 32.0f, Color::rgb(0, 0), theme_.focus_ring, focus_col);
    ui::text(list, fonts.semibold, "▶   Play", btn_play.cx(), btn_play.cy() + 7.0f, 20.0f,
             play_focused_ ? focus_col : text, Align::center);
}

void NuvioPocScreen::draw_hints(DrawList &list, const Context &ctx) const
{
    const auto &fonts = ctx.fonts;
    const Color muted = hex(theme_.text_muted);
    const float y = 1045.0f;
    float rx = 1920.0f - 48.0f;

    auto hint = [&](const char *glyph, const char *lbl) {
        const float lbl_w = fonts.regular.font->measure(lbl, 14.0f);
        const float gly_w = fonts.semibold.font->measure(glyph, 16.0f);
        rx -= lbl_w;
        ui::text(list, fonts.regular, lbl, rx, y, 14.0f, muted);
        rx -= (gly_w + 6.0f);
        ui::text(list, fonts.semibold, glyph, rx, y, 16.0f, hex(theme_.focus_color));
        rx -= 24.0f;
    };

    if (detail_open_)
    {
        hint("○", "Back");
        hint("✕", "Play");
    }
    else
    {
        hint("○", "Back");
        hint("✕", focused_area_ == 1 ? "Select" : "Details");
        hint("□", "Cycle Theme");
        if (focused_shelf_ == 0 && focused_area_ == 0)
            hint("▲", "Hero Actions");
    }
}

void NuvioPocScreen::draw(DrawList &list, const Context &ctx) const
{
    /* Deep dark canvas matching Nuvio TV */
    list.gradient_rect({0, 0, 1920, 1080}, 0, hex(theme_.bg_top), hex(theme_.bg_bottom));

    draw_hero(list, ctx);
    draw_shelves(list, ctx);
    draw_sidebar(list, ctx);
    draw_detail(list, ctx);
    draw_hints(list, ctx);
}

bool NuvioPocScreen::focus(FocusInfo *out) const
{
    if (!out)
        return false;
    out->rect = focus_rect();
    out->id = "poc-focus";
    return true;
}

} // namespace evo::kit
