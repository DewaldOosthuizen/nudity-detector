"""
Tests for issue #72 — startup validation logging in _load_helloz_config.
"""
import json
from unittest import mock

import pytest

from src.core import constants


class TestLoadHellozConfigWarning:
    def test_warning_emitted_when_config_missing(self):
        """_load_helloz_config logs a warning when app_config.json is missing."""
        with mock.patch('builtins.open', side_effect=OSError('not found')):
            with mock.patch.object(constants.logger, 'warning') as mock_warning:
                result = constants._load_helloz_config()
        assert result == (constants.HELLOZ_NSFW_HOST,
                          constants.HELLOZ_NSFW_PORT,
                          constants.HELLOZ_NSFW_API_ENDPOINT,
                          'http')
        mock_warning.assert_called_once()
        msg = mock_warning.call_args[0][0]
        assert 'app_config.json not found or invalid' in msg
        assert 'using built-in defaults' in msg

    def test_warning_emitted_when_config_malformed(self, tmp_path):
        """_load_helloz_config logs a warning when app_config.json is malformed."""
        config_path = tmp_path / 'app_config.json'
        config_path.write_text('{ not valid json')
        original_path = constants._config_path()
        try:
            with mock.patch.object(constants, '_config_path', return_value=str(config_path)):
                with mock.patch.object(constants.logger, 'warning') as mock_warning:
                    result = constants._load_helloz_config()
            assert result == (constants.HELLOZ_NSFW_HOST,
                              constants.HELLOZ_NSFW_PORT,
                              constants.HELLOZ_NSFW_API_ENDPOINT,
                              'http')
            mock_warning.assert_called_once()
            msg = mock_warning.call_args[0][0]
            assert 'app_config.json not found or invalid' in msg
            assert 'using built-in defaults' in msg
        finally:
            if str(config_path) != original_path:
                pass


def test_helloz_max_file_bytes_uses_config_override(tmp_path):
    config_path = tmp_path / 'app_config.json'
    config_path.write_text(json.dumps({'helloz_nsfw_max_file_bytes': 1234}), encoding='utf-8')

    with mock.patch.object(constants, '_config_path', return_value=str(config_path)):
        assert constants.get_helloz_nsfw_max_file_bytes() == 1234


def test_helloz_max_file_bytes_defaults_when_config_is_missing():
    with mock.patch('builtins.open', side_effect=OSError('not found')):
        assert constants.get_helloz_nsfw_max_file_bytes() == constants.HELLOZ_NSFW_MAX_FILE_BYTES


def test_ensure_helloz_nsfw_file_size_rejects_oversize_and_accepts_boundary(tmp_path, monkeypatch):
    file_path = tmp_path / 'frame.jpg'
    file_path.write_bytes(b'1234')
    monkeypatch.setattr(constants, 'get_helloz_nsfw_max_file_bytes', lambda: 4)

    constants.ensure_helloz_nsfw_file_size(file_path)

    file_path.write_bytes(b'12345')
    with pytest.raises(ValueError, match=r'5 bytes.*4-byte limit'):
        constants.ensure_helloz_nsfw_file_size(file_path)
