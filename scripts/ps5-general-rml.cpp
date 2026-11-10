    auto general_text = [](const std::string &text) {
        std::string escaped;
        for (char c : text) {
            if (c == '&') escaped += "&amp;";
            else if (c == '<') escaped += "&lt;";
            else if (c == '>') escaped += "&gt;";
            else if (c == '\n') escaped += "<br/>";
            else if (c != '\r') escaped += c;
        }
        return escaped;
    };
    auto general_card = [&](const char *id, const char *heading, const std::string &text, const std::string &actions) {
        if (auto *card = m_playback_doc->GetElementById(id)) {
            card->SetProperty("display", text.empty() ? "none" : "block");
            card->SetInnerRML(std::string("<div class=\"nuvio-general-heading\">") + heading +
                "</div><div class=\"nuvio-general-body\">" + general_text(text) + "</div>" +
                (actions.empty() ? "" : "<div class=\"nuvio-general-actions\">" + actions + "</div>"));
        }
    };
    if (state.nuvio_parental != m_last_state.nuvio_parental) {
        if (auto *tags = m_playback_doc->GetElementById("nuvio-parental")) {
            tags->SetProperty("display", state.nuvio_parental.empty() ? "none" : "flex");
            std::string markup;
            size_t start = 0;
            while (start < state.nuvio_parental.size()) {
                const size_t end = state.nuvio_parental.find('\n', start);
                const auto label = state.nuvio_parental.substr(start, end - start);
                if (!label.empty()) markup += "<span class=\"badge-codec nuvio-parental-tag\">" + general_text(label) + "</span>";
                if (end == std::string::npos) break;
                start = end + 1;
            }
            tags->SetInnerRML(markup);
        }
    }
    if (state.nuvio_pause_text != m_last_state.nuvio_pause_text)
        general_card("nuvio-pause", "You're watching", state.nuvio_pause_text, "");
    if (state.nuvio_recommendation != m_last_state.nuvio_recommendation || state.skip_label != m_last_state.skip_label)
        general_card("nuvio-recommendation", "Watch next", state.nuvio_recommendation,
            std::string(state.skip_label.empty() ? "R1 View details   " : "") + "Triangle Next pick   L1 Keep watching");
    if (state.nuvio_still_countdown != m_last_state.nuvio_still_countdown)
        general_card("nuvio-still", "Are you still watching?", state.nuvio_still_countdown > 0 ?
            "Stopping in " + std::to_string(state.nuvio_still_countdown) + "s" : "", "X Play next episode   O Back to Nuvio");
    if (auto *clock = m_playback_doc->GetElementById("nuvio-clock")) {
        clock->SetProperty("display", state.chrome_hidden || state.nuvio_clock.empty() ? "none" : "block");
        clock->SetProperty("opacity", std::to_string(state.alpha / 255.0));
        if (state.nuvio_clock != m_last_state.nuvio_clock)
            clock->SetInnerRML(general_text(state.nuvio_clock));
    }
    if (state.nuvio_active != m_last_state.nuvio_active || state.nuvio_loading_status != m_last_state.nuvio_loading_status)
        if (auto *label = m_playback_doc->GetElementById("loading-label"))
            label->SetInnerRML(state.nuvio_active ? general_text(state.nuvio_loading_status) : "LOADING");
