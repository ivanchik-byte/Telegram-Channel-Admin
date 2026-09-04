import os

import pytest

from src.core.utils import (
    parse_time_suffix,
    format_seconds_readable,
    strip_html,
    delete_media_file,
    cleanup_old_media_files,
)
from datetime import timedelta


class TestParseTimeSuffix:
    def test_seconds(self):
        assert parse_time_suffix("30s") == timedelta(seconds=30)

    def test_minutes(self):
        assert parse_time_suffix("45m") == timedelta(minutes=45)

    def test_hours(self):
        assert parse_time_suffix("12h") == timedelta(hours=12)

    def test_days(self):
        assert parse_time_suffix("7d") == timedelta(days=7)

    def test_bare_number_is_seconds(self):
        assert parse_time_suffix("90") == timedelta(seconds=90)

    def test_zero_minutes_is_valid_timedelta(self):
        # regression: "/interval 0m-30m" must not be rejected
        delta = parse_time_suffix("0m")
        assert delta is not None and delta.total_seconds() == 0

    def test_invalid_returns_none(self):
        assert parse_time_suffix("abc") is None
        assert parse_time_suffix("") is None


@pytest.fixture(autouse=True)
def english_units():
    """format_seconds_readable output depends on the global UI language."""
    from src.core.i18n import i18n
    i18n.set_language("en")
    yield
    i18n.set_language("ru")


class TestFormatSecondsReadable:
    def test_zero(self):
        assert "0" in format_seconds_readable(0)

    def test_complex_duration(self):
        result = format_seconds_readable(90061)  # 1d 1h 1min 1s
        assert result == "1 d 1 h 1 min 1 sec"

    def test_roundtrip_hours(self):
        text = format_seconds_readable(3600)
        assert text == "1 h"


class TestStripHtml:
    def test_tags_removed(self):
        assert strip_html("<b>bold</b> plain") == "bold plain"

    def test_entities_unescaped(self):
        assert strip_html("<b>a &amp; b</b>") == "a & b"

    def test_href_content_kept_as_text(self):
        assert strip_html('x <a href="u">&lt;tag&gt;</a> y') == "x <tag> y"


class TestDeleteMediaFile:
    @pytest.fixture()
    def media_root(self, tmp_path, monkeypatch):
        root = tmp_path / "data" / "media"
        root.mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        return root

    def test_deletes_file_inside_media_root(self, media_root):
        f = media_root / "photo.jpg"
        f.write_bytes(b"x")
        assert delete_media_file(str(f)) is True
        assert not f.exists()

    def test_refuses_relative_escape(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "secret.txt").write_text("nope")
        assert delete_media_file("../secret.txt") is False
        assert (tmp_path / "secret.txt").exists()

    def test_traversal_prefix_trick_blocked(self, tmp_path, monkeypatch):
        # classic startswith() bypass: data/media_evil/... — commonpath must reject it
        evil = tmp_path / "data" / "media_evil"
        evil.mkdir(parents=True)
        (evil / "f.txt").write_text("x")
        monkeypatch.chdir(tmp_path)
        assert delete_media_file(str(evil / "f.txt")) is False

    def test_missing_file_returns_false(self, media_root):
        assert delete_media_file(str(media_root / "ghost.jpg")) is False

    def test_none_safe(self):
        assert delete_media_file(None) is False


class TestCleanupOldMediaFiles:
    @pytest.fixture()
    def media_dir(self, tmp_path):
        d = tmp_path / "media"
        d.mkdir()
        return d

    def test_deletes_files_older_than_cutoff(self, media_dir):
        import time
        now = time.time()
        old_file = media_dir / "old_photo.jpg"
        new_file = media_dir / "new_video.mp4"

        old_file.write_bytes(b"old")
        new_file.write_bytes(b"new")

        # Set old_file mtime to 13 hours ago (13 * 3600)
        os.utime(str(old_file), (now - 13 * 3600, now - 13 * 3600))
        # Set new_file mtime to 1 hour ago
        os.utime(str(new_file), (now - 1 * 3600, now - 1 * 3600))

        deleted = cleanup_old_media_files(str(media_dir), max_age_hours=12)

        assert deleted == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_custom_max_age(self, media_dir):
        import time
        now = time.time()
        f1 = media_dir / "f1.jpg"
        f1.write_bytes(b"1")
        # 5 hours ago
        os.utime(str(f1), (now - 5 * 3600, now - 5 * 3600))

        deleted = cleanup_old_media_files(str(media_dir), max_age_hours=4)
        assert deleted == 1
        assert not f1.exists()

    def test_nonexistent_directory_returns_zero(self):
        assert cleanup_old_media_files("/nonexistent/directory/path/xyz", max_age_hours=12) == 0

    def test_ignores_subdirectories(self, media_dir):
        sub = media_dir / "subdir"
        sub.mkdir()
        deleted = cleanup_old_media_files(str(media_dir), max_age_hours=0)
        assert deleted == 0
        assert sub.exists()

