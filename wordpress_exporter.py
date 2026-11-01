"""Read-only WordPress REST API exporter; no HTML transformation."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from typing import Any

import requests

API_URL = "https://cpptake.com/wp-json/wp/v2/posts"
LOG = logging.getLogger(__name__)


def write_json(path: Path, data: Any) -> None:
    """Replace a JSON file atomically, leaving existing data intact on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         suffix=".tmp", delete=False) as stream:
            temporary = stream.name
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def retry_delay(value: str | None, fallback: float) -> float:
    """Honor Retry-After seconds or an HTTP date."""
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                return max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    return fallback


class WordPressClient:
    def __init__(self, session: requests.Session, *, interval: float = 1.0,
                 retries: int = 3, timeout: float = 30.0) -> None:
        self.session = session
        self.interval = interval
        self.retries = retries
        self.timeout = timeout
        self.last_request: float | None = None

    def page(self, number: int) -> tuple[list[dict[str, Any]], int, int]:
        for attempt in range(self.retries + 1):
            if self.last_request is not None:
                time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            response = None
            try:
                response = self.session.get(API_URL, params={
                    "per_page": 100, "page": number, "status": "publish",
                    "orderby": "id", "order": "asc",
                }, timeout=self.timeout)
                response.raise_for_status()
                posts = response.json()
                total = int(response.headers["X-WP-Total"])
                pages = int(response.headers["X-WP-TotalPages"])
                if (not isinstance(posts, list) or total < 0 or pages < 0
                        or pages != (total + 99) // 100):
                    raise ValueError("Invalid posts or pagination metadata")
                return posts, total, pages
            except (requests.RequestException, ValueError, KeyError) as error:
                retryable = (not isinstance(error, requests.HTTPError)
                             or response is None or response.status_code == 429
                             or 500 <= response.status_code <= 599)
                LOG.warning("page=%s attempt=%s/%s: %s", number, attempt + 1,
                            self.retries + 1, error)
                if not retryable or attempt == self.retries:
                    raise RuntimeError(f"page {number}: {error}") from error
                delay = retry_delay(response.headers.get("Retry-After") if response is not None else None,
                                    min(60.0, 2.0 ** attempt))
                time.sleep(max(self.interval, delay))
            finally:
                if response is not None:
                    response.close()
        raise AssertionError("unreachable")


def validate_post(post: Any) -> dict[str, Any]:
    if not isinstance(post, dict) or type(post.get("id")) is not int or post["id"] <= 0:
        raise ValueError("Invalid article ID")
    for key in ("title", "content", "excerpt"):
        if not isinstance(post.get(key), dict) or not isinstance(post[key].get("rendered"), str):
            raise ValueError(f"Missing {key}.rendered for ID {post['id']}")
    for key in ("date", "date_gmt", "modified", "slug", "link"):
        if not isinstance(post.get(key), str):
            raise ValueError(f"Missing {key} for ID {post['id']}")
    for key in ("categories", "tags"):
        if not isinstance(post.get(key), list) or any(type(v) is not int for v in post[key]):
            raise ValueError(f"Invalid {key} for ID {post['id']}")
    if type(post.get("featured_media")) is not int or post.get("status") != "publish":
        raise ValueError(f"Invalid media or unpublished article: {post['id']}")
    if post["content"].get("protected"):
        raise ValueError(f"Password-protected content unavailable for ID {post['id']}")
    return post


def export_posts(client: WordPressClient, output: Path, limit: int | None = None) -> dict[str, Any]:
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    started = datetime.now(timezone.utc).isoformat()
    output.mkdir(parents=True, exist_ok=True)
    (output / "raw").mkdir(exist_ok=True)
    index: dict[int, dict[str, Any]] = {}
    seen: set[int] = set()
    errors: list[str] = []
    warnings: list[str] = []
    failed_pages: list[int] = []
    failed_posts = 0
    duplicates = 0
    total: int | None = None
    pages: int | None = None
    page = 1
    while pages is None or page <= pages:
        try:
            posts, current_total, current_pages = client.page(page)
        except RuntimeError as error:
            LOG.error("%s", error)
            errors.append(str(error))
            failed_pages.append(page)
            if pages is None:
                break
            page += 1
            continue
        if total is None:
            total, pages = current_total, current_pages
        elif (total, pages) != (current_total, current_pages):
            message = f"API totals changed on page {page}: {current_total} posts, {current_pages} pages"
            warnings.append(message)
            LOG.warning(message)
        for post in posts:
            if limit is not None and len(index) >= limit:
                break
            try:
                post = validate_post(post)
                post_id = post["id"]
                if post_id in seen:
                    duplicates += 1
                    continue
                seen.add(post_id)
                write_json(output / "raw" / f"{post_id}.json", post)
                index[post_id] = {"id": post_id, "title": post["title"]["rendered"],
                                  **{key: post[key] for key in ("link", "date", "date_gmt", "modified", "slug", "status")},
                                  "raw_file": f"raw/{post_id}.json"}
            except (ValueError, OSError) as error:
                failed_posts += 1
                errors.append(str(error))
                LOG.error("Article export failed: %s", error)
        LOG.info("page=%s/%s saved=%s API total=%s", page, pages, len(index), total)
        if limit is not None and len(index) >= limit:
            break
        page += 1
    expected = min(total, limit) if total is not None and limit is not None else total
    if total is not None and len(index) != total:
        message = f"Saved {len(index)} articles vs API total {total}"
        if limit is not None:
            message += f" (limit={limit}; expected for this run={expected})"
        warnings.append(message)
        LOG.warning(message)
    complete = total is not None and len(index) == expected and not errors
    summary = {
        "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "api_url": API_URL, "limit": limit, "total_articles": len(index),
        "success_count": len(index), "failure_count": failed_posts + len(failed_pages),
        "failed_article_count": failed_posts, "failed_pages": failed_pages,
        "api_total": total, "api_total_pages": pages, "expected_count": expected,
        "duplicate_count": duplicates, "complete": complete,
        "full_export": complete and len(index) == total,
        "errors": errors, "warnings": warnings,
    }
    write_json(output / "index.json", list(index.values()))
    write_json(output / "export_summary.json", summary)
    return summary


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=positive_int)
    parser.add_argument("--output", type=Path, default=Path("wordpress_export"))
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--retries", type=int, default=3, help="retries after the initial request")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if not (args.interval >= 0 and args.retries >= 0 and args.timeout > 0):
        parser.error("interval/retries must be nonnegative and timeout must be positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        with requests.Session() as session:
            session.headers.update({"User-Agent": "cpptake-wordpress-exporter/1.0", "Accept": "application/json"})
            session.trust_env = False  # Do not load implicit .netrc credentials.
            summary = export_posts(WordPressClient(session, interval=args.interval,
                                   retries=args.retries, timeout=args.timeout), args.output, args.limit)
    except OSError:
        LOG.exception("Could not save export")
        return 1
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
