/* Nuvio TV 1.3.11 base.css + components-35.css. Local presentation values,
 * never a saved EVO theme change or a browser-profile preference write. */
static Palette nuvio_player_palette(Palette p)
{
    p.bg_top = p.bg_bottom = hui::gfx::Color::rgb(0x1a1a1a);
    p.surface = hui::gfx::Color::rgb(0x242424);
    p.surface_sel = hui::gfx::Color::rgb(0x303030);
    p.accent = p.accent_soft = p.accent_alt = hui::gfx::Color::rgb(0xf5f5f5);
    p.text = hui::gfx::Color::rgb(0xffffff);
    p.text_muted = hui::gfx::Color::rgb(0xb3b3b3);
    p.text_faint = hui::gfx::Color::rgb(0xb3b3b3);
    p.border = hui::gfx::Color::rgb(0x333333);
    return p;
}
