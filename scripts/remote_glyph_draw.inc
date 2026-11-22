float button_width(Button button, float size);

namespace {
bool g_remote_glyphs = false;
bool g_remote_menu_seen = false;
}

void set_remote_glyphs(bool on) { g_remote_glyphs = on; }
bool remote_glyphs() { return g_remote_glyphs; }
void set_remote_menu_seen(bool on) { g_remote_menu_seen = on; }
bool remote_menu_seen() { return g_remote_menu_seen; }

namespace {
float remote_x(float unit, float x, float w) { return x + unit / 64.0f * w; }
float remote_y(float unit, float cy, float h) { return cy - h * 0.5f + unit / 64.0f * h; }

void remote_body(gfx::DrawList &list, float x, float cy, float w, float h, gfx::Color fill)
{
    list.bordered_rect({x, cy - h * 0.5f, w, h}, h * 0.25f, fill, h * 0.0625f, gfx::Color::rgb(0xf2f2f8));
}

void remote_back_arrow(gfx::DrawList &list, float x, float cy, float w, float h, gfx::Color ink)
{
    const float xy[] = {
        remote_x(12, x, w), remote_y(28, cy, h),
        remote_x(28, x, w), remote_y(16, cy, h),
        remote_x(28, x, w), remote_y(23, cy, h),
        remote_x(50, x, w), remote_y(23, cy, h),
        remote_x(50, x, w), remote_y(46, cy, h),
        remote_x(38, x, w), remote_y(46, cy, h),
        remote_x(38, x, w), remote_y(33, cy, h),
        remote_x(28, x, w), remote_y(33, cy, h),
        remote_x(28, x, w), remote_y(40, cy, h),
    };
    list.polygon(xy, 9, ink);
}

void remote_hold_ok(gfx::DrawList &list, const Fonts &fonts, GlyphStyle style, float x, float cy,
                    float w, float h)
{
    const gfx::Color light = gfx::Color::rgb(0xf4f4f8);
    remote_body(list, x, cy, w, h, gfx::Color::rgb(0x141624));
    list.arc(x + w * 0.5f, cy, h * 0.30f, h * 0.07f, -2.2f, 5.0f, light, true);
    style.ink = light;
    label(list, fonts, style, "OK", x + w * 0.5f, cy, h * 0.28f);
}
}

bool draw_remote_button(gfx::DrawList &list, const Fonts &fonts, const GlyphStyle &style,
                        Button button, float x, float cy, float size)
{
    if (!g_remote_glyphs || button == Button::none) return false;
    const float w = button_width(button, size);
    const float h = size;
    const gfx::Color paper = gfx::Color::rgb(0x141624);
    const gfx::Color light = gfx::Color::rgb(0xf4f4f8);
    const gfx::Color red = gfx::Color::rgb(0xd64545);
    const gfx::Color green = gfx::Color::rgb(0x2f9e4f);
    const gfx::Color yellow = gfx::Color::rgb(0xe2b11a);
    const gfx::Color blue = gfx::Color::rgb(0x3b6fe2);
    auto word = [&](const char *text, gfx::Color fill) {
        remote_body(list, x, cy, w, h, fill);
        GlyphStyle inked = style;
        inked.ink = light;
        label(list, fonts, inked, text, x + w * 0.5f, cy, h * 0.34f);
    };
    switch (button) {
    case Button::cross:
        word("OK", paper);
        break;
    case Button::l1:
        word("CH-", paper);
        break;
    case Button::r1:
        word("CH+", paper);
        break;
    case Button::circle:
        remote_body(list, x, cy, w, h, paper);
        remote_back_arrow(list, x, cy, w, h, light);
        break;
    case Button::options:
    case Button::touchpad:
        if (!remote_menu_seen()) {
            remote_hold_ok(list, fonts, style, x, cy, w, h);
            break;
        }
        remote_body(list, x, cy, w, h, paper);
        list.rounded_rect({remote_x(16, x, w), remote_y(17, cy, h), w * 0.5f, h * 0.094f}, h * 0.04f, light);
        list.rounded_rect({remote_x(16, x, w), remote_y(29, cy, h), w * 0.5f, h * 0.094f}, h * 0.04f, light);
        list.rounded_rect({remote_x(16, x, w), remote_y(41, cy, h), w * 0.5f, h * 0.094f}, h * 0.04f, light);
        break;
    case Button::dpad:
        remote_body(list, x, cy, w, h, paper);
        list.rounded_rect({remote_x(27, x, w), remote_y(12, cy, h), w * 0.156f, h * 0.625f}, h * 0.04f, light);
        list.rounded_rect({remote_x(12, x, w), remote_y(27, cy, h), w * 0.625f, h * 0.156f}, h * 0.04f, light);
        break;
    case Button::square:
    case Button::left_stick: {
        remote_body(list, x, cy, w, h, paper);
        const float cx = remote_x(32, x, w);
        const float iy = remote_y(32, cy, h);
        list.ring(cx, iy, h * 0.25f, h * 0.0625f, light);
        list.circle(cx, remote_y(23.8f, cy, h), h * 0.044f, light);
        list.rounded_rect({remote_x(29.4f, x, w), remote_y(29, cy, h), w * 0.081f, h * 0.22f}, h * 0.03f, light);
        break;
    }
    case Button::r2:
        remote_body(list, x, cy, w, h, red);
        break;
    case Button::l2:
        remote_body(list, x, cy, w, h, green);
        break;
    case Button::triangle:
        remote_body(list, x, cy, w, h, yellow);
        break;
    case Button::right_stick:
        remote_body(list, x, cy, w, h, blue);
        break;
    default:
        return false;
    }
    return true;
}
