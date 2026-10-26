import json
from pathlib import Path

import pytest
from torf import Torrent

from src import main_cli
from src.api.startapi import api
from src.core.platforms import save_platform_templates


HIGH_HDR_MEDIAINFO = '''General
Overall bit rate : 20.8 Mb/s

Video
Width : 3 840 pixels
Height : 2 160 pixels
Transfer characteristics : PQ
HDR format : HDR Vivid, Version 1
'''


@pytest.fixture
def naming_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    static_dir = tmp_path / 'static'
    static_dir.mkdir()
    settings = {
        'file_name_movie': '{en_title}.{year}.{source}-{team}',
        'file_name_tv': '{en_title}.S{season}E{episode}.{source}-{team}',
        'file_name_playlet': '{en_title}.S{season}.{source}-{team}',
        'main_title_movie': '{en_title} {source}-{team}',
        'main_title_tv': '{en_title} S{season} {source}-{team}',
        'main_title_playlet': '{en_title} S{season} {source}-{team}',
        'second_title_movie': '{original_title} | {categories}',
        'second_title_tv': '{original_title} | {total_episodes}',
        'second_title_playlet': '{original_title} | {playlet_source}',
        'rename_file': 'True', 'make_dir': 'True', 'create_hard_link': '',
        'second_confirm_file_name': '', 'enable_api': '',
        'auto_download_upload_poster': '',
        'torrent_storage_path': str(tmp_path / 'torrents'),
    }
    (static_dir / 'settings.json').write_text(json.dumps(settings), encoding='utf-8')
    return tmp_path


def test_api_platform_requests_are_independent(naming_workspace):
    save_platform_templates('iQIYI', {'file_name_movie': '{platform}.{en_title}.{source}'})
    client = api.test_client()
    params = {'template': 'file_name_movie', 'englishTitle': 'Example', 'source': 'WEB-DL',
              'team': 'LongWeb'}
    for platform, expected in [
        ('爱奇艺', 'iQIYI.Example.WEB-DL'),
        ('Netflix', 'Example.NF.WEB-DL-LongWeb'),
        ('', 'Example.WEB-DL-LongWeb'),
    ]:
        response = client.get('/api/getNameFromTemplate', query_string={**params, 'platform': platform})
        assert response.status_code == 200, response.json
        assert response.json['data']['name'] == expected
    response = client.get('/api/getPlatforms')
    assert response.status_code == 200
    assert response.json['data']['platforms']['iQIYI']['templates']


@pytest.mark.parametrize('media_type', ['movie', 'tv', 'playlet'])
def test_cli_renames_files_and_creates_matching_torrent(naming_workspace, monkeypatch, media_type):
    save_platform_templates('iQIYI', {f'second_title_{media_type}': '{platform} | {original_title}'})
    monkeypatch.setattr(main_cli, 'get_pt_gen_description', lambda *args: (True, ('description', {})))
    monkeypatch.setattr(main_cli, 'get_pt_gen_info', lambda *args, **kwargs: (
        '示例', 'Example', '2026', [], '剧情', [], 2, 1,
    ))
    monkeypatch.setattr(main_cli, 'get_video_info', lambda *args: (True, [
        '2160p', 'H.265', '10bit', 'HDR10', '', 'DDP', '5.1', '',
    ]))
    monkeypatch.setattr(main_cli, 'get_media_info', lambda *args: (True, HIGH_HDR_MEDIAINFO))
    monkeypatch.setattr(main_cli, 'get_screenshot', lambda *args, **kwargs: (False, ['skip']))
    monkeypatch.setattr(main_cli, 'select_from_combo_box', lambda label, key: {'source': 'WEB-DL', 'team': 'LongWeb'}[key])
    monkeypatch.setattr('builtins.input', lambda *args: pytest.fail('Unexpected interactive prompt'))
    feed_calls = []
    monkeypatch.setattr(main_cli, 'generate_auto_feed_output', lambda *args: feed_calls.append(args))
    if media_type in ('movie', 'playlet'):
        video_path = naming_workspace / 'original.mkv'
        video_path.write_bytes(b'video content')
        if media_type == 'movie':
            result = main_cli.process_movie('https://example.test', str(video_path),
                                            source='WEB-DL', team='LongWeb', platform='爱奇艺')
        else:
            result = main_cli.process_playlet('Example', '2026', '大陆', '剧情', '国语', '网络收费短剧',
                                              str(video_path), 1, 1, platform='爱奇艺')
    else:
        video_path = naming_workspace / 'original'
        video_path.mkdir()
        for episode in (1, 2):
            (video_path / f'{episode:02d}.mkv').write_bytes(b'video content')
        result = main_cli.process_tv('https://example.test', str(video_path), 1, 1,
                                     source='WEB-DL', team='LongWeb', platform='爱奇艺')
    if media_type == 'playlet':
        assert result is True
        torrent_path, = (naming_workspace / 'torrents').glob('*.torrent')
        resource_path = naming_workspace / torrent_path.stem
    else:
        assert result and result['success']
        resource_path = Path(result['video_path'])
        torrent_path = Path(result['torrent_path'])
    assert resource_path.exists()
    assert '.iQIYI.WEB-DL-' in resource_path.name
    assert torrent_path.name == resource_path.name + '.torrent'
    torrent = Torrent.read(torrent_path)
    assert torrent.name == resource_path.name
    assert all('.iQIYI.WEB-DL-' in video.name for video in resource_path.glob('*.mkv'))
    assert feed_calls[0][1] == 'iQIYI | ' + ('Example' if media_type == 'playlet' else '示例') + ' | iQIYI【帧绮映画MAX】4K 20.8Mbps'
    if media_type == 'tv':
        assert any('S01E01' in video.name for video in resource_path.glob('*.mkv'))
        assert any('S01E02' in video.name for video in resource_path.glob('*.mkv'))


def test_cli_platform_selection_defaults_to_generic(naming_workspace, monkeypatch):
    monkeypatch.setattr(main_cli, 'prompt', lambda *args: '0')
    assert main_cli.select_platform() == ''
    monkeypatch.setattr(main_cli, 'prompt', lambda *args: '爱奇艺')
    assert main_cli.select_platform() == 'iQIYI'


def test_api_quality_note_uses_supplied_media_info(naming_workspace):
    response = api.test_client().get('/api/getNameFromTemplate', query_string={
        'template': 'second_title_movie', 'originalTitle': '示例', 'category': '剧情',
        'platform': '腾讯', 'mediaInfo': HIGH_HDR_MEDIAINFO,
    })
    assert response.status_code == 200, response.json
    assert response.json['data']['name'] == '示例 | 剧情 | Tencent【臻彩视听】4K 20.8Mbps'
