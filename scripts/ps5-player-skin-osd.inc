/* The pinned Nuvio player places metadata above the bottom timeline and
 * leaves only its optional clock at the top. Native hints retain EVO input. */
void OsdScreen::draw_top(DrawList &list, const Context &) const
{
    list.gradient_rect({0, 0, 1920, 300}, 0, kBlack.with_alpha(0.7f), kClear);
}

void OsdScreen::draw_bottom(DrawList &list, const Context &ctx) const
{
    const ui::Fonts &fonts = ctx.fonts;
    const Palette p = nuvio_player_palette(ctx.palette);
    list.gradient_rect({0, 680, 1920, 400}, 0, kClear, kBlack.with_alpha(0.8f));
    const std::vector<std::string> title_lines = split_lines(title_.c_str());
    if (title_lines.size() >= 2)
    {
        const float y1 = meta_.empty() ? 778.0f : 744.0f;
        const float y2 = meta_.empty() ? 826.0f : 788.0f;
        ui::text(list, fonts.semibold, fit(fonts.semibold, title_lines[0], 46, 1160), kMargin, y1, 46, kWhite);
        ui::text(list, fonts.regular, fit(fonts.regular, title_lines[1], 28, 1160),
                 kMargin, y2, 28, kWhite.with_alpha(0.9f));
    }
    else
    {
        const std::string &primary = title_lines.empty() ? title_ : title_lines[0];
        ui::text(list, fonts.semibold, fit(fonts.semibold, primary, 48, 1160), kMargin, 784, 48, kWhite);
    }
    if (!meta_.empty())
        ui::text(list, fonts.regular, fit(fonts.regular, meta_, 26, 1160),
                 kMargin, 830, 26, kWhite.with_alpha(0.68f));

    float bx = kMargin;
    for (const auto &badge : badges_)
    {
        if (badge.empty()) continue;
        const float w = fonts.semibold.measure(badge, 16) + 24;
        if (bx + w > 1160) break;
        list.bordered_rect({bx, 852, w, 30}, 6, kBlack.with_alpha(0.34f), 1, kWhite.with_alpha(0.28f));
        ui::text(list, fonts.semibold, badge, bx + 12, 873, 16, kWhite);
        bx += w + 8;
    }

    const Rect track{kMargin, 920, 1920 - 2 * kMargin, 12};
    if (raw_.is_live)
    {
        const Rect pill{kMargin, 900, 96, 36};
        list.rounded_rect(pill, 18, Color::rgb(0xe5484d));
        list.circle(pill.x + 22, pill.cy(), 5, kWhite.with_alpha(0.6f + 0.4f * ui::breathe(time_, 1.6f)));
        ui::text(list, fonts.semibold, "LIVE", pill.x + 36, pill.y + 25, 18, kWhite);
    }
    else
    {
        const float f = progress_.value;
        list.rounded_rect(track, 6, kWhite.with_alpha(raw_.scrub_active ? 0.45f : 0.3f));
        if (f > 0)
            list.rounded_rect({track.x, track.y, track.w * f, track.h}, 6, p.accent);
        if (scrub_.value > 0.01f && raw_.duration_sec > 0.0)
        {
            const float t = static_cast<float>(std::clamp(raw_.scrub_target / raw_.duration_sec, 0.0, 1.0));
            const float sx = track.x + track.w * t;
            list.push_opacity(scrub_.value);
            list.rounded_rect({sx - 2, track.y - 4, 4, 20}, 2, kWhite);
            list.pop_opacity();
        }
        if (raw_.duration_sec > 0.0)
        {
            float last = -100.0f;
            for (const double cs : chapter_starts_)
            {
                if (cs <= 1.0 || cs >= raw_.duration_sec - 1.0) continue;
                const float cx = track.x + track.w * static_cast<float>(cs / raw_.duration_sec);
                if (cx - last < 6.0f) continue;
                last = cx;
                list.rounded_rect({cx - 1, track.y, 2, track.h}, 1, kBlack.with_alpha(0.65f));
            }
        }
        const std::string cur = clock_text(raw_.position_sec);
        ui::text(list, fonts.regular, cur, track.x, 970, 24, kWhite);
        const std::string &ch = (scrub_.value > 0.5f && !scrub_chapter_title_.empty()) ? scrub_chapter_title_ : chapter_title_;
        if (!ch.empty())
            ui::text(list, fonts.regular, fit(fonts.regular, ch, 20, 480),
                     track.x + fonts.regular.measure(cur, 24) + 28, 968, 20, p.text_muted);
        ui::text(list, fonts.regular, clock_text(raw_.duration_sec), track.x + track.w, 970, 24,
                 kWhite.with_alpha(0.9f), Align::right);
        if (!remaining_.empty())
        {
            const std::string mid = ends_at_.empty() ? remaining_ : remaining_ + "   -   ends at " + ends_at_;
            ui::text(list, fonts.regular, mid, 960, 968, 20, p.text_muted, Align::center);
        }
    }

    // These are shortcuts, not focusable web buttons. Do not imply a focus
    // target or introduce an action the native controller does not implement.
    char aspect[32];
    std::snprintf(aspect, sizeof aspect, "Aspect: %s",
                  raw_.view_mode == 0 ? "Fit" : (raw_.view_mode == 1 ? "Fill" : "Stretch"));
    ui::Hint hints[7];
    int n = 0;
    hints[n++] = {ui::Button::cross, raw_.paused ? "Play" : "Pause"};
    if (!raw_.is_live) hints[n++] = {ui::Button::dpad, "Seek 10s"};
    hints[n++] = {ui::Button::r2, "Audio"};
    hints[n++] = {ui::Button::square, "Info"};
    hints[n++] = {ui::Button::triangle, aspect};
    hints[n++] = {ui::Button::circle, "Back"};
    ui::HintLayout layout;
    layout.size = 30; layout.text_size = 20; layout.item_gap = 30; layout.cy = 1014;
    ui::draw_hints(list, fonts, ui::GlyphStyle::dark(), hints, n, kMargin, false, layout);
    if (!raw_.is_live && raw_.chapter_count > 0)
    {
        ui::Hint chapters[] = {{ui::Button::l1, "Prev chapter"}, {ui::Button::r1, "Next chapter"},
                              {ui::Button::right_stick, "Chapter list"}};
        layout.size = 26; layout.text_size = 18;
        ui::draw_hints(list, fonts, ui::GlyphStyle::dark(), chapters, 3, 1920 - kMargin, true, layout);
    }
    else if (!raw_.is_live)
    {
        ui::Hint extras[] = {{ui::Button::l1, "-30s"}, {ui::Button::r1, "+30s"},
                             {ui::Button::touchpad, "Sub delay"}};
        layout.size = 26; layout.text_size = 18;
        ui::draw_hints(list, fonts, ui::GlyphStyle::dark(), extras, 3, 1920 - kMargin, true, layout);
    }
    std::string tracks = "Audio: " + (audio_track_.empty() ? std::string("Default") : audio_track_) +
        "   /   Subs: " + (sub_track_.empty() ? std::string("Off") : sub_track_) + "   (Up toggle / Down select)";
    if (raw_.sub_delay_ms != 0)
    {
        char sync[40];
        std::snprintf(sync, sizeof sync, "   Sync %+d ms", raw_.sub_delay_ms);
        tracks += sync;
    }
    ui::text(list, fonts.regular, fit(fonts.regular, tracks, 18, 1920 - 2 * kMargin),
             kMargin, 1058, 18, p.text_muted);
}
