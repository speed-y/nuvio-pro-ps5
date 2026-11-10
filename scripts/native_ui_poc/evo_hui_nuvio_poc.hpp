/*
 * Nuvio native UI proof screen on ps5-homebrew-ui DrawList / sceAgc.
 * GPL-3.0-or-later. One hero, one virtualized poster row, one detail card.
 */
#ifndef EVO_HUI_NUVIO_POC_HPP
#define EVO_HUI_NUVIO_POC_HPP

#include "evo_hui_screens.hpp"
#include "nuvio_poc_params.h"

#include "core/tween.hpp"
#include "ui/motion.hpp"

#include <string>
#include <vector>

namespace evo::kit
{

class NuvioPocScreen
{
  public:
    void set(const nuvio_poc_params_t &params);
    void enter();
    void update(float dt);
    void draw(hui::gfx::DrawList &list, const Context &ctx) const;
    bool focus(FocusInfo *out) const;

  private:
    struct Item
    {
        std::string title;
        std::string subtitle;
        std::string overview;
        const std::uint32_t *poster = nullptr;
        int poster_w = 0;
        int poster_h = 0;
    };

    hui::gfx::Rect poster_rect(int absolute_index) const;
    hui::gfx::Rect focus_rect() const;
    void draw_hero(hui::gfx::DrawList &list, const Context &ctx) const;
    void draw_row(hui::gfx::DrawList &list, const Context &ctx) const;
    void draw_detail(hui::gfx::DrawList &list, const Context &ctx) const;
    std::uint32_t art_texture(const Context &ctx, const std::uint32_t *art, int w, int h,
                              const std::string &tag) const;

    nuvio_poc_theme_t theme_{};
    std::string brand_;
    std::string hero_title_;
    std::string hero_detail_;
    std::string shelf_title_;
    std::string status_;
    int status_is_error_ = 0;
    int focus_index_ = 0;
    int scroll_index_ = 0;
    int detail_open_ = 0;
    int play_focused_ = 0;
    const std::uint32_t *hero_art_ = nullptr;
    int hero_art_w_ = 0;
    int hero_art_h_ = 0;
    std::vector<Item> items_;

    float age_ = 0.0f;
    float scroll_x_ = 0.0f;
    hui::ui::SpringRect ring_;
    bool ring_snapped_ = false;
};

} // namespace evo::kit

#endif /* EVO_HUI_NUVIO_POC_HPP */
