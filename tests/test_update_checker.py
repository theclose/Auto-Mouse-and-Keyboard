"""Tests for core.update_checker — version comparison and API handling."""


from core.update_checker import _version_compare


class TestVersionCompare:
    """Test semver comparison."""

    def test_equal(self):
        assert _version_compare("3.0.0", "3.0.0") == 0

    def test_newer_patch(self):
        assert _version_compare("3.0.1", "3.0.0") > 0

    def test_newer_minor(self):
        assert _version_compare("3.1.0", "3.0.0") > 0

    def test_newer_major(self):
        assert _version_compare("4.0.0", "3.0.0") > 0

    def test_older(self):
        assert _version_compare("2.9.9", "3.0.0") < 0

    def test_short_version(self):
        """Handles versions with fewer than 3 parts."""
        assert _version_compare("3.1", "3.0.0") > 0

    def test_non_numeric(self):
        """Handles non-numeric parts gracefully."""
        assert _version_compare("3.0.0-beta", "3.0.0") == 0


class TestCheckForUpdate:
    """Test the async check function (mocked)."""

    def test_callback_receives_result(self, monkeypatch):
        """Verify callback is called with parsed result."""
        import json
        from unittest.mock import patch

        fake_response = json.dumps({
            "tag_name": "v4.0.0",
            "html_url": "https://github.com/theclose/Auto-Mouse-and-Keyboard/releases/tag/v4.0.0",
        }).encode("utf-8")

        class FakeResponse:
            def read(self):
                return fake_response
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        results = []

        def _callback(has_update, latest, url):
            results.append((has_update, latest, url))

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            from core.update_checker import check_for_update
            check_for_update("3.0.0", on_result=_callback)

        # Wait for daemon thread
        import time
        time.sleep(1)

        assert len(results) == 1
        assert results[0][0] is True  # has_update
        assert results[0][1] == "4.0.0"
        assert "github.com" in results[0][2]

    def test_no_update(self, monkeypatch):
        """Callback reports no update when versions match."""
        import json
        from unittest.mock import patch

        fake_response = json.dumps({
            "tag_name": "v3.0.0",
            "html_url": "https://example.com",
        }).encode("utf-8")

        class FakeResponse:
            def read(self):
                return fake_response
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        results = []

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            from core.update_checker import check_for_update
            check_for_update("3.0.0", on_result=lambda h, v, u: results.append(h))

        import time
        time.sleep(1)

        assert len(results) == 1
        assert results[0] is False

    def test_network_error_silenced(self, monkeypatch):
        """Network errors are caught silently — no crash."""
        from unittest.mock import patch

        with patch("urllib.request.urlopen", side_effect=OSError("No network")):
            from core.update_checker import check_for_update
            # Should not raise
            check_for_update("3.0.0")

        import time
        time.sleep(1)
        # No assertion needed — just verify no crash
