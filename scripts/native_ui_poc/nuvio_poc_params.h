/*
 * Nuvio native UI proof params for the hui / sceAgc path.
 * GPL-3.0-or-later. Phase 1 only: one shelf, one detail card, one Play handoff.
 */
#ifndef NUVIO_POC_PARAMS_H
#define NUVIO_POC_PARAMS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
    NUVIO_POC_MAX_ITEMS = 24,
    NUVIO_POC_VISIBLE = 8,
    NUVIO_POC_TITLE_CHARS = 96,
    NUVIO_POC_DETAIL_CHARS = 256,
    NUVIO_POC_STATUS_CHARS = 128
};

typedef struct nuvio_poc_item {
    char title[NUVIO_POC_TITLE_CHARS];
    char subtitle[NUVIO_POC_TITLE_CHARS];
    char overview[NUVIO_POC_DETAIL_CHARS];
    char play_url[NUVIO_POC_DETAIL_CHARS];
    const uint32_t *poster; /* 0xAABBGGRR words; may be NULL */
    int poster_w;
    int poster_h;
} nuvio_poc_item_t;

typedef struct nuvio_poc_theme {
    /* Measured from the packaged browser Home CSS / live 1920x1080 layout. */
    uint32_t bg_top;      /* 0xRRGGBB */
    uint32_t bg_bottom;
    uint32_t surface;
    uint32_t accent;
    uint32_t text;
    uint32_t text_muted;
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
    const char *shelf_title;
    const char *status; /* empty, loading, error, or ready note */
    int status_is_error;
    int item_count;
    int focus_index;   /* absolute index in the catalogue */
    int scroll_index;  /* first virtualized card on the left */
    int detail_open;   /* 1 while the detail card is shown */
    int play_focused;  /* 1 when Play has focus inside the detail card */
    const uint32_t *hero_art;
    int hero_art_w;
    int hero_art_h;
    nuvio_poc_item_t items[NUVIO_POC_MAX_ITEMS];
} nuvio_poc_params_t;

static inline nuvio_poc_theme_t nuvio_poc_default_theme(void)
{
    /* Tokens from build/ui/css/bundle.css and a live 1920x1080 Home measure:
     * --bg-color #0d0d0d, --card-bg #222, --text-secondary #b3b3b3,
     * sidebar ~144px, posters ~221x339, white focus ring. */
    nuvio_poc_theme_t t;
    t.bg_top = 0x0d0d0d;
    t.bg_bottom = 0x0d0d0d;
    t.surface = 0x222222;
    t.accent = 0x7b62ff;
    t.text = 0xffffff;
    t.text_muted = 0xb3b3b3;
    t.poster_w = 221.0f;
    t.poster_h = 339.0f;
    t.poster_radius = 12.0f;
    t.focus_ring = 4.0f;
    t.sidebar_w = 144.0f;
    t.content_x = 168.0f;
    t.card_gap = 16.0f;
    return t;
}

void evo_hui_update_nuvio_poc(const nuvio_poc_params_t *params);
int evo_hui_render_nuvio_poc(int width, int height);
void evo_rmlui_update_nuvio_poc(const nuvio_poc_params_t *params);
void evo_rmlui_render_nuvio_poc(uint32_t *framebuffer, int width, int height);

#ifdef __cplusplus
}
#endif

#endif /* NUVIO_POC_PARAMS_H */
