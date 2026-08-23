"""
Tests for issue #72 — startup validation logging in _load_helloz_config.
"""
from unittest import mock

import pytest


class TestLoadHellozConfigWarning:
    def test_warning_emitted_when_config_missing(self):
        """_load_helloz_config logs a warning when app_config.json is missing."""
        from src.core import constants
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
        from src.core import constants
        import json
        import os
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
