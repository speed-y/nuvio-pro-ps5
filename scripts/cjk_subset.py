"""Minimum code points the embedded CJK faces must cover.

The set is the common subtitle repertoire: GB2312 for Simplified Chinese,
Big5 level 1 for Traditional Chinese, JIS X 0208 level 1 (it contains the
Joyo kanji) for Japanese, and the 2,350 KS X 1001 Hangul syllables.
Kana, Jamo, CJK punctuation and fullwidth forms are included as ranges.
Unassigned scalars inside those ranges are left out.
The embedded Noto Sans CJK subset faces contain more Han than this set.
"""

import unicodedata


def _decode_grid(encoding, rows, cols):
    found = set()
    for row in rows:
        for col in cols:
            try:
                text = bytes([row, col]).decode(encoding)
            except UnicodeDecodeError:
                continue
            if len(text) == 1:
                found.add(ord(text))
    return found


def cjk_codepoints():
    """Return the assigned Unicode scalars the CJK faces must contain."""
    codes = set()
    for first, last in (
        (0x1100, 0x11FF),  # Hangul Jamo
        (0x3000, 0x303F),  # CJK punctuation
        (0x3040, 0x30FF),  # Hiragana and Katakana
        (0x3130, 0x318F),  # Hangul compatibility Jamo
        (0x31F0, 0x31FF),  # Katakana phonetic extensions
        (0xFE30, 0xFE4F),  # CJK compatibility forms
        (0xFF00, 0xFFEF),  # fullwidth forms and halfwidth kana
    ):
        codes.update(range(first, last + 1))
    codes.update(_decode_grid('gb2312', range(0xA1, 0xF8), range(0xA1, 0xFF)))
    codes.update(_decode_grid(
        'big5', range(0xA4, 0xC7), list(range(0x40, 0x7F)) + list(range(0xA1, 0xFF))))
    # EUC-JP rows 16-47 are JIS X 0208 level 1.
    codes.update(_decode_grid('euc_jp', range(0xB0, 0xD0), range(0xA1, 0xFF)))
    for row in range(0xB0, 0xC9):
        for col in range(0xA1, 0xFF):
            try:
                text = bytes([row, col]).decode('euc_kr')
            except UnicodeDecodeError:
                continue
            if len(text) == 1 and 0xAC00 <= ord(text) <= 0xD7A3:
                codes.add(ord(text))
    return {code for code in codes if unicodedata.category(chr(code)) != 'Cn'}


SAMPLES = {
    'simplified': '我们今天去看电影，字幕显示正常。「你好！」',
    'traditional': '我們今天去看電影，字幕顯示正常。「你好！」',
    'japanese': '今日は映画を見に行きます。字幕のテストです。',
    'korean': '오늘은 영화를 보러 갑니다. 자막이 잘 보입니다.',
}
