# Runbook: WordPress REST API access

How this repository reads data from slsfc.org through the WordPress REST API,
and how the credential is protected.

## Overview

| Item                 | Value                                                  |
|----------------------|--------------------------------------------------------|
| Site                 | `https://slsfc.org` (the only WordPress environment)   |
| API root             | `/wp-json/wp/v2`                                       |
| WordPress user       | `claude-api` (dedicated, least-privilege)              |
| Auth method          | WordPress Application Password over HTTPS (Basic auth) |
| Credential storage   | macOS Keychain generic password                        |
| Keychain service     | `slsfc-wordpress-api`                                  |
| Keychain account     | `claude-api`                                           |
| Helper               | `scripts/wp_rest.py` (read-only, standard library only) |

The service and account names are identifiers, not secrets. The password
itself never appears in this repository.

## Usage

```bash
python3 scripts/wp_rest.py me --context edit           # current user, roles, capabilities
python3 scripts/wp_rest.py pages                        # published pages (compact fields)
python3 scripts/wp_rest.py pages --status any --context edit   # include drafts, private, etc.
python3 scripts/wp_rest.py page 42 --context edit       # one page, all fields, raw content
python3 scripts/wp_rest.py media --media-type image     # media library (compact fields)
python3 scripts/wp_rest.py media-item 99                # one media item, all fields
```

List commands accept `--search`, `--per-page` (1–100, default 100), `--page`,
and `--fields` (comma-separated, or `all`). Run
`python3 scripts/wp_rest.py COMMAND --help` for details.

Output is JSON on stdout:

```json
{
  "request": "GET /wp-json/wp/v2/pages?per_page=100&page=1&_fields=...",
  "pagination": {"total": 7, "total_pages": 1, "page": 1, "per_page": 100},
  "data": [ ... ]
}
```

`pagination` appears only for list commands. Errors are a single line on
stderr.

| Exit code | Meaning                                    |
|-----------|--------------------------------------------|
| 0         | Success                                    |
| 1         | API, HTTP, network, or redirect error      |
| 2         | Invalid command or arguments               |
| 3         | Credential missing or Keychain access denied |

## Capabilities

The helper is **read-only**. It can only send `GET` requests to a fixed
allowlist:

| Command      | Endpoint              |
|--------------|-----------------------|
| `me`         | `/wp/v2/users/me`     |
| `pages`      | `/wp/v2/pages`        |
| `page ID`    | `/wp/v2/pages/ID`     |
| `media`      | `/wp/v2/media`        |
| `media-item ID` | `/wp/v2/media/ID`  |

There is no option to change the HTTP method, send a request body, or
request an arbitrary path or host. Adding write support requires a code
change, a review, and the per-action approval process in `CLAUDE.md`.

## How the credential is protected

- **Retrieval:** the helper runs
  `/usr/bin/security find-generic-password -s slsfc-wordpress-api -a claude-api -w`
  as a subprocess and reads the password from its stdout over a pipe. The
  password is never a command-line argument, never in an environment
  variable, and never written to disk. `security`'s stderr is discarded.
- **Use:** the password is turned into a Basic `Authorization` header in
  memory. The header is attached with `add_unredirected_header`, so urllib
  never copies it onto a redirected request.
- **Destination:** the base URL is hard-coded to `https://slsfc.org`, every
  URL is checked to start with `https://slsfc.org/wp-json/wp/v2/`, and
  IDs must be positive integers.
- **Transport:** TLS certificate and hostname verification use Python's
  defaults and cannot be disabled. Plain HTTP is never used. Proxy
  environment variables are ignored. Every redirect is treated as an error
  and is not followed.
- **Output:** the helper has no debug or verbose mode. Before anything is
  written to stdout or stderr, the password (with and without spaces) and
  its base64 `user:password` forms are replaced with `[REDACTED]`. Errors
  are one-line messages; tracebacks are never shown.
- **Claude Code:** `.claude/settings.json` denies Claude running
  `security find-generic-password` (and related commands) directly. The
  helper calls `security` internally, which that rule does not match. That
  is the intended split: the helper can use the credential, and Claude does
  not see it.

## Security limitations

1. **The Claude Code deny rule is a guardrail, not a boundary.** It matches
   command text. The credential could still be obtained another way (for
   example `python3 -c`, or by editing the helper to print it). The real
   controls are the rules in `CLAUDE.md` and human review of every change to
   `scripts/wp_rest.py`. Review changes to that file with extra care.
2. **Keychain access control.** If the Keychain item lets `security` read it
   without prompting, any process running as this macOS user can read it
   silently. For stricter control, recreate the item so macOS asks for
   confirmation on every read. This adds a click per helper run.
3. **Helper runs do not trigger a Claude Code permission prompt.** The `ask`
   rules match `curl`, `wget`, and similar tools, not
   `python3 scripts/wp_rest.py`. Because the helper is read-only, this is
   currently accepted. Adding an `ask` rule would require changing
   `.claude/settings.json`.
4. **Response data is shown in full.** Whatever `claude-api` can read can
   appear in output, including drafts, raw content, and (with
   `--context edit`) the user's own email address. The Application
   Passwords endpoint is not in the allowlist.
5. **In-memory lifetime.** Python cannot reliably wipe a string from memory.
   Each run is short-lived and exits immediately.
6. **Exact host pinning.** If `slsfc.org` redirects the API (for example to
   `www.slsfc.org`), requests fail instead of following. Any change to the
   pinned host must be deliberate and reviewed.
7. **Old system Python.** macOS ships Python 3.9 with LibreSSL 2.8.3. It
   supports TLS 1.2, which is sufficient, but it is old. The helper avoids
   syntax newer than 3.9.

## Rotating or revoking the Application Password

1. In WordPress admin, sign in as an administrator, open
   **Users → claude-api → Application Passwords**, and revoke the old one.
   Create a new one if access should continue.
2. Replace the Keychain item. Typing `-w` last makes `security` prompt for
   the password, so it never appears in shell history:

   ```bash
   security add-generic-password -U -s slsfc-wordpress-api -a claude-api -w
   ```

3. Verify with `python3 scripts/wp_rest.py me`.

Revoke immediately if the password may have been exposed in output, logs,
a commit, or anywhere outside Keychain.

## Testing

Unit tests fake both Keychain and the network. They check that only `GET`
can be sent, that URLs are pinned, that redirects and proxies are refused,
and that a fake password never appears in output or errors.

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```
