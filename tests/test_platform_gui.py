import pytest
from PyQt6.QtWidgets import QApplication

from src.core.platforms import load_platforms, save_platform_templates
from src.gui import startgui


@pytest.fixture(scope='module')
def qt_app():
    return QApplication.instance() or QApplication(['platform-tests', '-platform', 'offscreen'])


def test_gui_has_separate_platform_selectors(qt_app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(startgui, 'get_settings', lambda key: '')
    monkeypatch.setattr(startgui, 'get_combo_box_data', lambda key: (True, ['WEB-DL']))
    window = startgui.mainwindow()
    for suffix in ('Movie', 'TV', 'Playlet'):
        combo = getattr(window, f'platform{suffix}')
        assert combo.currentText() == ''
        assert combo.findText('iQIYI') > 0
        assert combo.isEditable()
    window.platformMovie.setCurrentText('NF')
    assert window.platformTV.currentText() == ''
    assert window.platformPlaylet.currentText() == ''
    window.close()


def test_gui_rule_editor_preserves_other_media_types(qt_app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(startgui, 'get_settings', lambda key: '{en_title}.{source}')
    save_platform_templates('iQIYI', {'file_name_tv': '{en_title}.S{season}.{platform}'})
    dialog = startgui.PlatformRulesDialog('爱奇艺', 'movie')
    dialog.fields['file_name_movie'].setText('{platform}.{en_title}.{source}')
    dialog.save_rules()
    assert dialog.result() == dialog.DialogCode.Accepted
    templates = load_platforms()['iQIYI']['templates']
    assert templates['file_name_movie'] == '{platform}.{en_title}.{source}'
    assert templates['file_name_tv'] == '{en_title}.S{season}.{platform}'
    dialog = startgui.PlatformRulesDialog('iQIYI', 'movie')
    dialog.fields['file_name_movie'].clear()
    dialog.save_rules()
    assert 'file_name_movie' not in load_platforms()['iQIYI']['templates']


def test_gui_quality_metadata_comes_from_current_video(monkeypatch):
    calls = []
    monkeypatch.setattr(startgui, 'get_media_info', lambda path: (calls.append(path) or True, 'current MediaInfo'))
    assert startgui.get_platform_media_info('current.mkv', 'iQIYI') == 'current MediaInfo'
    assert calls == ['current.mkv']
    assert startgui.get_platform_media_info('other.mkv', '') == ''
    assert calls == ['current.mkv']
