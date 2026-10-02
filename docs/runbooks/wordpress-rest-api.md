# Runbook: WordPress and Elementor access

How Claude Code reaches slsfc.org, and how the credential is protected.
There are two interfaces, and both use the same `claude-api` credential:

| Interface | Purpose | Can write? |
|-----------|---------|------------|
| REST helper (`scripts/wp_rest.py`) | Read-only inspection and audit of WordPress and Elementor data | No. It can only send `GET` |
| Elementor MCP (`.mcp.json` server `elementor`) | Elementor's native interface for reading and editing Elementor documents | Only through tools that require your approval each time; see [Elementor MCP](#elementor-mcp) |

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
| REST helper          | `scripts/wp_rest.py` (read-only, standard library only) |
| Elementor MCP server | `https://slsfc.org/wp-json/elementor/mcp`              |
| MCP headers helper   | `scripts/elementor_mcp_headers.py`                     |
| MCP tool guard hook  | `scripts/elementor_mcp_tool_guard.py`                  |

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
python3 scripts/wp_rest.py library-item 7 --context edit  # Elementor library item (Kit 7)
python3 scripts/wp_rest.py globals                      # Elementor global colors and typography
python3 scripts/wp_rest.py global-classes               # Elementor atomic global classes
python3 scripts/wp_rest.py variables                    # Elementor atomic variables
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
| `library-item ID` | `/wp/v2/elementor_library/ID` |
| `globals`    | `/elementor/v1/globals` |
| `global-classes` | `/elementor/v1/global-classes?context=frontend` |
| `variables`  | `/elementor/v1/variables/list` |

`ALLOWED_PATHS` in the helper lists these routes as exact patterns, and
every request path must fully match one of them. No other `elementor/v1`
route, sub-route, or namespace can be reached. There is no option to change
the HTTP method, send a request body or headers, add query parameters, or
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
  path must fully match an entry in `ALLOWED_PATHS`, and IDs must be
  positive integers.
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

## Elementor MCP

Elementor 4.3.3 includes an MCP server, built on the WordPress MCP Adapter,
at `https://slsfc.org/wp-json/elementor/mcp` (HTTP transport). It
authenticates with any valid WordPress Application Password, so it uses the
existing `claude-api` credential. Do not use Elementor's "Generate & Copy
configuration" button: it creates an extra Application Password for the
logged-in administrator and returns a plaintext configuration.

### Configuration

- `.mcp.json` defines one project server, `elementor`, of type `http`, with a
  `headersHelper` and no credentials or credential-derived values.
- `.claude/settings.json` enables only that server
  (`enabledMcpjsonServers: ["elementor"]`), assigns every reviewed tool to
  an allow, ask or deny rule, and registers the tool guard hook.

### Keychain credential flow

1. When Claude Code connects to the `elementor` server (at session start or
   on reconnect), it runs the `headersHelper` command
   `/usr/bin/python3 scripts/elementor_mcp_headers.py` from the project
   directory, with `CLAUDE_CODE_MCP_SERVER_URL` set.
2. The helper refuses, and outputs nothing, unless that variable is exactly
   `https://slsfc.org/wp-json/elementor/mcp`.
3. It reads the password from Keychain with the same code as the REST helper
   (`wp_rest.get_password()`), builds `Authorization: Basic …` in memory, and
   writes only `{"Authorization": "Basic …"}` to stdout, which Claude Code
   reads. Errors go to stderr, redacted.
4. Claude Code sends the header to the MCP server over HTTPS. The header is
   not stored in `.mcp.json`, `~/.claude.json`, the environment or shell
   history.

Claude is denied running the headers helper directly (the
`Bash(... elementor_mcp_headers ...)` deny rules). Claude Code runs
`headersHelper` itself, not through Claude's shell tool, so those rules do
not affect it.

### Tool permission classes

| Class | Tools | Behavior |
|-------|-------|----------|
| **Allow** | `elementor-get-page-structure`, `elementor-get-default-styles`, `elementor-get-widget-schema`, `elementor-list-widget-schemas`, `elementor-list-assets`, `elementor-list-resources`, `elementor-read-resource`, `elementor-list-components`, `elementor-list-posts` | Read-only; runs without prompting |
| **Ask** | `elementor-build-composition`, `elementor-manage-elements`, `elementor-update-page-settings`, `elementor-create-page`, `elementor-create-preview-link` | Changes content or creates an anonymous preview URL; prompts for approval every time, including in auto mode |
| **Deny** | `elementor-publish-document`, `elementor-manage-default-styles`, `elementor-manage-component`, `elementor-manage-global-variable`, `elementor-manage-classes`, `elementor-reorder-classes` | Never runs; the tool is removed from Claude's context |

Permission rules use the full names (`mcp__elementor__<tool>`). Claude Code
checks deny first, then ask, then allow, in every permission mode.

**Publishing stays denied.** `elementor-publish-document` is denied, and
`elementor-manage-component` (which can publish components immediately) is
denied too. Content created through MCP stays a draft until a person
publishes it in WordPress.

### Unknown tools fail closed

`scripts/elementor_mcp_tool_guard.py` is a `PreToolUse` hook for every
`mcp__elementor__.*` tool call. It:

- does nothing (exit 0, no output) for the 20 reviewed tools, leaving the
  decision to the allow/ask/deny rules. It never returns `allow`, which
  would bypass them;
- blocks (exit 2) any other `mcp__elementor__` tool, such as one added by a
  future Elementor update;
- blocks if the hook input is malformed or the tool name cannot be
  determined, and on any unexpected error.

When Elementor adds or changes tools, review the new tool list, then update
`KNOWN_ELEMENTOR_TOOLS` and the permission rules together. The tests check
that the two match.

### Server-side boundary

`claude-api` is a WordPress **Editor**, and WordPress checks each ability's
permission when it is called. That check is the real server-side boundary:

- The MCP server lists all tools to every user. Being listed does not mean
  `claude-api` can run a tool.
- Tools that need `manage_options` or `elementor_global_classes_update_class`
  (global variables, default styles, components, global classes) are refused
  by WordPress for an Editor, as well as denied in Claude Code.
- Editors *can* publish and create anonymous preview links, so for
  `elementor-publish-document` and `elementor-create-preview-link` the Claude
  Code deny and ask rules are the only barrier.

### MCP limitations

1. **The headers-helper deny rules are a guardrail.** They match command
   text. Claude could still obtain the header another way (for example
   `python3 -c` importing the helper). Review changes to
   `scripts/elementor_mcp_headers.py`, `scripts/wp_rest.py`, `.mcp.json`
   and `.claude/settings.json` with extra care.
2. **Hook failure modes.** Claude Code treats a `PreToolUse` hook that times
   out (10 seconds here), or exits with a code other than 0 or 2, as
   "no decision" and continues with the normal permission rules. The guard
   catches all errors and exits 2, but if `/usr/bin/python3` itself could not
   start, the guard would not block. The allow/ask/deny rules still apply.
3. **Unreviewed tools in other permission modes.** If the guard did not run,
   an unlisted tool would prompt in Manual mode and go to the auto mode
   classifier in auto mode.
4. **Project trust.** Hooks in `.claude/settings.json` and project
   `headersHelper` commands run only in a trusted workspace. This project is
   trusted.
5. **Claude Code logs.** The Claude Code documentation does not say whether
   debug or MCP logs ever record `headersHelper` output. Check this once
   before routine use.

## Rotating or revoking the Application Password

1. In WordPress admin, sign in as an administrator, open
   **Users → claude-api → Application Passwords**, and revoke the old one.
   Create a new one if access should continue.
2. Replace the Keychain item. Typing `-w` last makes `security` prompt for
   the password, so it never appears in shell history:

   ```bash
   security add-generic-password -U -s slsfc-wordpress-api -a claude-api -w
   ```

3. Verify with `python3 scripts/wp_rest.py me`. The Elementor MCP connection
   picks up the new password the next time Claude Code connects.

Revoke immediately if the password may have been exposed in output, logs,
a commit, or anywhere outside Keychain.

## Testing

Unit tests fake both Keychain and the network.

- `scripts/test_wp_rest.py` checks that the REST helper can only send `GET`,
  that every path is on the allowlist, that redirects and proxies are refused,
  and that a fake password never appears in output or errors.
- `scripts/test_elementor_mcp.py` checks:
  - the headers helper outputs only the header JSON, refuses any other server
    URL before reading Keychain, and redacts errors;
  - the tool guard defers for all 20 reviewed tools, blocks unknown Elementor
    tools and malformed input, ignores other tools, and never writes a
    permission decision;
  - `.mcp.json` holds no credentials, and the allow/ask/deny rules exactly
    cover the guard's 20 tools.

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```
