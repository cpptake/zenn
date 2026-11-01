import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from wordpress_exporter import WordPressClient, export_posts, retry_delay, write_json


def post(number):
    return dict(id=number, title={"rendered": "日本語の記事"},
                content={"rendered": "<p>本文</p>" * 10000, "protected": False},
                excerpt={"rendered": "抜粋"}, date="2026-01-01T00:00:00",
                date_gmt="2025-12-31T15:00:00", modified="2026-01-01T00:00:00",
                slug=f"article-{number}", link=f"https://example.com/{number}",
                categories=[1], tags=[], featured_media=0, status="publish", extra={"keep": True})


def response(posts=None, total=1, pages=1, status=200):
    result = Mock(status_code=status, headers={"X-WP-Total": str(total), "X-WP-TotalPages": str(pages)})
    result.json.return_value = posts if posts is not None else [post(1)]
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}")
    return result


class ExportTests(unittest.TestCase):
    def test_limit_raw_roundtrip_and_rerun(self):
        client = Mock()
        originals = [post(i) for i in range(1, 6)]
        client.page.return_value = (originals, 5, 1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for _ in range(2):
                summary = export_posts(client, root, 3)
                self.assertTrue(summary["complete"])
                self.assertFalse(summary["full_export"])
                self.assertEqual(summary["failure_count"], 0)
                self.assertEqual(len(list((root / "raw").glob("*.json"))), 3)
                for original in originals[:3]:
                    raw = (root / "raw" / f"{original['id']}.json").read_text(encoding="utf-8")
                    self.assertIn("日本語", raw)
                    self.assertEqual(json.loads(raw), original)
                self.assertEqual(len(json.loads((root / "index.json").read_text())), 3)

    def test_all_pages_duplicates_and_mismatch(self):
        client = Mock()
        client.page.side_effect = [([post(1), post(2)], 101, 2), ([post(2), post(3)], 101, 2)]
        with tempfile.TemporaryDirectory() as directory:
            summary = export_posts(client, Path(directory))
        self.assertEqual(client.page.call_args_list[1].args, (2,))
        self.assertEqual(summary["success_count"], 3)
        self.assertEqual(summary["duplicate_count"], 1)
        self.assertFalse(summary["complete"])
        self.assertTrue(summary["warnings"])

    def test_page_failure_continues_and_records_error(self):
        client = Mock()
        client.page.side_effect = [([post(1)], 201, 3), RuntimeError("timeout"), ([post(3)], 201, 3)]
        with tempfile.TemporaryDirectory() as directory:
            summary = export_posts(client, Path(directory))
        self.assertEqual(summary["failed_pages"], [2])
        self.assertEqual(summary["failure_count"], 1)
        self.assertEqual(summary["success_count"], 2)

    def test_invalid_article_and_first_page_failure(self):
        client = Mock()
        client.page.return_value = ([{"id": 1}], 1, 1)
        with tempfile.TemporaryDirectory() as directory:
            summary = export_posts(client, Path(directory))
            self.assertEqual(summary["failed_article_count"], 1)
            client.page.side_effect = RuntimeError("connection failed")
            summary = export_posts(client, Path(directory))
            self.assertIsNone(summary["api_total"])
            self.assertFalse(summary["complete"])

    def test_empty_export(self):
        client = Mock()
        client.page.return_value = ([], 0, 0)
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(export_posts(client, Path(directory))["full_export"])

    def test_atomic_save_preserves_old_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            write_json(path, {"old": True})
            with patch("wordpress_exporter.os.replace", side_effect=OSError("disk error")):
                with self.assertRaises(OSError):
                    write_json(path, {"new": True})
            self.assertEqual(json.loads(path.read_text()), {"old": True})
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    @patch("wordpress_exporter.time.sleep")
    def test_retry_timeout_429_5xx(self, sleep):
        session = Mock()
        limited = response(status=429)
        limited.headers["Retry-After"] = "3"
        session.get.side_effect = [requests.Timeout("timeout"), limited, response(status=503), response()]
        client = WordPressClient(session, interval=0, retries=3)
        self.assertEqual(client.page(1)[1:], (1, 1))
        self.assertEqual(session.get.call_count, 4)
        self.assertEqual(session.get.call_args.kwargs["params"]["per_page"], 100)
        self.assertEqual(session.get.call_args.kwargs["params"]["status"], "publish")
        self.assertIn(unittest.mock.call(3.0), sleep.call_args_list)

    @patch("wordpress_exporter.time.sleep")
    def test_retry_exhaustion_and_nonretryable_error(self, sleep):
        session = Mock()
        session.get.side_effect = requests.ConnectionError("offline")
        with self.assertRaises(RuntimeError):
            WordPressClient(session, interval=0, retries=2).page(1)
        self.assertEqual(session.get.call_count, 3)
        session.reset_mock(side_effect=True)
        session.get.return_value = response(status=404)
        with self.assertRaises(RuntimeError):
            WordPressClient(session).page(1)
        self.assertEqual(session.get.call_count, 1)

    @patch("wordpress_exporter.time.sleep")
    def test_invalid_json_and_headers(self, sleep):
        session = Mock()
        bad = response()
        bad.json.side_effect = ValueError("not JSON")
        missing = response()
        missing.headers = {}
        session.get.side_effect = [bad, missing, response()]
        self.assertEqual(WordPressClient(session, interval=0).page(1)[1], 1)
        self.assertEqual(retry_delay("invalid", 2), 2)


if __name__ == "__main__":
    unittest.main()
