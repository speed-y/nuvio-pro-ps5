"""Draw the remote glyph PNGs and the comparison sheet in docs/."""
from pathlib import Path
import tarfile
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'remote-glyphs'
FONT = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')

PAPER = (20, 22, 36, 255)
LIGHT = (244, 244, 248, 255)
RED = (214, 69, 69, 255)
GREEN = (47, 158, 79, 255)
YELLOW = (226, 177, 26, 255)
BLUE = (59, 111, 226, 255)
EDGE = (242, 242, 248, 255)
SCALE = 2  # 64-unit design drawn at 128 px so the TV icons stay sharp.


def font(size):
    return ImageFont.truetype(str(FONT), size) if FONT.is_file() else ImageFont.load_default()


def u(value):
    return value * SCALE


def canvas():
    image = Image.new('RGBA', (64 * SCALE, 64 * SCALE), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def key(fill):
    image, draw = canvas()
    draw.rounded_rectangle((u(3), u(3), u(61), u(61)), radius=u(16), fill=fill, outline=EDGE, width=int(u(4)))
    return image, draw


def label(draw, text, size, ink):
    face = font(int(u(size)))
    box = draw.textbbox((0, 0), text, font=face)
    x = (64 * SCALE - (box[2] - box[0])) / 2 - box[0]
    y = (64 * SCALE - (box[3] - box[1])) / 2 - box[1]
    draw.text((x, y), text, font=face, fill=ink)


def play():
    image, draw = key(PAPER)
    draw.polygon([(u(23), u(16)), (u(23), u(48)), (u(47), u(32))], fill=LIGHT)
    return image


def pause():
    image, draw = key(PAPER)
    draw.rounded_rectangle((u(20), u(16), u(28), u(48)), radius=u(2), fill=LIGHT)
    draw.rounded_rectangle((u(36), u(16), u(44), u(48)), radius=u(2), fill=LIGHT)
    return image


def arrows():
    image, draw = key(PAPER)
    draw.rounded_rectangle((u(27), u(12), u(37), u(52)), radius=u(3), fill=LIGHT)
    draw.rounded_rectangle((u(12), u(27), u(52), u(37)), radius=u(3), fill=LIGHT)
    return image


def back():
    """Left-pointing return arrow: head, top shaft, right drop, short foot."""
    image, draw = key(PAPER)
    draw.polygon([
        (u(12), u(28)),
        (u(28), u(16)),
        (u(28), u(23)),
        (u(50), u(23)),
        (u(50), u(46)),
        (u(38), u(46)),
        (u(38), u(33)),
        (u(28), u(33)),
        (u(28), u(40)),
    ], fill=LIGHT)
    return image


def info():
    image, draw = key(PAPER)
    draw.ellipse((u(16), u(16), u(48), u(48)), outline=LIGHT, width=int(u(4)))
    draw.ellipse((u(29.2), u(21), u(34.8), u(26.6)), fill=LIGHT)
    draw.rounded_rectangle((u(29.4), u(29), u(34.6), u(43)), radius=u(2), fill=LIGHT)
    return image


def hold_ok():
    image, draw = key(PAPER)
    draw.arc((u(15), u(15), u(49), u(49)), start=210, end=520, fill=LIGHT, width=int(u(4)))
    label(draw, 'OK', 16, LIGHT)
    return image


def menu():
    image, draw = key(PAPER)
    for top in (17, 29, 41):
        draw.rounded_rectangle((u(16), u(top), u(48), u(top + 6)), radius=u(3), fill=LIGHT)
    return image


def word(text, size=22):
    image, draw = key(PAPER)
    label(draw, text, size, LIGHT)
    return image


def colour(fill):
    image, draw = key(fill)
    return image


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    made = {
        'btn_remote_ok.png': word('OK', 20),
        'btn_remote_hold_ok.png': hold_ok(),
        'btn_remote_back.png': back(),
        'btn_remote_menu.png': menu(),
        'btn_remote_arrows.png': arrows(),
        'btn_remote_red.png': colour(RED),
        'btn_remote_green.png': colour(GREEN),
        'btn_remote_yellow.png': colour(YELLOW),
        'btn_remote_blue.png': colour(BLUE),
        'btn_remote_info.png': info(),
        'btn_remote_play.png': play(),
        'btn_remote_pause.png': pause(),
        'btn_remote_ch_up.png': word('CH+', 16),
        'btn_remote_ch_down.png': word('CH-', 16),
    }
    for digit in range(10):
        made['btn_remote_%d.png' % digit] = word(str(digit), 26)
    for name, image in made.items():
        image.save(OUT / name)

    archive = next((ROOT / '.cache').glob('evo-player-nuvio-source-*.tar.gz'), None)
    controllers = []
    if archive and archive.is_file():
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                if '/assets/icons/btn_' in member.name and member.name.endswith('.png'):
                    raw = tar.extractfile(member).read()
                    path = Path('/tmp') / Path(member.name).name
                    path.write_bytes(raw)
                    controllers.append((path.stem.replace('btn_', ''), Image.open(path).convert('RGBA')))
    controllers.sort()

    order = ['ok', 'hold_ok', 'back', 'menu', 'arrows', 'red', 'green', 'yellow', 'blue', 'info', 'play', 'pause',
             'ch_up', 'ch_down'] + [str(n) for n in range(10)]
    names = {
        'ok': 'OK', 'hold_ok': 'Hold OK', 'back': 'Back', 'menu': 'Menu', 'arrows': 'Arrows',
        'red': 'Red', 'green': 'Green',
        'yellow': 'Yellow', 'blue': 'Blue', 'info': 'Info', 'play': 'Play', 'pause': 'Pause',
        'ch_up': 'CH+', 'ch_down': 'CH-',
    }
    labels = [(names.get(key, key), made['btn_remote_%s.png' % key]) for key in order]

    cell = 132
    columns = 8
    rows = (len(labels) + columns - 1) // columns
    controller_rows = (len(controllers) + columns - 1) // columns
    width = 40 + columns * cell
    height = 88 + rows * cell + 64 + controller_rows * cell
    sheet = Image.new('RGB', (width, height), (12, 14, 24))
    draw = ImageDraw.Draw(sheet)
    title = font(36)
    small = font(18)
    draw.text((28, 22), 'Remote glyphs', font=title, fill=LIGHT)
    icon_size = 84
    for index, (caption, image) in enumerate(labels):
        col, row = index % columns, index // columns
        x, y = 28 + col * cell, 72 + row * cell
        sheet.paste(image.resize((icon_size, icon_size), Image.Resampling.LANCZOS), (x + 16, y), image.resize((icon_size, icon_size), Image.Resampling.LANCZOS))
        draw.text((x + 16, y + icon_size + 4), caption, font=small, fill=LIGHT)
    base = 72 + rows * cell + 8
    draw.text((28, base), 'Controller glyphs', font=title, fill=LIGHT)
    for index, (caption, image) in enumerate(controllers):
        col, row = index % columns, index // columns
        x, y = 28 + col * cell, base + 52 + row * cell
        pasted = image.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        sheet.paste(pasted, (x + 16, y), pasted)
        draw.text((x + 16, y + icon_size + 4), caption, font=small, fill=LIGHT)
    sheet.save(ROOT / 'docs' / 'input-glyphs-preview.png')
    print('wrote', len(made), 'icons and docs/input-glyphs-preview.png')


if __name__ == '__main__':
    main()
