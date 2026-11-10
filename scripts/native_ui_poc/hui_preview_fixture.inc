/* Host-preview fixture for the Nuvio native UI proof. Included by hui_preview.cpp. */
static void fill_nuvio_poc_fixture(nuvio_poc_params_t &p, std::vector<uint32_t> &hero,
                                   std::vector<std::vector<uint32_t>> &posters, int focus)
{
    p = {};
    p.theme = nuvio_poc_default_theme();
    p.brand = "Nuvio Native PoC";
    p.shelf_title = "Featured";
    p.status = "Host preview";
    p.status_is_error = 0;
    p.focus_index = focus;
    p.scroll_index = focus > 2 ? focus - 2 : 0;
    p.detail_open = 0;
    p.play_focused = 0;

    hero = fake_art(960, 540, 0x101820, 0x7b62ff, 0.25f);
    p.hero_art = hero.data();
    p.hero_art_w = 960;
    p.hero_art_h = 540;
    p.hero_title = "Night Circuit";
    p.hero_detail = "Movie · 2024";

    static const char *titles[] = {"Night Circuit", "Harbor Light", "Glass Orchard", "Static Season",
                                   "Copper Meridian", "Low Orbit Mail", "Paper Tide", "Quiet Frequency"};
    static const char *subs[] = {"Movie · 2024", "Series · S01E03", "Movie · 2023", "Series · S02E01",
                                 "Movie · 2022", "Series · S01E08", "Movie · 2021", "Movie · 2020"};
    static const uint32_t pairs[][2] = {{0x0f3d3e, 0x3fd0b0}, {0x2b1055, 0xd16ba5}, {0x3a1c0b, 0xf2a541},
                                        {0x0b1f3a, 0x5aa9e6}, {0x1e2a12, 0x9bd16b}, {0x331022, 0xff6f91},
                                        {0x102033, 0x6bb6ff}, {0x241018, 0xff8f6b}};
    posters.clear();
    p.item_count = 8;
    for (int i = 0; i < p.item_count; ++i)
    {
        posters.push_back(fake_art(176, 264, pairs[i][0], pairs[i][1], static_cast<float>(i)));
        std::snprintf(p.items[i].title, sizeof p.items[i].title, "%s", titles[i]);
        std::snprintf(p.items[i].subtitle, sizeof p.items[i].subtitle, "%s", subs[i]);
        std::snprintf(p.items[i].overview, sizeof p.items[i].overview,
                      "Host preview overview for %s.", titles[i]);
        p.items[i].poster = posters[static_cast<std::size_t>(i)].data();
        p.items[i].poster_w = 176;
        p.items[i].poster_h = 264;
    }
}

static void fill_nuvio_poc_detail_fixture(nuvio_poc_params_t &p, std::vector<uint32_t> &hero,
                                          std::vector<std::vector<uint32_t>> &posters)
{
    fill_nuvio_poc_fixture(p, hero, posters, 0);
    p.detail_open = 1;
    p.play_focused = 1;
    p.status = "Detail card";
}

static void fill_nuvio_poc_error_fixture(nuvio_poc_params_t &p, std::vector<uint32_t> &hero,
                                         std::vector<std::vector<uint32_t>> &posters)
{
    fill_nuvio_poc_fixture(p, hero, posters, 0);
    p.item_count = 0;
    posters.clear();
    p.status = "Remote metadata unavailable";
    p.status_is_error = 1;
    p.hero_title = "Nuvio shelf proof";
    p.hero_detail = p.status;
}
