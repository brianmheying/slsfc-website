#!/usr/bin/env python3
"""Read-only WordPress REST helper for slsfc.org.

Retrieves the `claude-api` Application Password from macOS Keychain at
runtime and uses it only to authenticate HTTPS GET requests to
https://slsfc.org. The credential is never printed, logged, written to
disk, placed in an environment variable, or passed as a command-line
argument.

Standard library only; compatible with the macOS system Python (3.9+).

Usage:
    python3 scripts/wp_rest.py me [--context edit]
    python3 scripts/wp_rest.py pages [--status any] [--search Q] [--per-page N] [--page N] [--fields F] [--context edit]
    python3 scripts/wp_rest.py page ID [--context edit] [--fields F]
    python3 scripts/wp_rest.py media [--media-type image] [--search Q] [--per-page N] [--page N] [--fields F]
    python3 scripts/wp_rest.py media-item ID [--context edit] [--fields F]

Exit codes: 0 success, 1 API/network error, 2 usage error, 3 credential error.

See docs/runbooks/wordpress-rest-api.md.
"""

import argparse
import base64
import json
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

# --- Fixed configuration (not overridable from the command line) ----------

HOST = "slsfc.org"
BASE_URL = "https://" + HOST
API_ROOT = "/wp-json/wp/v2"
KEYCHAIN_SERVICE = "slsfc-wordpress-api"
KEYCHAIN_ACCOUNT = "claude-api"  # Also the WordPress username.
SECURITY_BIN = "/usr/bin/security"
HTTP_METHOD = "GET"  # The only method this helper can send.
TIMEOUT_SECONDS = 30
USER_AGENT = "slsfc-wp-rest/1.0 (read-only)"
REDACTED = "[REDACTED]"

DEFAULT_FIELDS = {
    "pages": "id,title,status,slug,link,parent,menu_order,modified",
    "media": "id,title,media_type,mime_type,source_url,post,modified",
}
PAGE_STATUSES = {"publish", "future", "draft", "pending", "private", "trash", "any"}
MEDIA_TYPES = ("image", "video", "text", "application", "audio")
CONTEXTS = ("view", "edit", "embed")


# --- Errors ----------------------------------------------------------------

class HelperError(Exception):
    exit_code = 1


class ApiError(HelperError):
    exit_code = 1


class CredentialError(HelperError):
    exit_code = 3


# --- Credential handling ---------------------------------------------------

def get_password(runner=subprocess.run):
    """Return the Application Password from macOS Keychain.

    The password travels over a pipe from `security` into this process.
    Only the service and account names appear in the subprocess arguments.
    `security`'s own stderr is discarded rather than echoed.
    """
    args = [
        SECURITY_BIN, "find-generic-password",
        "-s", KEYCHAIN_SERVICE,
        "-a", KEYCHAIN_ACCOUNT,
        "-w",
    ]
    try:
        result = runner(args, capture_output=True, text=True, check=False)
    except OSError:
        raise CredentialError("could not run " + SECURITY_BIN) from None
    if result.returncode != 0:
        raise CredentialError(
            "credential not found or access denied in Keychain "
            "(service={}, account={})".format(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
        )
    password = result.stdout.rstrip("\r\n")
    if not password:
        raise CredentialError("Keychain item is empty "
                              "(service={}, account={})".format(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT))
    return password


def build_auth_header(username, password):
    token = base64.b64encode("{}:{}".format(username, password).encode("utf-8")).decode("ascii")
    return "Basic " + token


class Redactor:
    """Replaces any known secret form with [REDACTED] before text is emitted."""

    def __init__(self):
        self._secrets = []

    def add_password(self, username, password):
        forms = {password, password.replace(" ", "")}
        for form in list(forms):
            forms.add(build_auth_header(username, form)[len("Basic "):])
        # Longest first so a full form is replaced before any substring of it.
        self._secrets = sorted((f for f in forms if len(f) >= 8), key=len, reverse=True)

    def __call__(self, text):
        for secret in self._secrets:
            text = text.replace(secret, REDACTED)
        return text


# --- HTTP ------------------------------------------------------------------

class RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Treat every redirect as an error so credentials never follow one."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ApiError("refusing to follow HTTP {} redirect to {}".format(code, newurl))


def build_opener():
    context = ssl.create_default_context()  # Certificate + hostname verification on.
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),  # Ignore *_PROXY environment variables.
        RefuseRedirects(),
        urllib.request.HTTPSHandler(context=context),
    )


def build_url(path, params):
    url = BASE_URL + API_ROOT + path
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    if query:
        url += "?" + query
    if not url.startswith(BASE_URL + API_ROOT + "/"):
        raise ApiError("refusing to request a URL outside " + BASE_URL + API_ROOT)
    return url


def make_request(url, auth_header):
    req = urllib.request.Request(url, method=HTTP_METHOD)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", USER_AGENT)
    # Unredirected: urllib never copies this header onto a redirected request.
    req.add_unredirected_header("Authorization", auth_header)
    return req


def _describe_error_body(body):
    try:
        data = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return "non-JSON error response"
    if isinstance(data, dict):
        return "{}: {}".format(data.get("code", "unknown"), data.get("message", ""))
    return "unexpected error response"


def fetch(opener, url, auth_header):
    """Perform one GET request. Returns (parsed_json, headers)."""
    req = make_request(url, auth_header)
    if req.get_method() != "GET":
        raise ApiError("refusing non-GET request")
    try:
        with opener.open(req, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read()
            headers = resp.headers
    except urllib.error.HTTPError as e:
        body = e.read() if e.fp is not None else b""
        raise ApiError("HTTP {} {}".format(e.code, _describe_error_body(body))) from None
    except urllib.error.URLError as e:
        raise ApiError("connection failed: {}".format(e.reason)) from None
    except OSError as e:
        raise ApiError("connection failed: {}".format(type(e).__name__)) from None
    try:
        return json.loads(body.decode("utf-8")), headers
    except ValueError:
        content_type = headers.get("Content-Type", "unknown") if headers else "unknown"
        raise ApiError("response was not JSON (Content-Type: {})".format(content_type)) from None


# --- Commands (the complete allowlist) -------------------------------------

def plan_request(args):
    """Map parsed arguments to (path, params, is_list). Only GET paths exist here."""
    fields = None if args.fields == "all" else args.fields
    if args.command == "me":
        return "/users/me", {"context": args.context}, False
    if args.command == "pages":
        return "/pages", {
            "status": args.status,
            "search": args.search,
            "per_page": args.per_page,
            "page": args.page,
            "context": args.context,
            "_fields": fields if args.fields is not None else DEFAULT_FIELDS["pages"],
        }, True
    if args.command == "page":
        return "/pages/{}".format(args.id), {"context": args.context, "_fields": fields}, False
    if args.command == "media":
        return "/media", {
            "media_type": args.media_type,
            "search": args.search,
            "per_page": args.per_page,
            "page": args.page,
            "context": args.context,
            "_fields": fields if args.fields is not None else DEFAULT_FIELDS["media"],
        }, True
    if args.command == "media-item":
        return "/media/{}".format(args.id), {"context": args.context, "_fields": fields}, False
    raise HelperError("unknown command")


# --- CLI -------------------------------------------------------------------

def _positive_int(value):
    if not value.isdigit() or int(value) < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return int(value)


def _per_page(value):
    number = _positive_int(value)
    if number > 100:
        raise argparse.ArgumentTypeError("must be between 1 and 100")
    return number


def _status(value):
    parts = value.split(",")
    if not parts or any(p not in PAGE_STATUSES for p in parts):
        raise argparse.ArgumentTypeError("must be one or more of: " + ", ".join(sorted(PAGE_STATUSES)))
    return value


def build_parser():
    parser = argparse.ArgumentParser(
        prog="wp_rest.py",
        description="Read-only WordPress REST helper for " + BASE_URL + " (GET only).",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    def add_common(p, fields_help):
        p.add_argument("--context", choices=CONTEXTS, help="REST context (edit shows raw/draft data)")
        p.add_argument("--fields", help=fields_help + " Use 'all' for every field.")

    me = sub.add_parser("me", help="the authenticated user")
    me.add_argument("--context", choices=CONTEXTS, help="use 'edit' to include roles and capabilities")

    pages = sub.add_parser("pages", help="list pages")
    add_common(pages, "Comma-separated fields. Default: " + DEFAULT_FIELDS["pages"] + ".")
    pages.add_argument("--status", type=_status, help="e.g. publish, draft, any (default: WordPress default)")
    pages.add_argument("--search")
    pages.add_argument("--per-page", type=_per_page, default=100)
    pages.add_argument("--page", type=_positive_int, default=1)

    page = sub.add_parser("page", help="a single page by ID")
    page.add_argument("id", type=_positive_int)
    add_common(page, "Comma-separated fields. Default: all.")

    media = sub.add_parser("media", help="list media items")
    add_common(media, "Comma-separated fields. Default: " + DEFAULT_FIELDS["media"] + ".")
    media.add_argument("--media-type", choices=MEDIA_TYPES)
    media.add_argument("--search")
    media.add_argument("--per-page", type=_per_page, default=100)
    media.add_argument("--page", type=_positive_int, default=1)

    item = sub.add_parser("media-item", help="a single media item by ID")
    item.add_argument("id", type=_positive_int)
    add_common(item, "Comma-separated fields. Default: all.")

    return parser


def main(argv=None, password_source=get_password, opener=None, stdout=None, stderr=None):
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    args = build_parser().parse_args(argv)  # Usage errors exit with code 2.
    if not hasattr(args, "fields"):
        args.fields = None

    redact = Redactor()
    try:
        path, params, is_list = plan_request(args)
        url = build_url(path, params)
        password = password_source()
        redact.add_password(KEYCHAIN_ACCOUNT, password)
        auth_header = build_auth_header(KEYCHAIN_ACCOUNT, password)
        del password
        data, headers = fetch(opener or build_opener(), url, auth_header)

        result = {"request": "GET " + url[len(BASE_URL):]}
        if is_list:
            result["pagination"] = {
                "total": _int_or_none(headers.get("X-WP-Total")),
                "total_pages": _int_or_none(headers.get("X-WP-TotalPages")),
                "page": params.get("page"),
                "per_page": params.get("per_page"),
            }
        result["data"] = data
        stdout.write(redact(json.dumps(result, indent=2, ensure_ascii=False)) + "\n")
        return 0
    except HelperError as e:
        stderr.write(redact("error: {}".format(e)) + "\n")
        return e.exit_code
    except KeyboardInterrupt:
        stderr.write("error: interrupted\n")
        return 130
    except Exception as e:  # Never let a traceback reach the terminal.
        stderr.write(redact("error: unexpected {}: {}".format(type(e).__name__, e)) + "\n")
        return 1


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    sys.exit(main())
