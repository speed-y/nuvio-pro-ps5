/*
 * Nuvio native UI proof draw path. GPL-3.0-or-later.
 * One-screen Home-like layout measured against the packaged browser UI.
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

constexpr float kHeroH = 620.0f;
constexpr float kRowY = 700.0f;

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
    shelf_title_ = params.shelf_title ? params.shelf_title : "Popular - Movie";
    status_ = params.status ? params.status : "";
    status_is_error_ = params.status_is_error;
    focus_index_ = std::max(0, params.focus_index);
    scroll_index_ = std::max(0, params.scroll_index);
    detail_open_ = params.detail_open ? 1 : 0;
    play_focused_ = params.play_focused ? 1 : 0;
    hero_art_ = params.hero_art;
    hero_art_w_ = params.hero_art_w;
    hero_art_h_ = params.hero_art_h;

    items_.clear();
    const int count = std::max(0, std::min(params.item_count, static_cast<int>(NUVIO_POC_MAX_ITEMS)));
    items_.reserve(static_cast<std::size_t>(count));
    for (int i = 0; i < count; ++i)
    {
        Item item;
        item.title = params.items[i].title;
        item.subtitle = params.items[i].subtitle;
        item.overview = params.items[i].overview;
        item.poster = params.items[i].poster;
        item.poster_w = params.items[i].poster_w;
        item.poster_h = params.items[i].poster_h;
        items_.push_back(std::move(item));
    }
    if (!items_.empty())
        focus_index_ = std::min(focus_index_, static_cast<int>(items_.size()) - 1);
}

void NuvioPocScreen::enter()
{
    age_ = 0.0f;
    ring_snapped_ = false;
    scroll_x_ = static_cast<float>(scroll_index_);
}

void NuvioPocScreen::update(float dt)
{
    age_ += dt;
    const float target = static_cast<float>(scroll_index_);
    scroll_x_ += (target - scroll_x_) * std::min(1.0f, dt * 14.0f);

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
    ring_.update(dt, 22.0f);
}

Rect NuvioPocScreen::poster_rect(int absolute_index) const
{
    const float stride = theme_.poster_w + card_gap();
    const float x = content_x() + (static_cast<float>(absolute_index) - scroll_x_) * stride;
    return {x, kRowY + 42.0f, theme_.poster_w, theme_.poster_h};
}

Rect NuvioPocScreen::focus_rect() const
{
    if (detail_open_)
    {
        if (play_focused_)
        {
            const float text_x = content_x() + 48.0f + theme_.poster_w + 48.0f;
            return {text_x, 220.0f + 470.0f, 220.0f, 64.0f};
        }
        return {content_x(), 180.0f, 1920.0f - content_x() - 48.0f, 720.0f};
    }
    if (items_.empty())
        return {content_x(), kRowY + 42.0f, theme_.poster_w, theme_.poster_h};
    return poster_rect(focus_index_);
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
    const Color well = hex(0x1c1c1c);
    const Color accent = hex(theme_.accent);
    const Color muted = hex(theme_.text_muted);
    list.rounded_rect({0, 0, w, 1080}, 0, rail);

    const char *labels[] = {"Home", "Search", "Library", "Settings"};
    for (int i = 0; i < 4; ++i)
    {
        const float y = 120.0f + static_cast<float>(i) * 110.0f;
        const Rect icon{w * 0.5f - 28.0f, y, 56.0f, 56.0f};
        const bool active = i == 0;
        list.rounded_rect(icon, 16.0f, active ? accent.with_alpha(0.28f) : well);
        if (active)
            list.bordered_rect(icon, 16.0f, Color::rgb(0x000000, 0.0f), 2.0f, Color::rgb(0xffffff, 0.85f));
        ui::text(list, ctx.fonts.regular, labels[i], w * 0.5f, y + 78.0f, 14.0f,
                 active ? hex(theme_.text) : muted, Align::center);
    }
}

void NuvioPocScreen::draw_hero(DrawList &list, const Context &ctx) const
{
    const auto &fonts = ctx.fonts;
    const Color top = hex(theme_.bg_top);
    const Color bottom = hex(theme_.bg_bottom);
    const Color text = hex(theme_.text);
    const Color muted = hex(theme_.text_muted);
    const float left = content_x();

    list.gradient_rect({0, 0, 1920, 1080}, 0, top, bottom);

    const Rect hero{left, 0, 1920.0f - left, kHeroH};
    if (hero_art_ && hero_art_w_ > 0 && hero_art_h_ > 0)
    {
        const std::uint32_t tex = art_texture(ctx, hero_art_, hero_art_w_, hero_art_h_, "poc-hero");
        if (tex)
            list.image(tex, hero, ::hui::gfx::kFullUv, Color::rgb(0xffffff, 0.92f));
    }
    /* Left readable field + bottom fade into the shelf, matching modern Home. */
    list.gradient_rect(hero, 0, Color::rgb(0x000000, 0.72f), Color::rgb(0x000000, 0.08f));
    list.gradient_rect({left, kHeroH - 180.0f, 1920.0f - left, 180.0f}, 0, Color::rgb(0x000000, 0.05f),
                       Color::rgb(theme_.bg_bottom, 0.98f));

    ui::text(list, fonts.semibold, brand_, left + 8.0f, 56.0f, 22.0f, muted);

    const std::string title =
        hero_title_.empty() && !items_.empty() ? items_[static_cast<std::size_t>(focus_index_)].title
                                               : hero_title_;
    const std::string detail =
        hero_detail_.empty() && !items_.empty() ? items_[static_cast<std::size_t>(focus_index_)].subtitle
                                                : hero_detail_;
    const std::string overview =
        hero_overview_.empty() && !items_.empty() ? items_[static_cast<std::size_t>(focus_index_)].overview
                                                  : hero_overview_;

    ui::text(list, fonts.display, fonts.display.font->fit(title, 56.0f, 820.0f), left + 8.0f, 250.0f, 56.0f,
             text);
    ui::text(list, fonts.regular, fonts.regular.font->fit(detail, 22.0f, 820.0f), left + 8.0f, 318.0f, 22.0f,
             muted);
    if (!overview.empty())
        ui::paragraph(list, fonts.regular, overview, left + 8.0f, 360.0f, 20.0f, 760.0f, 30.0f, muted, 5);

    if (!status_.empty())
    {
        const Color status_color = status_is_error_ ? Color::rgb(0xff7a7a) : muted;
        ui::text(list, fonts.semibold, status_, 1920.0f - 48.0f, 56.0f, 18.0f, status_color, Align::right);
    }
}

void NuvioPocScreen::draw_row(DrawList &list, const Context &ctx) const
{
    const auto &fonts = ctx.fonts;
    const Color text = hex(theme_.text);
    const Color muted = hex(theme_.text_muted);
    const Color surface = hex(theme_.surface);
    const float left = content_x();

    ui::text(list, fonts.display, shelf_title_, left, kRowY, 28.0f, text);

    if (items_.empty())
    {
        const Rect empty{left, kRowY + 42.0f, 640.0f, theme_.poster_h};
        list.rounded_rect(empty, theme_.poster_radius, surface);
        ui::text(list, fonts.regular, status_is_error_ ? "Metadata unavailable" : "No titles yet", empty.cx(),
                 empty.cy(), 22.0f, muted, Align::center);
        return;
    }

    const float stride = theme_.poster_w + card_gap();
    for (int i = 0; i < static_cast<int>(items_.size()); ++i)
    {
        const Rect poster = poster_rect(i);
        if (poster.x > 1920.0f || poster.x + poster.w < left - stride)
            continue;

        const Item &item = items_[static_cast<std::size_t>(i)];
        list.shadow(poster, theme_.poster_radius, 16.0f, Color::rgb(0x000000, 0.45f));
        const std::uint32_t tex =
            art_texture(ctx, item.poster, item.poster_w, item.poster_h, "poc-" + std::to_string(i));
        if (tex)
            list.image(tex, poster, ::hui::gfx::kFullUv, Color::rgb(0xffffff));
        else
            list.gradient_rect(poster, theme_.poster_radius, surface, hex(theme_.bg_bottom));
    }

    if (!detail_open_)
    {
        const Rect ring = ring_.value();
        list.bordered_rect(ring.inset(-theme_.focus_ring), theme_.poster_radius + theme_.focus_ring,
                           Color::rgb(0x000000, 0.0f), 4.0f, Color::rgb(0xffffff));
    }

    const ui::Hint hints[] = {{ui::Button::cross, detail_open_ ? "Play" : "Details"},
                              {ui::Button::circle, detail_open_ ? "Back" : "Home"}};
    draw_page_hints(list, fonts, hints, 2);
}

void NuvioPocScreen::draw_detail(DrawList &list, const Context &ctx) const
{
    if (!detail_open_ || items_.empty())
        return;

    const auto &fonts = ctx.fonts;
    const Item &item = items_[static_cast<std::size_t>(focus_index_)];
    const Color surface = hex(theme_.surface, 0.96f);
    const Color text = hex(theme_.text);
    const Color muted = hex(theme_.text_muted);
    const Color accent = hex(theme_.accent);
    const float left = content_x();

    const Rect card{left, 180.0f, 1920.0f - left - 48.0f, 720.0f};
    list.rounded_rect(card, 22.0f, Color::rgb(0x000000, 0.55f));
    list.bordered_rect(card, 22.0f, surface, 2.0f, Color::rgb(0xffffff, 0.18f));

    const Rect poster{card.x + 48.0f, card.y + 56.0f, theme_.poster_w, theme_.poster_h};
    const std::uint32_t tex =
        art_texture(ctx, item.poster, item.poster_w, item.poster_h, "poc-detail");
    if (tex)
        list.image(tex, poster, ::hui::gfx::kFullUv, Color::rgb(0xffffff));
    else
        list.rounded_rect(poster, theme_.poster_radius, hex(theme_.bg_bottom));

    const float text_x = poster.x + poster.w + 48.0f;
    ui::text(list, fonts.display, fonts.display.font->fit(item.title, 42.0f, 980.0f), text_x,
             card.y + 110.0f, 42.0f, text);
    ui::text(list, fonts.semibold, item.subtitle, text_x, card.y + 160.0f, 22.0f, accent);
    ui::paragraph(list, fonts.regular, item.overview.empty() ? "No overview yet." : item.overview, text_x,
                  card.y + 220.0f, 22.0f, 980.0f, 32.0f, muted, 8);

    const Rect play{text_x, card.y + 470.0f, 220.0f, 64.0f};
    const Color play_fill = play_focused_ ? accent : surface;
    const Color play_text = play_focused_ ? hex(theme_.bg_bottom) : text;
    list.rounded_rect(play, 16.0f, play_fill);
    ui::text(list, fonts.semibold, "Play", play.cx(), play.cy() + 8.0f, 24.0f, play_text, Align::center);

    if (play_focused_)
    {
        const Rect ring = ring_.value();
        list.bordered_rect(ring.inset(-4.0f), 20.0f, Color::rgb(0x000000, 0.0f), 3.0f,
                           Color::rgb(0xffffff));
    }
}

void NuvioPocScreen::draw(DrawList &list, const Context &ctx) const
{
    draw_hero(list, ctx);
    draw_sidebar(list, ctx);
    if (!detail_open_)
        draw_row(list, ctx);
    else
    {
        draw_row(list, ctx);
        draw_detail(list, ctx);
    }
}

bool NuvioPocScreen::focus(FocusInfo *out) const
{
    if (!out)
        return false;
    out->rect = focus_rect();
    out->index = focus_index_ + 1;
    out->total = static_cast<int>(items_.size());
    if (detail_open_)
    {
        out->id = play_focused_ ? "nuvio-poc-play" : "nuvio-poc-detail";
        out->text = play_focused_ ? "Play" : (items_.empty() ? "Detail" : items_[focus_index_].title);
        return true;
    }
    if (items_.empty())
    {
        out->id = "nuvio-poc-empty";
        out->text = status_;
        return true;
    }
    out->id = "nuvio-poc-" + std::to_string(focus_index_);
    out->text = items_[static_cast<std::size_t>(focus_index_)].title;
    for (int i = 0; i < static_cast<int>(items_.size()); ++i)
        out->focusable.emplace_back("nuvio-poc-" + std::to_string(i), items_[static_cast<std::size_t>(i)].title);
    return true;
}

} // namespace evo::kit
