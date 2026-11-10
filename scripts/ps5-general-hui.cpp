void OsdScreen::draw_nuvio_general(DrawList &list, const Context &ctx) const
{
    const auto &fonts = ctx.fonts;
    auto lines = [&](const std::string &text, float x, float y, float width, int maximum) {
        int count = 0;
        for (const auto &paragraph : split_lines(text.c_str())) {
            if (count >= maximum) return;
            std::string line;
            size_t start = paragraph.find_first_not_of(" \t");
            while (start != std::string::npos) {
                const size_t end = paragraph.find_first_of(" \t", start);
                const std::string word = paragraph.substr(start, end - start);
                std::string next = line.empty() ? word : line + " " + word;
                if (!line.empty() && fonts.regular.measure(next, 24) > width) {
                    ui::text(list, fonts.regular, line, x, y + count++ * 34, 24, kWhite);
                    if (count >= maximum) return;
                    line = word;
                } else line = next;
                start = end == std::string::npos ? end : paragraph.find_first_not_of(" \t", end);
            }
            ui::text(list, fonts.regular, fit(fonts.regular, line, 24, width),
                x, y + count++ * 34, 24, kWhite);
        }
    };
    auto card = [&](Rect box, const std::string &heading, const std::string &body, int max_lines) {
        list.bordered_rect(box, 16, kInk.with_alpha(0.96f), 2, ctx.palette.accent);
        ui::text(list, fonts.semibold, heading, box.x + 30, box.y + 42, 26, ctx.palette.accent);
        lines(body, box.x + 30, box.y + 86, box.w - 60, max_lines);
    };
    if (!nuvio_clock_.empty() && !raw_.chrome_hidden) {
        list.push_opacity(chrome_.value);
        ui::text(list, fonts.mono, nuvio_clock_, 1920 - kMargin, 175, 23, kWhite, Align::right);
        list.pop_opacity();
    }
    float tag_x = 1920 - kMargin, tag_y = 210;
    for (const auto &warning : split_lines(nuvio_parental_.c_str())) {
        if (warning.empty()) continue;
        const std::string label = fonts.semibold.font->fit(warning, 16, 976, 1.5f);
        const float width = fonts.semibold.measure(label, 16, 1.5f) + 24;
        if (tag_x - width < 1920 - kMargin - 1000) {
            tag_x = 1920 - kMargin;
            tag_y += 42;
        }
        const Rect tag{tag_x - width, tag_y, width, 32};
        list.bordered_rect(tag, 8, kBlack.with_alpha(0.35f), 1.5f, kWhite.with_alpha(0.45f));
        ui::text(list, fonts.semibold, label, tag.cx(), tag.y + 22, 16, kWhite, Align::center, 1.5f);
        tag_x -= width + 10;
    }
    if (!nuvio_pause_text_.empty()) {
        card({kMargin, 280, 1100, 360}, "You're watching", nuvio_pause_text_, 8);
    }
    if (!nuvio_recommendation_.empty()) {
        const Rect box{1920 - kMargin - 740, 470, 740, 230};
        card(box, "Watch next", nuvio_recommendation_, 3);
        ui::Hint hints[3];
        int n = 0;
        if (!skip_on_) hints[n++] = {ui::Button::r1, "View details"};
        hints[n++] = {ui::Button::triangle, "Next pick"};
        hints[n++] = {ui::Button::l1, "Keep watching"};
        ui::HintLayout layout;
        layout.size = 28; layout.text_size = 18; layout.item_gap = 18;
        layout.cy = box.y + box.h - 30;
        ui::draw_hints(list, fonts, ui::GlyphStyle::dark(), hints, n, box.x + 30, false, layout);
    }
    if (raw_.nuvio_still_countdown > 0) {
        const Rect box{560, 350, 800, 280};
        card(box, "Are you still watching?", "Stopping in " +
            std::to_string(raw_.nuvio_still_countdown) + "s", 2);
        ui::Hint hints[] = {{ui::Button::cross, "Play next episode"}, {ui::Button::circle, "Back to Nuvio"}};
        ui::HintLayout layout;
        layout.size = 32; layout.text_size = 24; layout.item_gap = 36; layout.cy = box.y + 215;
        ui::draw_hints(list, fonts, ui::GlyphStyle::dark(), hints, 2, box.x + 30, false, layout);
    }
}
