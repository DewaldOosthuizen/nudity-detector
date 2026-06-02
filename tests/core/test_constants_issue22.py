"""
Tests for issue #22 — configurable Helloz NSFW API URL via config/app_config.json.
"""
import json
from unittest import mock

import pytest


class TestGetHellozNsfwUrl:
    def test_default_fallback_when_config_absent(self):
        """When config file is missing, uses hardcoded defaults."""
        from src.core import constants
        with mock.patch('builtins.open', side_effect=OSError('not found')):
            url = constants.get_helloz_nsfw_url()
        assert url == 'http://localhost:6086/api/upload_check'

    def test_loopback_host_uses_http_by_default(self, tmp_path):
        """Loopback host defaults to http scheme when no scheme is configured."""
        from src.core import constants
        cfg = {
            'helloz_nsfw_host': 'localhost',
            'helloz_nsfw_port': 9000,
            'helloz_nsfw_api_endpoint': '/v2/check',
        }
        config_path = tmp_path / 'app_config.json'
        config_path.write_text(json.dumps(cfg))
        with mock.patch('src.core.constants._config_path', return_value=str(config_path)):
            url = constants.get_helloz_nsfw_url()
        assert url == 'http://localhost:9000/v2/check'

    def test_remote_host_uses_https_by_default(self, tmp_path):
        """Non-loopback host defaults to https scheme when no scheme is configured."""
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
        assert url == 'https://myserver:9000/v2/check'

    def test_explicit_https_scheme_accepted_for_remote_host(self, tmp_path):
        """Explicitly configured https scheme is used for a remote host."""
        from src.core import constants
        cfg = {
            'helloz_nsfw_scheme': 'https',
            'helloz_nsfw_host': 'myserver',
            'helloz_nsfw_port': 9000,
            'helloz_nsfw_api_endpoint': '/v2/check',
        }
        config_path = tmp_path / 'app_config.json'
        config_path.write_text(json.dumps(cfg))
        with mock.patch('src.core.constants._config_path', return_value=str(config_path)):
            url = constants.get_helloz_nsfw_url()
        assert url == 'https://myserver:9000/v2/check'

    def test_http_scheme_rejected_for_remote_host(self, tmp_path):
        """Explicitly configured http scheme raises ValueError for a non-loopback host."""
        from src.core import constants
        cfg = {
            'helloz_nsfw_scheme': 'http',
            'helloz_nsfw_host': 'myserver',
            'helloz_nsfw_port': 9000,
            'helloz_nsfw_api_endpoint': '/v2/check',
        }
        config_path = tmp_path / 'app_config.json'
        config_path.write_text(json.dumps(cfg))
        with mock.patch('src.core.constants._config_path', return_value=str(config_path)):
            with pytest.raises(ValueError, match="'http' is not allowed for non-loopback host"):
                constants.get_helloz_nsfw_url()

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

    def test_loopback_host_uses_http_by_default(self, tmp_path):
        """Loopback host defaults to http scheme."""
        from src.core import constants
        cfg = {
            'helloz_nsfw_host': '127.0.0.1',
            'helloz_nsfw_port': 8888,
        }
        config_path = tmp_path / 'app_config.json'
        config_path.write_text(json.dumps(cfg))
        with mock.patch('src.core.constants._config_path', return_value=str(config_path)):
            url = constants.get_helloz_nsfw_connection_check_url()
        assert url == 'http://127.0.0.1:8888'

    def test_remote_host_uses_https_by_default(self, tmp_path):
        """Connection check URL uses https for a non-loopback host."""
        from src.core import constants
        cfg = {
            'helloz_nsfw_host': 'remotehost',
            'helloz_nsfw_port': 8888,
        }
        config_path = tmp_path / 'app_config.json'
        config_path.write_text(json.dumps(cfg))
        with mock.patch('src.core.constants._config_path', return_value=str(config_path)):
            url = constants.get_helloz_nsfw_connection_check_url()
        assert url == 'https://remotehost:8888'

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
