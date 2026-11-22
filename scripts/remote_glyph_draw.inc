float button_width(Button button, float size);

namespace {
bool g_remote_glyphs = false;
}

void set_remote_glyphs(bool on) { g_remote_glyphs = on; }
bool remote_glyphs() { return g_remote_glyphs; }

namespace {
void remote_key(gfx::DrawList &list, const Fonts &fonts, GlyphStyle style, const char *text,
                float x, float cy, float w, float h, gfx::Color fill, gfx::Color ink)
{
    list.bordered_rect({x, cy - h * 0.5f, w, h}, h * 0.34f, fill, 1.5f, style.edge);
    if (text && text[0]) {
        style.ink = ink;
        label(list, fonts, style, text, x + w * 0.5f, cy, h * 0.42f);
    }
}
}

bool draw_remote_button(gfx::DrawList &list, const Fonts &fonts, const GlyphStyle &style,
                        Button button, float x, float cy, float size)
{
    if (!g_remote_glyphs || button == Button::none) return false;
    const float w = button_width(button, size);
    const float h = size * 0.74f;
    const gfx::Color paper = gfx::Color::rgb(0x11131f);
    const gfx::Color light = gfx::Color::rgb(0xf4f4f8);
    const gfx::Color red = gfx::Color::rgb(0xd64545);
    const gfx::Color green = gfx::Color::rgb(0x2f9e4f);
    const gfx::Color yellow = gfx::Color::rgb(0xe2b11a);
    const gfx::Color blue = gfx::Color::rgb(0x3b6fe2);
    switch (button) {
    case Button::cross: remote_key(list, fonts, style, "OK", x, cy, w, h, paper, light); break;
    case Button::circle: remote_key(list, fonts, style, "Back", x, cy, w, h, paper, light); break;
    case Button::options:
    case Button::touchpad: remote_key(list, fonts, style, "Menu", x, cy, w, h, paper, light); break;
    case Button::triangle: remote_key(list, fonts, style, "", x, cy, w, h, yellow, gfx::Color::rgb(0x1a1a1a)); break;
    case Button::square:
    case Button::left_stick: remote_key(list, fonts, style, "i", x, cy, w, h, paper, light); break;
    case Button::r1: remote_key(list, fonts, style, "CH+", x, cy, w, h, paper, light); break;
    case Button::l1: remote_key(list, fonts, style, "CH-", x, cy, w, h, paper, light); break;
    case Button::r2: remote_key(list, fonts, style, "", x, cy, w, h, red, light); break;
    case Button::l2: remote_key(list, fonts, style, "", x, cy, w, h, green, light); break;
    case Button::right_stick: remote_key(list, fonts, style, "", x, cy, w, h, blue, light); break;
    case Button::dpad: remote_key(list, fonts, style, "<>", x, cy, w, h, paper, light); break;
    default: return false;
    }
    return true;
}
