import unittest
from unittest.mock import patch

from fastapi import HTTPException, Request, Response

from src.auth.dependencies import require_csrf, set_auth_cookies
from src.auth.rate_limit import (
    RateLimitExceeded,
    RateLimitUnavailable,
    _rate_key,
    enforce_rate_limit,
)


def make_request(cookie: str = "", csrf_header: str = "") -> Request:
    headers = []
    if cookie:
        headers.append((b"cookie", cookie.encode("ascii")))
    if csrf_header:
        headers.append((b"x-csrf-token", csrf_header.encode("ascii")))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/auth/logout",
            "raw_path": b"/auth/logout",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
            "root_path": "",
        }
    )


class FakePipeline:
    def __init__(self, count: int) -> None:
        self.count = count

    def incr(self, _key: str) -> None:
        return None

    def expire(self, _key: str, _window: int) -> None:
        return None

    def execute(self) -> tuple[int, int]:
        return self.count, 1


class FakeRedis:
    def __init__(self, count: int, available: bool = True) -> None:
        self.count = count
        self.available = available

    def ping(self) -> bool:
        return self.available

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self.count)

    def ttl(self, _key: str) -> int:
        return 17


class AuthControlsTests(unittest.TestCase):
    def test_csrf_requires_double_submit_token(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            require_csrf(make_request("gridscope_csrf=abc", "wrong"))
        self.assertEqual(raised.exception.status_code, 403)

        require_csrf(make_request("gridscope_csrf=abc", "abc"))

    def test_session_and_csrf_cookies_are_set_with_expected_flags(self) -> None:
        response = Response()
        set_auth_cookies(response, "opaque-session-token")
        cookies = b"\n".join(value for key, value in response.raw_headers if key.lower() == b"set-cookie")

        self.assertIn(b"gridscope_session=opaque-session-token", cookies)
        self.assertIn(b"HttpOnly", cookies)
        self.assertIn(b"gridscope_csrf=", cookies)

    def test_rate_key_does_not_expose_identity(self) -> None:
        key = _rate_key("login-email", "operator@example.com")
        self.assertNotIn("operator@example.com", key)
        self.assertTrue(key.startswith("gridscope:rate:login-email:"))

    def test_rate_limit_raises_after_limit(self) -> None:
        with patch("src.auth.rate_limit.redis_client", FakeRedis(count=4)):
            with self.assertRaises(RateLimitExceeded) as raised:
                enforce_rate_limit("chat-user", "user-id", limit=3, window_seconds=60)
        self.assertEqual(raised.exception.retry_after, 17)

    def test_rate_limit_fails_closed_without_redis(self) -> None:
        with patch("src.auth.rate_limit.redis_client", FakeRedis(count=1, available=False)):
            with self.assertRaises(RateLimitUnavailable):
                enforce_rate_limit("login-ip", "127.0.0.1", limit=3, window_seconds=60)


if __name__ == "__main__":
    unittest.main()
