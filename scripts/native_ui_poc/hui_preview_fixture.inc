/* Host-preview fixture for the Nuvio native UI proof. Included by host_preview.cpp. */
static void fill_nuvio_poc_fixture(nuvio_poc_params_t &p, std::vector<uint32_t> &hero, int hero_w,
                                   int hero_h, std::vector<std::vector<uint32_t>> &posters,
                                   int poster_w, int poster_h, int focus)
{
    p = {};
    p.theme = nuvio_poc_default_theme();
    p.brand = "Nuvio";
    p.shelf_title = "Popular - Movie";
    p.status = "Native proof";
    p.status_is_error = 0;
    p.focus_index = focus;
    p.scroll_index = focus > 2 ? focus - 2 : 0;
    p.detail_open = 0;
    p.play_focused = 0;

    if (hero.empty())
    {
        hero = fake_art(1280, 720, 0x101820, 0x7b62ff, 0.25f);
        hero_w = 1280;
        hero_h = 720;
    }
    p.hero_art = hero.data();
    p.hero_art_w = hero_w;
    p.hero_art_h = hero_h;

    static const char *titles[] = {"Resident Evil", "Hocus Pocus", "Halloween", "Primetime",
                                   "Obsession", "A Dog's Perfect Christmas", "Verity",
                                   "The Nightmare Before Christmas"};
    static const char *subs[] = {"Movie · Action · 1h 34m", "Movie · 1993", "Movie · 1978",
                                 "Movie · 2026", "Movie · Horror", "Movie · 2026", "Movie · 2026",
                                 "Movie · 1993"};
    static const char *overviews[] = {
        "Follows a hapless courier tasked with delivering a package to a remote hospital. He soon "
        "finds himself caught in the middle of an outbreak.",
        "A teenage boy and his younger sister face three witches raised from the dead on Halloween.",
        "Fifteen years after murdering his sister, Michael Myers escapes from a mental hospital.",
        "A tense thriller set behind the cameras of a live broadcast.",
        "A chilling tale of desire that turns deadly.",
        "A holiday story about family and a loyal dog.",
        "A ghostwriter discovers a manuscript that may not be fiction.",
        "Jack Skellington discovers Christmas Town and tries to take over the holiday."};
    static const uint32_t pairs[][2] = {{0x1a1040, 0x7b62ff}, {0x2b1055, 0xd16ba5}, {0x3a1c0b, 0xf2a541},
                                        {0x0b1f3a, 0x5aa9e6}, {0x1e2a12, 0x9bd16b}, {0x331022, 0xff6f91},
                                        {0x102033, 0x6bb6ff}, {0x241018, 0xff8f6b}};

    const int safe = std::max(0, std::min(focus, 7));
    p.hero_title = titles[safe];
    p.hero_detail = subs[safe];
    p.hero_overview = overviews[safe];

    if (posters.empty())
    {
        for (int i = 0; i < 8; ++i)
            posters.push_back(fake_art(poster_w, poster_h, pairs[i][0], pairs[i][1],
                                       static_cast<float>(i)));
    }

    p.item_count = static_cast<int>(std::min<std::size_t>(8, posters.size()));
    for (int i = 0; i < p.item_count; ++i)
    {
        std::snprintf(p.items[i].title, sizeof p.items[i].title, "%s", titles[i]);
        std::snprintf(p.items[i].subtitle, sizeof p.items[i].subtitle, "%s", subs[i]);
        std::snprintf(p.items[i].overview, sizeof p.items[i].overview, "%s", overviews[i]);
        p.items[i].poster = posters[static_cast<std::size_t>(i)].data();
        p.items[i].poster_w = poster_w;
        p.items[i].poster_h = poster_h;
    }
}

static void fill_nuvio_poc_detail_fixture(nuvio_poc_params_t &p, std::vector<uint32_t> &hero, int hero_w,
                                          int hero_h, std::vector<std::vector<uint32_t>> &posters,
                                          int poster_w, int poster_h)
{
    fill_nuvio_poc_fixture(p, hero, hero_w, hero_h, posters, poster_w, poster_h, 0);
    p.detail_open = 1;
    p.play_focused = 1;
    p.status = "Detail card";
}

static void fill_nuvio_poc_error_fixture(nuvio_poc_params_t &p, std::vector<uint32_t> &hero, int hero_w,
                                         int hero_h, std::vector<std::vector<uint32_t>> &posters,
                                         int poster_w, int poster_h)
{
    fill_nuvio_poc_fixture(p, hero, hero_w, hero_h, posters, poster_w, poster_h, 0);
    p.item_count = 0;
    posters.clear();
    p.status = "Remote metadata unavailable";
    p.status_is_error = 1;
    p.hero_title = "Nuvio";
    p.hero_detail = p.status;
    p.hero_overview = "";
}
