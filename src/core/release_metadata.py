import re

from src.core.platforms import get_platform


def split_mediainfo_sections(media_info):
    sections = []
    current = ''
    lines = []
    for line in str(media_info or '').splitlines():
        heading = re.fullmatch(r'(General|Video|Audio|Text|Menu)(?:\s*#\d+)?', line.strip(), re.IGNORECASE)
        if heading:
            if current:
                sections.append((current, '\n'.join(lines)))
            current = heading.group(1).lower()
            lines = [line]
        elif current:
            lines.append(line)
    if current:
        sections.append((current, '\n'.join(lines)))
    return sections


def section_text(sections, *names):
    return '\n'.join(text for name, text in sections if name in names)


def parse_overall_bitrate_mbps(media_info):
    sections = split_mediainfo_sections(media_info)
    general = section_text(sections, 'general') if sections else str(media_info or '')
    pattern = r'^\s*Overall bit rate\s*:\s*([\d][\d ,.]*?)\s*([kmg]?)(?:b/s|bps)\b'
    values = []
    for value, prefix in re.findall(pattern, general, re.IGNORECASE | re.MULTILINE):
        number = float(value.replace(' ', '').replace(',', ''))
        values.append(number * {'': 0.000001, 'k': 0.001, 'm': 1, 'g': 1000}[prefix.lower()])
    return max(values, default=0.0)


def parse_video_frame_rate(media_info):
    text = section_text(split_mediainfo_sections(media_info), 'video', 'general')
    values = re.findall(r'^\s*Frame rate\s*:\s*([\d.]+)(?:\s*\([^\n]*?\))?\s*FPS\b', text, re.IGNORECASE | re.MULTILINE)
    return max((float(value) for value in values), default=0.0)


def pixel_number(value):
    match = re.search(r'\d+', str(value or '').replace(' ', '').replace(',', ''))
    return int(match.group()) if match else 0


def resolution_from_dimensions(width, height):
    width, height = pixel_number(width), pixel_number(height)
    if not width and not height:
        return ''
    use_width = bool(width)
    if width and height:
        long_edge, short_edge = max(width, height), min(width, height)
        use_width = long_edge / short_edge >= 1.5
        value = long_edge if use_width else short_edge
    else:
        value = width or height
    thresholds = (
        (4608 if use_width else 4000, '4320p'),
        (3200 if use_width else 2000, '2160p'),
        (2240 if use_width else 1400, '1440p'),
        (1600 if use_width else 1000, '1080p'),
        (900 if use_width else 700, '720p'),
        (533 if use_width else 400, '480p'),
    )
    return next((label for minimum, label in thresholds if value >= minimum), '480p')


def normalize_hdr_format(hdr_format, transfer=''):
    raw = str(hdr_format or '').strip()
    value = raw.replace('.', ' ').lower()
    transfer = str(transfer or '').lower()
    if re.search(r'bt\.?\s*709|bt\.?\s*601|\bsdr\b', transfer):
        return ''
    dolby = bool(re.search(r'dolby\s*vision|dvhe|dvh1|\bdv\b', value))
    hdr_plus = bool(re.search(r'hdr10\+|smpte\s*st\s*2094', value))
    hdr10 = bool(re.search(r'hdr10|smpte\s*st\s*2086', value))
    if dolby and hdr_plus:
        return 'DV HDR10+ Hybrid'
    if dolby and hdr10:
        return 'DV HDR10 Hybrid'
    if dolby:
        return 'DV'
    if hdr_plus:
        return 'HDR10+'
    if hdr10:
        return 'HDR10'
    if 'hdr vivid' in value or value == 'hdr':
        return 'HDR'
    if re.search(r'\bhlg\b|arib\s*std.?b67', value + ' ' + transfer):
        return 'HLG'
    if re.search(r'\bpq\b|smpte\s*st\s*2084', transfer):
        return 'HDR10'
    return '' if not raw or value == 'sdr' else None


def _video_fields(media_info):
    sections = split_mediainfo_sections(media_info)
    video = next((text for name, text in sections if name == 'video'), '')
    return {
        key.strip().lower(): value.strip()
        for key, value in re.findall(r'^\s*([^:\n]+):\s*([^\n]*)', video, re.MULTILINE)
    }


def _has_hdr(fields):
    transfer = fields.get('transfer characteristics', '')
    hdr = normalize_hdr_format(fields.get('hdr format', ''), transfer)
    if hdr == 'HDR10' and not transfer:
        return False
    return bool(hdr)


def _valid_quality_summary(summary, fields, media_info):
    hdr_brands = r'帧绮映画|4K\s*MAX\s*\+|臻彩|帧享(?!影院)'
    if re.search(hdr_brands, summary, re.IGNORECASE) and not _has_hdr(fields):
        return False
    if re.search(r'帧享\s*120\s*帧', summary) and parse_video_frame_rate(media_info) < 100:
        return False
    return True


def append_quality_note(second_title, quality_summary='', media_info='', platform=''):
    title = str(second_title or '')
    label = get_platform(platform)[0]
    fields = _video_fields(media_info)
    explicit = str(quality_summary or '').strip()
    note = explicit if _valid_quality_summary(explicit, fields, media_info) else ''
    resolution = resolution_from_dimensions(fields.get('width', ''), fields.get('height', ''))
    bitrate = parse_overall_bitrate_mbps(media_info)
    fallback = ''
    if (resolution == '2160p' and bitrate >= 12) or (resolution == '1080p' and bitrate >= 8):
        brands = {'iQIYI': '帧绮映画MAX', 'Tencent': '臻彩视听', 'YouKu': '帧享影院'}
        brand = brands.get(label, '') if resolution == '2160p' else ''
        if label != 'YouKu' and not _has_hdr(fields):
            brand = ''
        speed = f'{bitrate:.1f}'.rstrip('0').rstrip('.')
        quality = f'【{brand}】4K' if brand else ('4K高码率' if resolution == '2160p' else '1080P高码率')
        fallback = f'{label}{quality} {speed}Mbps'
    brand_pattern = r'帧享影院|帧享\s*120\s*帧|帧享|帧绮映画(?:MAX)?|臻彩(?:视听|MAX)?|4K\s*MAX\s*\+'
    if not note or (fallback and not re.search(brand_pattern, note) and '【' in fallback):
        note = fallback
    if note and '【' not in note:
        note = re.sub(f'({brand_pattern})', r'【\1】', note, count=1, flags=re.IGNORECASE)
        note = re.sub(r'】\s+', '】', note)
    if not note or note in title:
        return title
    return f'{title} | {note}' if title else note
