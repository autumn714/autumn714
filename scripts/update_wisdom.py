"""Rotate traditional Korean idioms/proverbs daily in KST, without an API."""
import json
import unicodedata
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9), 'Asia/Seoul')
START = '<!-- WISDOM:START -->'
END = '<!-- WISDOM:END -->'


def wrapped(text, limit=78):
    lines, line, width = [], '', 0
    for char in text:
        size = 2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
        if width + size > limit:
            lines.append(line.rstrip())
            line, width = '', 0
        line += char
        width += size
    if line:
        lines.append(line.rstrip())
    return lines


def card(entry, kind):
    accent = '#f0b866' if kind == 'idiom' else '#76c7b7'
    eyebrow = entry.get('hanja', '한국 속담')
    title_size = 26 if kind == 'idiom' else 22
    lines = wrapped(entry['meaning'])
    height = 144 + max(0, len(lines) - 1) * 22
    title = entry['text'] + ' — ' + entry['meaning']
    content = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="{height}" viewBox="0 0 640 {height}" role="img" aria-labelledby="title">',
        f'<title id="title">{escape(title)}</title>',
        f'<rect x=".5" y=".5" width="639" height="{height-1}" rx="10" fill="#151515" stroke="#424242"/>',
        f'<rect x="24" y="26" width="3" height="{height-52}" rx="1.5" fill="{accent}"/>',
        '<g font-family="Malgun Gothic, Apple SD Gothic Neo, Noto Sans CJK KR, sans-serif">',
        f'<text x="44" y="39" font-size="14" fill="{accent}">{escape(eyebrow)}</text>',
        f'<text x="44" y="78" font-size="{title_size}" font-weight="700" fill="#f4f4f5">{escape(entry["text"])}</text>',
    ]
    for index, line in enumerate(lines):
        content.append(f'<text x="44" y="{111+index*22}" font-size="14" fill="#c4c4cc">{escape(line)}</text>')
    return '\n'.join(content + ['</g>', '</svg>', ''])


def main():
    source = json.loads((ROOT / 'profile/wisdom.json').read_text(encoding='utf-8'))
    today = datetime.now(KST).date()
    offset = (today - date(2026, 9, 29)).days
    idiom = source['idioms'][offset % len(source['idioms'])]
    proverb = source['proverbs'][offset % len(source['proverbs'])]
    readme_path = ROOT / 'README.md'
    readme = readme_path.read_text(encoding='utf-8')
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError('README must have one wisdom marker pair')
    begin, end = readme.index(START), readme.index(END)
    if begin >= end:
        raise ValueError('Invalid wisdom marker order')
    idiom_alt = escape(f'{idiom["text"]} ({idiom["hanja"]}): {idiom["meaning"]}', quote=True)
    proverb_alt = escape(f'{proverb["text"]}: {proverb["meaning"]}', quote=True)
    section = f'''{START}
### 📜 오늘의 사자성어

<img src="./assets/daily-idiom.svg" width="640" alt="{idiom_alt}" />

### 🌿 오늘의 한국 속담

<img src="./assets/daily-proverb.svg" width="640" alt="{proverb_alt}" />

<sub>한국 시간 기준 매일 새로운 한마디 · {today}</sub>
{END}'''
    (ROOT / 'assets/daily-idiom.svg').write_text(card(idiom, 'idiom'), encoding='utf-8')
    (ROOT / 'assets/daily-proverb.svg').write_text(card(proverb, 'proverb'), encoding='utf-8')
    readme_path.write_text(readme[:begin] + section + readme[end+len(END):], encoding='utf-8')
    print(f'Updated daily Korean idiom and proverb for {today} (KST).')


if __name__ == '__main__':
    main()
