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

typedef struct {
    char title[NUVIO_POC_TITLE_CHARS];
    char subtitle[NUVIO_POC_TITLE_CHARS];
    char overview[NUVIO_POC_DETAIL_CHARS];
    char play_url[NUVIO_POC_DETAIL_CHARS];
    const uint32_t *poster; /* 0xAABBGGRR words; may be NULL */
    int poster_w;
    int poster_h;
} nuvio_poc_item_t;

typedef struct {
    /* Theme tokens for the proof. Later phases measure Nuvio CSS. */
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
} nuvio_poc_theme_t;

typedef struct {
    nuvio_poc_theme_t theme;
    const char *brand;
    const char *hero_title;
    const char *hero_detail;
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
    /* Dark Nuvio-like proof palette. Not the EVO MIDNIGHT blue rail look. */
    nuvio_poc_theme_t t;
    t.bg_top = 0x0b0d10;
    t.bg_bottom = 0x050607;
    t.surface = 0x161a20;
    t.accent = 0x3dd6c6;
    t.text = 0xf2f4f7;
    t.text_muted = 0x9aa3af;
    t.poster_w = 176.0f;
    t.poster_h = 264.0f;
    t.poster_radius = 18.0f;
    t.focus_ring = 5.0f;
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
