"""Draw the remote glyph PNGs and the comparison sheet in docs/."""
from pathlib import Path
import tarfile
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'remote-glyphs'
FONT = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')

PAPER = (17, 19, 31, 255)
LIGHT = (244, 244, 248, 255)
RED = (214, 69, 69, 255)
GREEN = (47, 158, 79, 255)
YELLOW = (226, 177, 26, 255)
BLUE = (59, 111, 226, 255)
EDGE = (108, 113, 150, 255)


def font(size):
    return ImageFont.truetype(str(FONT), size) if FONT.is_file() else ImageFont.load_default()


def rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=EDGE, width=2)


def icon(label, fill, ink, wide=False):
    image = Image.new('RGBA', (96 if wide else 64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    rounded(draw, (4, 10, image.width - 5, 54), 12, fill)
    if label:
        face = font(18 if len(label) > 2 else 22)
        box = draw.textbbox((0, 0), label, font=face)
        x = (image.width - (box[2] - box[0])) / 2
        y = (64 - (box[3] - box[1])) / 2 - 1
        draw.text((x, y), label, font=face, fill=ink)
    return image


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    specs = {
        'btn_remote_ok.png': ('OK', PAPER, LIGHT, False),
        'btn_remote_back.png': ('Back', PAPER, LIGHT, True),
        'btn_remote_menu.png': ('Menu', PAPER, LIGHT, True),
        'btn_remote_arrows.png': ('<>', PAPER, LIGHT, False),
        'btn_remote_red.png': ('', RED, LIGHT, False),
        'btn_remote_green.png': ('', GREEN, LIGHT, False),
        'btn_remote_yellow.png': ('', YELLOW, (26, 26, 26, 255), False),
        'btn_remote_blue.png': ('', BLUE, LIGHT, False),
        'btn_remote_info.png': ('i', PAPER, LIGHT, False),
        'btn_remote_play.png': ('>', PAPER, LIGHT, False),
        'btn_remote_pause.png': ('||', PAPER, LIGHT, False),
        'btn_remote_ch_up.png': ('CH+', PAPER, LIGHT, True),
        'btn_remote_ch_down.png': ('CH-', PAPER, LIGHT, True),
    }
    for digit in range(10):
        specs['btn_remote_%d.png' % digit] = (str(digit), PAPER, LIGHT, False)
    made = {}
    for name, spec in specs.items():
        image = icon(*spec)
        image.save(OUT / name)
        made[name] = image

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

    labels = [
        ('OK', made['btn_remote_ok.png']),
        ('Back', made['btn_remote_back.png']),
        ('Menu', made['btn_remote_menu.png']),
        ('Arrows', made['btn_remote_arrows.png']),
        ('Red', made['btn_remote_red.png']),
        ('Green', made['btn_remote_green.png']),
        ('Yellow', made['btn_remote_yellow.png']),
        ('Blue', made['btn_remote_blue.png']),
        ('Info', made['btn_remote_info.png']),
        ('Play', made['btn_remote_play.png']),
        ('Pause', made['btn_remote_pause.png']),
        ('CH+', made['btn_remote_ch_up.png']),
        ('CH-', made['btn_remote_ch_down.png']),
    ] + [(str(n), made['btn_remote_%d.png' % n]) for n in range(10)]

    cell_w, cell_h = 120, 108
    columns = 8
    rows = (len(labels) + columns - 1) // columns
    controller_rows = (len(controllers) + columns - 1) // columns
    width = 48 + columns * cell_w
    height = 90 + rows * cell_h + 70 + controller_rows * cell_h
    sheet = Image.new('RGB', (width, height), (12, 14, 24))
    draw = ImageDraw.Draw(sheet)
    title = font(28)
    small = font(16)
    draw.text((32, 24), 'Remote glyphs', font=title, fill=LIGHT)
    for index, (label, image) in enumerate(labels):
        col, row = index % columns, index // columns
        x, y = 32 + col * cell_w, 70 + row * cell_h
        sheet.paste(image, (x + 12, y), image)
        draw.text((x + 8, y + 70), label, font=small, fill=LIGHT)
    base = 70 + rows * cell_h + 16
    draw.text((32, base), 'Controller glyphs', font=title, fill=LIGHT)
    for index, (label, image) in enumerate(controllers):
        col, row = index % columns, index // columns
        x, y = 32 + col * cell_w, base + 48 + row * cell_h
        sheet.paste(image, (x + 28, y + 8), image)
        draw.text((x + 8, y + 76), label, font=small, fill=LIGHT)
    sheet.save(ROOT / 'docs' / 'input-glyphs-preview.png')
    print('wrote', OUT, 'and docs/input-glyphs-preview.png')


if __name__ == '__main__':
    main()
