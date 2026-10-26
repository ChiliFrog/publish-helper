import json
import os
import re
import tempfile
from pathlib import Path


DEFAULT_PLATFORMS = {
    'iQIYI': ['爱奇艺', 'IQY'],
    'Tencent': ['腾讯', '腾讯视频', 'WeTV', 'TX'],
    'YouKu': ['优酷', 'YK'],
    'Bilibili': ['哔哩哔哩', 'B站', 'BILI'],
    'MGTV': ['芒果', '芒果TV'],
    'DSNP': ['DisneyPlus', 'Disney+', '迪士尼'],
    'NF': ['Netflix', '奈飞', '网飞'],
    'AMZN': ['Amazon', 'Prime Video'],
    'HMAX': ['HBO Max', 'Max'],
    'ATVP': ['AppleTV+', 'Apple TV+'],
}
TEMPLATE_KEYS = {
    f'{kind}_{media_type}'
    for kind in ('file_name', 'main_title', 'second_title')
    for media_type in ('movie', 'tv', 'playlet')
}
TEMPLATE_FIELDS = {
    'en_title', 'original_title', 'season', 'episode', 'year', 'video_format',
    'source', 'platform', 'video_codec', 'bit_depth', 'hdr_format', 'frame_rate',
    'audio_codec', 'channels', 'audio_num', 'team', 'other_titles',
    'season_number', 'total_episodes', 'playlet_source', 'categories', 'actors',
    '集数',
}


def load_platforms():
    profiles = {
        label: {'aliases': list(aliases), 'templates': {}}
        for label, aliases in DEFAULT_PLATFORMS.items()
    }
    config_path = Path('static/platforms.json')
    if config_path.exists():
        try:
            overrides = json.loads(config_path.read_text(encoding='utf-8-sig'))
        except (ValueError, OSError) as error:
            raise ValueError(f'读取平台命名配置失败：{error}') from error
        if not isinstance(overrides, dict):
            raise ValueError('平台命名配置必须是 JSON 对象')
        for label, profile in overrides.items():
            if not label.strip() or not isinstance(profile, dict):
                raise ValueError(f'无效的平台配置：{label}')
            profiles[label] = {
                **profiles.get(label, {'aliases': [], 'templates': {}}),
                **profile,
            }
    _validate_platforms(profiles)
    return profiles


def _validate_platforms(profiles):
    identifiers = {}
    for label, profile in profiles.items():
        if set(profile) - {'aliases', 'templates'}:
            raise ValueError(f'{label} 的配置仅支持 aliases 和 templates')
        aliases = profile.get('aliases', [])
        templates = profile.get('templates', {})
        if not isinstance(aliases, list) or not all(
            isinstance(alias, str) and alias.strip() for alias in aliases
        ):
            raise ValueError(f'{label} 的 aliases 必须是非空字符串列表')
        if not isinstance(templates, dict):
            raise ValueError(f'{label} 的 templates 必须是 JSON 对象')
        for key, template in templates.items():
            if (
                key not in TEMPLATE_KEYS
                or not isinstance(template, str)
                or not template.strip()
            ):
                raise ValueError(f'{label} 的命名模板无效：{key}')
            unknown = set(re.findall(r'\{([^{}]+)\}', template)) - TEMPLATE_FIELDS
            if unknown:
                raise ValueError(f'{label}/{key} 包含未知占位符：{", ".join(sorted(unknown))}')
            remainder = re.sub(r'\{[^{}]+\}', '', template)
            if '{' in remainder or '}' in remainder:
                raise ValueError(f'{label}/{key} 的占位符括号不完整')
        for identifier in [label, *aliases]:
            normalized = identifier.strip().casefold()
            if normalized in identifiers and identifiers[normalized] != label:
                raise ValueError(f'平台名称或别名重复：{identifier}')
            identifiers[normalized] = label


def get_platform(platform, profiles=None):
    label = str(platform or '').strip()
    if not label:
        return '', {'aliases': [], 'templates': {}}
    if profiles is None:
        profiles = load_platforms()
    for canonical, profile in profiles.items():
        identifiers = [canonical, *profile['aliases']]
        if label.casefold() in {value.strip().casefold() for value in identifiers}:
            return canonical, profile
    return label, {'aliases': [], 'templates': {}}


def normalize_platform_source(platform, source):
    label = get_platform(platform)[0]
    source = str(source or '').strip()
    if not label:
        return source
    if source and not re.search(r'WEB[ ._-]*(?:DL|RIP)', source, re.IGNORECASE):
        profiles = load_platforms()
        identifiers = [value for canonical, profile in profiles.items() for value in [canonical, *profile['aliases']]]
        if source.casefold() not in {value.casefold() for value in identifiers}:
            return source
        return 'WEB-DL'
    profiles = load_platforms()
    for canonical, profile in profiles.items():
        for alias in [canonical, *profile['aliases']]:
            pattern = r'(?<![^\W_])' + re.escape(alias.strip()) + r'(?![^\W_])'
            source = re.sub(pattern, '', source, flags=re.IGNORECASE)
    source = re.sub(r'WEB[ ._-]*DL', 'WEB-DL', source, flags=re.IGNORECASE)
    source = re.sub(r'WEB[ ._-]*RIP', 'WEBRip', source, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', source).strip(' ._-') or 'WEB-DL'


def prepare_platform_template(template_key, template, platform, source):
    label, profile = get_platform(platform)
    override = profile['templates'].get(template_key)
    if override is not None:
        template = override
    elif (
        label
        and template_key.startswith(('file_name_', 'main_title_'))
        and '{platform}' not in template
    ):
        separator = '.' if template_key.startswith('file_name_') else ' '
        template = template.replace('{source}', '{platform}' + separator + '{source}')
    platform_token = label
    if label and '{source}' in template:
        for alias in [label, *profile['aliases']]:
            pattern = r'(?<![^\W_])' + re.escape(alias.strip()) + r'(?![^\W_])'
            if re.search(pattern, source, re.IGNORECASE):
                platform_token = ''
                break
    return template, platform_token


def save_platform_templates(platform, templates):
    profiles = load_platforms()
    label, profile = get_platform(platform, profiles)
    if not label:
        raise ValueError('请先选择或输入平台')
    profile = {**profile, 'templates': templates}
    profiles[label] = profile
    _validate_platforms(profiles)
    config_path = Path('static/platforms.json')
    overrides = (
        json.loads(config_path.read_text(encoding='utf-8-sig'))
        if config_path.exists() else {}
    )
    overrides[label] = profile
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode='w', encoding='utf-8', dir=config_path.parent,
        prefix='.platforms-', suffix='.tmp', delete=False,
    ) as pending:
        pending_path = Path(pending.name)
        try:
            pending.write(json.dumps(overrides, ensure_ascii=False, indent=4) + '\n')
        except OSError:
            pending.close()
            pending_path.unlink(missing_ok=True)
            raise
    try:
        os.replace(pending_path, config_path)
    finally:
        pending_path.unlink(missing_ok=True)
