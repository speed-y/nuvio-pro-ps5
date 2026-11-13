/*
 * Nuvio native UI proof params for the hui / sceAgc path.
 * GPL-3.0-or-later. Multi-shelf, themes, metadata pills, and Play handoff.
 */
#ifndef NUVIO_POC_PARAMS_H
#define NUVIO_POC_PARAMS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
    NUVIO_POC_MAX_ITEMS = 24,
    NUVIO_POC_MAX_SHELVES = 4,
    NUVIO_POC_MAX_ITEMS_PER_SHELF = 16,
    NUVIO_POC_VISIBLE = 8,
    NUVIO_POC_TITLE_CHARS = 96,
    NUVIO_POC_DETAIL_CHARS = 256,
    NUVIO_POC_STATUS_CHARS = 128
};

typedef enum nuvio_theme_preset {
    NUVIO_THEME_ARCTIC_BLUE = 0,
    NUVIO_THEME_DEFAULT_DARK = 1,
    NUVIO_THEME_GRAPHITE = 2,
    NUVIO_THEME_GOLD = 3,
    NUVIO_THEME_JADE = 4,
    NUVIO_THEME_ROSE_GOLD = 5,
    NUVIO_THEME_VIOLET = 6,
    NUVIO_THEME_OCEAN = 7,
    NUVIO_THEME_CRIMSON = 8,
    NUVIO_THEME_EMERALD = 9,
    NUVIO_THEME_AMBER = 10,
    NUVIO_THEME_ROSE = 11,
    NUVIO_THEME_COUNT = 12
} nuvio_theme_preset_t;

typedef struct nuvio_poc_item {
    char title[NUVIO_POC_TITLE_CHARS];
    char subtitle[NUVIO_POC_TITLE_CHARS];
    char overview[NUVIO_POC_DETAIL_CHARS];
    char play_url[NUVIO_POC_DETAIL_CHARS];
    char quality_badge[16];   /* e.g. "4K HDR", "1080p" */
    char rating[16];          /* e.g. "7.8" */
    char year[8];             /* e.g. "1978" */
    char duration[16];        /* e.g. "1h 31m" */
    char genres[64];          /* e.g. "Horror, Mystery" */
    float progress;           /* 0.0 to 1.0; > 0 shows progress bar (Continue Watching) */
    const uint32_t *poster;   /* 0xAABBGGRR words; may be NULL */
    int poster_w;
    int poster_h;
} nuvio_poc_item_t;

typedef struct nuvio_poc_shelf {
    char title[NUVIO_POC_TITLE_CHARS];
    int item_count;
    int focus_index;
    int scroll_index;
    nuvio_poc_item_t items[NUVIO_POC_MAX_ITEMS_PER_SHELF];
} nuvio_poc_shelf_t;

typedef struct nuvio_poc_theme {
    /* Measured from the packaged browser Home CSS / live 1920x1080 layout:
     * uC theme map: ARCTIC_BLUE, GOLD, JADE, ROSE_GOLD, GRAPHITE, WHITE, etc. */
    const char *name;
    uint32_t bg_top;      /* 0xRRGGBB */
    uint32_t bg_bottom;
    uint32_t surface;
    uint32_t accent;
    uint32_t accent_variant;
    uint32_t focus_color;
    uint32_t focus_bg;
    uint32_t text;
    uint32_t text_muted;
    uint32_t border_color;
    float poster_w;
    float poster_h;
    float poster_radius;
    float focus_ring;
    float sidebar_w;
    float content_x;
    float card_gap;
} nuvio_poc_theme_t;

typedef struct nuvio_poc_params {
    nuvio_poc_theme_t theme;
    const char *brand;
    const char *hero_title;
    const char *hero_detail;
    const char *hero_overview;
    const char *hero_quality;
    const char *hero_rating;
    const char *hero_year;
    const char *hero_duration;
    const char *hero_genres;
    const char *shelf_title;
    const char *status; /* empty, loading, error, or ready note */
    int status_is_error;
    
    /* Legacy single-shelf compatibility */
    int item_count;
    int focus_index;   /* absolute index in the catalogue */
    int scroll_index;  /* first virtualized card on the left */
    
    /* Multi-shelf support */
    int shelf_count;
    int focused_shelf;
    int focused_area;      /* 0 = shelves, 1 = hero action buttons */
    int hero_button_focus; /* 0 = Play, 1 = Add to Library / Details */
    
    int detail_open;   /* 1 while the detail card is shown */
    int play_focused;  /* 1 when Play has focus inside the detail card */
    const uint32_t *hero_art;
    int hero_art_w;
    int hero_art_h;
    
    nuvio_poc_item_t items[NUVIO_POC_MAX_ITEMS];
    nuvio_poc_shelf_t shelves[NUVIO_POC_MAX_SHELVES];
} nuvio_poc_params_t;

static inline nuvio_poc_theme_t nuvio_poc_get_theme_preset(nuvio_theme_preset_t preset)
{
    nuvio_poc_theme_t t;
    t.poster_w = 221.0f;
    t.poster_h = 332.0f;
    t.poster_radius = 16.0f;
    t.focus_ring = 3.5f;
    t.sidebar_w = 144.0f;
    t.content_x = 168.0f;
    t.card_gap = 16.0f;
    t.text = 0xffffff;
    t.text_muted = 0xb3b3b3;
    t.border_color = 0x333333;

    switch (preset) {
    case NUVIO_THEME_ARCTIC_BLUE:
        t.name = "Arctic Blue";
        t.bg_top = 0x0b0e14;
        t.bg_bottom = 0x0b0e14;
        t.surface = 0x161e2a;
        t.accent = 0x3185f5;
        t.accent_variant = 0x4d55e8;
        t.focus_color = 0x4de3ff;
        t.focus_bg = 0x172844;
        break;
    case NUVIO_THEME_GOLD:
        t.name = "Gold";
        t.bg_top = 0x0f0e0b;
        t.bg_bottom = 0x0f0e0b;
        t.surface = 0x262116;
        t.accent = 0xe8a91c;
        t.accent_variant = 0x9a6200;
        t.focus_color = 0xffd45c;
        t.focus_bg = 0x3d2d1a;
        break;
    case NUVIO_THEME_JADE:
        t.name = "Jade";
        t.bg_top = 0x0b0f0d;
        t.bg_bottom = 0x0b0f0d;
        t.surface = 0x16251d;
        t.accent = 0x22d37c;
        t.accent_variant = 0x0bbf9a;
        t.focus_color = 0x7bf08d;
        t.focus_bg = 0x153a2c;
        break;
    case NUVIO_THEME_ROSE_GOLD:
        t.name = "Rose Gold";
        t.bg_top = 0x100c0f;
        t.bg_bottom = 0x100c0f;
        t.surface = 0x281a24;
        t.accent = 0xec70a9;
        t.accent_variant = 0xb75aff;
        t.focus_color = 0xffb37a;
        t.focus_bg = 0x442037;
        break;
    case NUVIO_THEME_GRAPHITE:
        t.name = "Graphite";
        t.bg_top = 0x0c0d0f;
        t.bg_bottom = 0x0c0d0f;
        t.surface = 0x20242a;
        t.accent = 0xaab2be;
        t.accent_variant = 0x687381;
        t.focus_color = 0xf3f5f7;
        t.focus_bg = 0x30343a;
        break;
    case NUVIO_THEME_VIOLET:
        t.name = "Violet";
        t.bg_top = 0x0d0d0f;
        t.bg_bottom = 0x0d0d0f;
        t.surface = 0x1f1a24;
        t.accent = 0x8e24aa;
        t.accent_variant = 0x6a1b9a;
        t.focus_color = 0xab47bc;
        t.focus_bg = 0x2d1a3d;
        break;
    case NUVIO_THEME_OCEAN:
        t.name = "Ocean";
        t.bg_top = 0x0d0d0f;
        t.bg_bottom = 0x0d0d0f;
        t.surface = 0x1a1f24;
        t.accent = 0x1e88e5;
        t.accent_variant = 0x1565c0;
        t.focus_color = 0x42a5f5;
        t.focus_bg = 0x1a2d3d;
        break;
    case NUVIO_THEME_CRIMSON:
        t.name = "Crimson";
        t.bg_top = 0x0d0d0d;
        t.bg_bottom = 0x0d0d0d;
        t.surface = 0x241a1a;
        t.accent = 0xe53935;
        t.accent_variant = 0xc62828;
        t.focus_color = 0xff5252;
        t.focus_bg = 0x3d1a1a;
        break;
    case NUVIO_THEME_EMERALD:
        t.name = "Emerald";
        t.bg_top = 0x0d0d0d;
        t.bg_bottom = 0x0d0d0d;
        t.surface = 0x1a241a;
        t.accent = 0x43a047;
        t.accent_variant = 0x2e7d32;
        t.focus_color = 0x66bb6a;
        t.focus_bg = 0x1a3d1e;
        break;
    case NUVIO_THEME_AMBER:
        t.name = "Amber";
        t.bg_top = 0x0f0d0d;
        t.bg_bottom = 0x0f0d0d;
        t.surface = 0x24201a;
        t.accent = 0xfb8c00;
        t.accent_variant = 0xef6c00;
        t.focus_color = 0xffa726;
        t.focus_bg = 0x3d2d1a;
        break;
    case NUVIO_THEME_ROSE:
        t.name = "Rose";
        t.bg_top = 0x0d0d0d;
        t.bg_bottom = 0x0d0d0d;
        t.surface = 0x241a1f;
        t.accent = 0xd81b60;
        t.accent_variant = 0xc2185b;
        t.focus_color = 0xec407a;
        t.focus_bg = 0x3d1a2d;
        break;
    case NUVIO_THEME_DEFAULT_DARK:
    default:
        t.name = "Nuvio Dark";
        t.bg_top = 0x0d0d0d;
        t.bg_bottom = 0x0d0d0d;
        t.surface = 0x222222;
        t.accent = 0x7b62ff;
        t.accent_variant = 0x5a63f7;
        t.focus_color = 0xffffff;
        t.focus_bg = 0x303030;
        break;
    }
    return t;
}

static inline nuvio_poc_theme_t nuvio_poc_default_theme(void)
{
    /* Default is Nuvio Dark (0x0d0d0d, 0x7b62ff, white focus ring). */
    return nuvio_poc_get_theme_preset(NUVIO_THEME_DEFAULT_DARK);
}

void evo_hui_update_nuvio_poc(const nuvio_poc_params_t *params);
int evo_hui_render_nuvio_poc(int width, int height);
void evo_rmlui_update_nuvio_poc(const nuvio_poc_params_t *params);
void evo_rmlui_render_nuvio_poc(uint32_t *framebuffer, int width, int height);

#ifdef __cplusplus
}
#endif

#endif /* NUVIO_POC_PARAMS_H */
