"""
Tests for issue #22 — configurable Helloz NSFW API URL via config/app_config.json.
"""
import json
import os
from unittest import mock

import pytest


class TestGetHellozNsfwUrl:
    def test_default_fallback_when_config_absent(self):
        """When config file is missing, uses hardcoded defaults."""
        from src.core import constants
        with mock.patch('builtins.open', side_effect=OSError('not found')):
            url = constants.get_helloz_nsfw_url()
        assert url == 'http://localhost:6086/api/upload_check'

    def test_values_read_from_config(self, tmp_path):
        """URL is built from values in config/app_config.json."""
        from src.core import constants
        cfg = {
            'helloz_nsfw_host': 'myserver',
            'helloz_nsfw_port': 9000,
            'helloz_nsfw_api_endpoint': '/v2/check',
        }
        config_path = tmp_path / 'app_config.json'
        config_path.write_text(json.dumps(cfg))
        with mock.patch('src.core.constants._config_path', return_value=str(config_path)):
            url = constants.get_helloz_nsfw_url()
        assert url == 'http://myserver:9000/v2/check'

    def test_malformed_json_fallback(self, tmp_path):
        """Malformed JSON causes fallback to defaults."""
        from src.core import constants
        config_path = tmp_path / 'app_config.json'
        config_path.write_text('{ not valid json')
        with mock.patch('src.core.constants._config_path', return_value=str(config_path)):
            url = constants.get_helloz_nsfw_url()
        assert url == 'http://localhost:6086/api/upload_check'


class TestGetHellozNsfwConnectionCheckUrl:
    def test_default_fallback_when_config_absent(self):
        """When config file is missing, uses hardcoded defaults."""
        from src.core import constants
        with mock.patch('builtins.open', side_effect=OSError('not found')):
            url = constants.get_helloz_nsfw_connection_check_url()
        assert url == 'http://localhost:6086'

    def test_values_read_from_config(self, tmp_path):
        """Connection check URL uses host/port from config."""
        from src.core import constants
        cfg = {
            'helloz_nsfw_host': 'remotehost',
            'helloz_nsfw_port': 8888,
        }
        config_path = tmp_path / 'app_config.json'
        config_path.write_text(json.dumps(cfg))
        with mock.patch('src.core.constants._config_path', return_value=str(config_path)):
            url = constants.get_helloz_nsfw_connection_check_url()
        assert url == 'http://remotehost:8888'

    def test_malformed_json_fallback(self, tmp_path):
        """Malformed JSON causes fallback to defaults."""
        from src.core import constants
        config_path = tmp_path / 'app_config.json'
        config_path.write_text('{bad}')
        with mock.patch('src.core.constants._config_path', return_value=str(config_path)):
            url = constants.get_helloz_nsfw_connection_check_url()
        assert url == 'http://localhost:6086'


class TestModuleLevelAliases:
    def test_helloz_nsfw_url_alias_exists(self):
        from src.core import constants
        assert hasattr(constants, 'HELLOZ_NSFW_URL')
        assert constants.HELLOZ_NSFW_URL.startswith('http://')

    def test_helloz_nsfw_connection_check_url_alias_exists(self):
        from src.core import constants
        assert hasattr(constants, 'HELLOZ_NSFW_CONNECTION_CHECK_URL')
        assert constants.HELLOZ_NSFW_CONNECTION_CHECK_URL.startswith('http://')
