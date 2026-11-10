/*
 * Core screen for the Nuvio native UI proof. GPL-3.0-or-later.
 * Focus, metadata fetch, detail card and Play handoff live here.
 * Drawing stays in ui_kit on the hui DrawList path.
 */
#ifndef NUVIO_POC_SCREEN_HPP
#define NUVIO_POC_SCREEN_HPP

#include "evo/screens/StatefulScreen.hpp"
#include "nuvio_poc_params.h"

#include <atomic>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace evo
{

class NuvioPocScreen : public StatefulScreen
{
  public:
    NuvioPocScreen();
    ~NuvioPocScreen() override;

    ScreenId getScreenId() const override { return ScreenId::NuvioPoc; }
    void onEnter() override;
    void onExit() override;
    bool handleInput(uint32_t pressed, uint32_t held, uint32_t released) override;
    void update(double deltaMs) override;
    void render(uint32_t *framebuffer, int width, int height) override;

    struct CatalogItem
    {
        std::string title;
        std::string subtitle;
        std::string overview;
        std::string play_url;
        std::vector<uint32_t> poster;
        int poster_w = 0;
        int poster_h = 0;
    };

    static std::vector<uint32_t> makePoster(uint32_t a, uint32_t b, float seed);

  private:
    void startMetadataFetch();
    void applyCatalogLocked();
    void moveFocus(int delta);
    void openDetail();
    void closeDetail();
    void playFocused();
    void fillParams(nuvio_poc_params_t *params) const;

    nuvio_poc_theme_t theme_{};
    std::vector<CatalogItem> items_;
    int focus_index_ = 0;
    int scroll_index_ = 0;
    int detail_open_ = 0;
    int play_focused_ = 0;
    std::string status_;
    int status_is_error_ = 0;
    std::vector<uint32_t> hero_art_;
    int hero_w_ = 0;
    int hero_h_ = 0;

    std::mutex catalog_mx_;
    std::vector<CatalogItem> pending_items_;
    std::string pending_status_;
    int pending_error_ = 0;
    std::atomic<int> catalog_ready_{0};
    std::atomic<int> fetch_running_{0};
    std::thread fetch_thread_;
    bool sounds_were_enabled_ = true;
};

} // namespace evo

#endif /* NUVIO_POC_SCREEN_HPP */
