void PlayerScreen::updateNuvioPresentation(uint64_t now)
{
    auto playback = Application::getInstance().getPlaybackController();
    const auto *policy = evo_webui_presentation();
    const bool ready = playback && playback->isActive() && !playback->isMusicMode() &&
        !playback->isLiveSource() && video_frame_loaded && !g_pp_pb.seek_discarding &&
        !pb_prebuffer_hold && !readerStalled() && !playback->isScrubbing();
    const bool paused = playback && (playback->isPaused() || evo_pb_is_paused());
    if (!playback) { m_nuvioView = {}; m_nuvioClock[0] = 0; m_nuvioRecommendation.clear(); return; }
    // Numeric snapshots only, at 2/10/30 seconds without a first frame.
    // Do not turn a long preparation or an intentional pause into a retry.
    if (policy->active && playback->isActive() && !playback->isMusicMode() &&
        !video_frame_loaded && !m_playbackEnded) {
        if (!m_nuvioWaitSince) m_nuvioWaitSince = now;
        static const uint64_t delays[] = {2000, 10000, 30000};
        if (m_nuvioWaitReports < 3 && now - m_nuvioWaitSince >= delays[m_nuvioWaitReports]) {
            ++m_nuvioWaitReports;
            evo_boot_log("playback first-frame wait: ms=%llu screen=%d paused=%d engine_paused=%d "
                "ready=%d hold=%d prebuffer=%d scrub=%d video_run=%d exited=%d parked=%d "
                "demux_run=%d audio_run=%d vq=%d aq=%d fatal=%d",
                static_cast<unsigned long long>(now - m_nuvioWaitSince), screen,
                playback->isPaused(), evo_pb_is_paused(), video_decode_ready,
                static_cast<int>(video_decode_hold), static_cast<int>(pb_prebuffer_hold),
                static_cast<int>(pb_scrub_hold), static_cast<int>(video_thread_running),
                static_cast<int>(video_thread_exited), static_cast<int>(video_decode_parked),
                static_cast<int>(demux_thread_running), static_cast<int>(audio_decode_thread_running),
                packet_queue_count(&video_packet_queue), packet_queue_count(&audio_packet_queue),
                evo_pb_decode_fatal());
        }
    } else {
        m_nuvioWaitSince = 0;
        m_nuvioWaitReports = 0;
    }
    m_nuvioView = evo_webui_presentation_update(playback->getPositionSeconds(),
        playback->getDurationSeconds(), now, ready || m_playbackEnded, paused,
        m_showStatsForNerds || m_nextEpisodeState != 0, m_playbackEnded);
    evo_webui_presentation_clock(playback->getPositionSeconds(), playback->getDurationSeconds(),
        m_nuvioClock, sizeof m_nuvioClock);
    m_nuvioRecommendation.clear();
    if (m_nuvioView.recommendation) {
        const auto &item = policy->recommendations[m_nuvioView.recommendation - 1];
        m_nuvioRecommendation = std::string(item.title) + "\n" + item.description;
    }
    if (m_osdVisibilityAlpha <= 0 ||
        (m_nuvioEndSuggestionSince && now - m_nuvioEndSuggestionSince >= 10000))
        m_nuvioView.recommendation = 0;
}

void PlayerScreen::fillNuvioPresentation(evo_playback_osd_params_t &p)
{
    const auto *policy = evo_webui_presentation();
    p.nuvio_active = policy->active;
    p.nuvio_pause_text = m_nuvioView.pause ? (policy->description[0] ? policy->description : "Paused") : "";
    p.nuvio_parental = m_nuvioView.parental ? policy->parental : "";
    p.nuvio_recommendation = m_nuvioRecommendation.c_str();
    // Start the cap when a suggestion becomes visible, not at the last input.
    // Keep the raw recommendation above so expiry cannot restart this timer.
    const uint64_t now = NowMs();
    const bool suggestion = p.next_episode || p.playback_ended || m_nuvioRecommendation.size();
    if (!policy->active || p.chrome_hidden || !suggestion) m_nuvioEndSuggestionSince = 0;
    else if (!m_nuvioEndSuggestionSince) m_nuvioEndSuggestionSince = now;
    if (policy->active && (p.chrome_hidden ||
        (m_nuvioEndSuggestionSince && now - m_nuvioEndSuggestionSince >= 10000))) {
        p.next_episode = 0;
        p.playback_ended = 0;
        p.nuvio_recommendation = "";
    }
    p.nuvio_clock = m_nuvioClock;
    // Nuvio's clock policy owns the end time in the upper-right corner.
    // Keep remaining duration below the timeline, without a second end time.
    if (policy->active) p.ends_at = "";
    p.nuvio_still_countdown = m_nextEpisodeState >= 1000 ? m_nextEpisodeState - 1000 : 0;
    if (p.nuvio_still_countdown) { p.next_episode = 0; p.skip_label = ""; }
    const bool loading = !evo_pb_is_finished() &&
        (!video_frame_loaded || g_pp_pb.seek_discarding || pb_prebuffer_hold || readerStalled());
    if (policy->active) p.loading = policy->loading && loading;
    p.nuvio_loading_status = !policy->loading_detail ? "" : g_pp_pb.seek_discarding ? "Seeking" :
        !video_frame_loaded ? "Preparing video" : "Buffering";
}
