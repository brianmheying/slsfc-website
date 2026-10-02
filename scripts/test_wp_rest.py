#!/usr/bin/env python3
"""Unit tests for scripts/wp_rest.py. Keychain and network are faked.

Run:
    python3 -m unittest discover -s scripts -p 'test_*.py' -v
"""

import base64
import io
import json
import os
import ssl
import sys
import unittest
import unittest.mock
import urllib.error
import urllib.request

sys.dont_write_bytecode = True  # Keep __pycache__ out of the working tree.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import wp_rest  # noqa: E402

FAKE_PASSWORD = "abcd EFGH 1234 ijkl MNOP 5678"
FAKE_PASSWORD_NOSPACE = FAKE_PASSWORD.replace(" ", "")
FAKE_B64 = base64.b64encode(("claude-api:" + FAKE_PASSWORD).encode()).decode()


def secret_forms():
    return [FAKE_PASSWORD, FAKE_PASSWORD_NOSPACE, FAKE_B64]


class FakeResponse:
    def __init__(self, body, headers=None):
        self._body = body
        self.headers = headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    """Records requests and returns a canned response or raises an error."""

    def __init__(self, body=b"{}", headers=None, error=None):
        self.requests = []
        self.body = body
        self.headers = headers or {"Content-Type": "application/json"}
        self.error = error

    def open(self, req, timeout=None):
        self.requests.append(req)
        if self.error is not None:
            raise self.error
        return FakeResponse(self.body, self.headers)


def run(argv, opener=None, password_source=lambda: FAKE_PASSWORD):
    out, err = io.StringIO(), io.StringIO()
    code = wp_rest.main(argv, password_source=password_source,
                        opener=opener or FakeOpener(), stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


ALL_COMMANDS = [
    ["me"],
    ["me", "--context", "edit"],
    ["pages"],
    ["pages", "--status", "any", "--context", "edit", "--search", "home"],
    ["page", "12"],
    ["media"],
    ["media", "--media-type", "image"],
    ["media-item", "34"],
]


class RequestShapeTests(unittest.TestCase):

    def test_every_command_sends_get_only(self):
        for argv in ALL_COMMANDS:
            opener = FakeOpener()
            code, _, err = run(argv, opener)
            self.assertEqual(code, 0, (argv, err))
            self.assertEqual(len(opener.requests), 1)
            self.assertEqual(opener.requests[0].get_method(), "GET", argv)
            self.assertIsNone(opener.requests[0].data, argv)

    def test_every_url_is_pinned_to_https_slsfc_api(self):
        for argv in ALL_COMMANDS:
            opener = FakeOpener()
            run(argv, opener)
            url = opener.requests[0].full_url
            self.assertTrue(url.startswith("https://slsfc.org/wp-json/wp/v2/"), url)

    def test_expected_endpoints(self):
        cases = {
            ("me",): "https://slsfc.org/wp-json/wp/v2/users/me",
            ("page", "12"): "https://slsfc.org/wp-json/wp/v2/pages/12",
            ("media-item", "34"): "https://slsfc.org/wp-json/wp/v2/media/34",
        }
        for argv, expected in cases.items():
            opener = FakeOpener()
            run(list(argv), opener)
            self.assertEqual(opener.requests[0].full_url, expected)

    def test_list_defaults_use_compact_fields(self):
        opener = FakeOpener()
        run(["pages"], opener)
        self.assertIn("_fields=id%2Ctitle%2Cstatus", opener.requests[0].full_url)
        self.assertIn("per_page=100", opener.requests[0].full_url)

    def test_fields_all_removes_field_filter(self):
        opener = FakeOpener()
        run(["pages", "--fields", "all"], opener)
        self.assertNotIn("_fields", opener.requests[0].full_url)

    def test_auth_header_is_unredirected(self):
        opener = FakeOpener()
        run(["me"], opener)
        req = opener.requests[0]
        self.assertIn("Authorization", req.unredirected_hdrs)
        self.assertNotIn("Authorization", req.headers)
        self.assertEqual(req.unredirected_hdrs["Authorization"], "Basic " + FAKE_B64)

    def test_build_url_rejects_paths_outside_api(self):
        with self.assertRaises(wp_rest.ApiError):
            wp_rest.build_url("@evil.example/x", {})


class ArgumentTests(unittest.TestCase):

    def assertUsageError(self, argv):
        with self.assertRaises(SystemExit) as ctx, \
                unittest.mock.patch("sys.stderr", io.StringIO()):
            wp_rest.main(argv, password_source=self.fail_if_called, opener=FakeOpener())
        self.assertEqual(ctx.exception.code, 2)

    def fail_if_called(self):
        self.fail("credential must not be read for invalid input")

    def test_rejects_method_and_data_options(self):
        self.assertUsageError(["pages", "--method", "POST"])
        self.assertUsageError(["pages", "--data", "{}"])

    def test_rejects_non_allowlisted_commands(self):
        for command in ["users", "settings", "plugins", "application-passwords", "delete", "post"]:
            self.assertUsageError([command])

    def test_rejects_path_injection_in_ids(self):
        for bad in ["12/../users", "../settings", "12?x=1", "-1", "0", "abc", "1.5"]:
            self.assertUsageError(["page", bad])

    def test_rejects_invalid_status_and_per_page(self):
        self.assertUsageError(["pages", "--status", "publish,bogus"])
        self.assertUsageError(["pages", "--per-page", "101"])

    def test_no_raw_url_or_host_option(self):
        self.assertUsageError(["pages", "--url", "https://evil.example"])
        self.assertUsageError(["pages", "--host", "evil.example"])


class TransportTests(unittest.TestCase):

    def test_redirects_are_refused(self):
        handler = wp_rest.RefuseRedirects()
        req = urllib.request.Request("https://slsfc.org/wp-json/wp/v2/users/me")
        with self.assertRaises(wp_rest.ApiError):
            handler.redirect_request(req, None, 301, "Moved", {}, "https://evil.example/")

    def test_opener_disables_proxies_and_verifies_tls(self):
        opener = wp_rest.build_opener()
        proxies = [h for h in opener.handlers if isinstance(h, urllib.request.ProxyHandler)]
        self.assertTrue(all(h.proxies == {} for h in proxies))
        https = [h for h in opener.handlers if isinstance(h, urllib.request.HTTPSHandler)]
        self.assertEqual(len(https), 1)
        context = https[0]._context
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertTrue(any(isinstance(h, wp_rest.RefuseRedirects) for h in opener.handlers))

    def test_redirect_surfaced_as_clean_error(self):
        opener = FakeOpener(error=wp_rest.ApiError("refusing to follow HTTP 301 redirect to https://www.slsfc.org/"))
        code, out, err = run(["me"], opener)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("refusing to follow HTTP 301", err)


class SecretLeakTests(unittest.TestCase):

    def assertNoSecret(self, text):
        for form in secret_forms():
            self.assertNotIn(form, text)

    def test_secret_echoed_in_success_body_is_redacted(self):
        body = ('{"note": "%s %s %s"}' % tuple(secret_forms())).encode()
        code, out, err = run(["me"], FakeOpener(body=body))
        self.assertEqual(code, 0)
        self.assertNoSecret(out + err)
        self.assertIn(wp_rest.REDACTED, out)

    def test_secret_echoed_in_http_error_is_redacted(self):
        body = ('{"code": "x", "message": "bad %s"}' % FAKE_PASSWORD).encode()
        error = urllib.error.HTTPError("https://slsfc.org/wp-json/wp/v2/users/me",
                                       401, "Unauthorized", {}, io.BytesIO(body))
        code, out, err = run(["me"], FakeOpener(error=error))
        self.assertEqual(code, 1)
        self.assertNoSecret(out + err)
        self.assertIn("HTTP 401", err)

    def test_unexpected_exception_has_no_traceback_or_secret(self):
        error = RuntimeError("boom " + FAKE_B64)
        code, out, err = run(["me"], FakeOpener(error=error))
        self.assertEqual(code, 1)
        self.assertNoSecret(out + err)
        self.assertNotIn("Traceback", err)
        self.assertIn("unexpected RuntimeError", err)

    def test_auth_header_never_in_output(self):
        code, out, err = run(["pages"], FakeOpener(body=b"[]", headers={"X-WP-Total": "0"}))
        self.assertEqual(code, 0)
        self.assertNotIn("Authorization", out + err)
        self.assertNoSecret(out + err)


class CredentialTests(unittest.TestCase):

    class Result:
        def __init__(self, returncode, stdout="", stderr=""):
            self.returncode, self.stdout, self.stderr = returncode, stdout, stderr

    def test_keychain_call_args_never_contain_secret(self):
        calls = []

        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return self.Result(0, FAKE_PASSWORD + "\n")

        self.assertEqual(wp_rest.get_password(runner), FAKE_PASSWORD)
        args, kwargs = calls[0]
        self.assertEqual(args, ["/usr/bin/security", "find-generic-password",
                                "-s", "slsfc-wordpress-api", "-a", "claude-api", "-w"])
        self.assertTrue(kwargs.get("capture_output"))
        self.assertNotIn("env", kwargs)

    def test_keychain_failure_is_clean_and_hides_security_stderr(self):
        def runner(args, **kwargs):
            return self.Result(44, "", "security: SecKeychainSearchCopyNext: secret detail")

        with self.assertRaises(wp_rest.CredentialError) as ctx:
            wp_rest.get_password(runner)
        self.assertNotIn("secret detail", str(ctx.exception))
        self.assertIn("service=slsfc-wordpress-api", str(ctx.exception))

    def test_empty_keychain_item_is_rejected(self):
        with self.assertRaises(wp_rest.CredentialError):
            wp_rest.get_password(lambda args, **kw: self.Result(0, "\n"))

    def test_credential_error_exit_code(self):
        def missing():
            raise wp_rest.CredentialError("credential not found")

        opener = FakeOpener()
        code, out, err = run(["me"], opener, password_source=missing)
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertIn("credential not found", err)
        self.assertEqual(opener.requests, [], "no request may be sent without a credential")


class OutputTests(unittest.TestCase):

    def test_list_output_includes_pagination(self):
        opener = FakeOpener(body=b'[{"id": 1}]',
                            headers={"X-WP-Total": "1", "X-WP-TotalPages": "1"})
        code, out, _ = run(["pages"], opener)
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["pagination"]["total"], 1)
        self.assertEqual(result["pagination"]["total_pages"], 1)
        self.assertEqual(result["data"], [{"id": 1}])
        self.assertTrue(result["request"].startswith("GET /wp-json/wp/v2/pages?"))

    def test_non_json_response_is_an_error(self):
        opener = FakeOpener(body=b"<html>challenge</html>", headers={"Content-Type": "text/html"})
        code, out, err = run(["me"], opener)
        self.assertEqual(code, 1)
        self.assertIn("not JSON", err)


if __name__ == "__main__":
    unittest.main()
