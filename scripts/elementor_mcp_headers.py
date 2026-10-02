#!/usr/bin/env python3
"""Claude Code `headersHelper` for the Elementor MCP server on slsfc.org.

Claude Code runs this when it connects to the `elementor` server defined in
.mcp.json. It reads the `claude-api` Application Password from macOS
Keychain, builds the Basic Authorization header in memory, and writes only
the JSON headers object to stdout, where Claude Code reads it.

It refuses to emit anything unless CLAUDE_CODE_MCP_SERVER_URL (set by Claude
Code) is exactly the expected server URL. Claude is denied running this
script directly; see .claude/settings.json and
docs/runbooks/wordpress-rest-api.md.

Exit codes: 0 success, 1 refused or unexpected error, 3 credential error.
"""

import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import wp_rest  # noqa: E402

EXPECTED_SERVER_URL = "https://slsfc.org/wp-json/elementor/mcp"
SERVER_URL_ENV = "CLAUDE_CODE_MCP_SERVER_URL"


class RefusedError(wp_rest.HelperError):
    exit_code = 1


def main(env=None, password_source=wp_rest.get_password, stdout=None, stderr=None):
    env = os.environ if env is None else env
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    redact = wp_rest.Redactor()
    try:
        server_url = env.get(SERVER_URL_ENV)
        if server_url != EXPECTED_SERVER_URL:
            raise RefusedError("refusing: {} is not {}".format(SERVER_URL_ENV, EXPECTED_SERVER_URL))
        password = password_source()
        redact.add_password(wp_rest.KEYCHAIN_ACCOUNT, password)
        headers = {"Authorization": wp_rest.build_auth_header(wp_rest.KEYCHAIN_ACCOUNT, password)}
        del password
        # The header is the one intended output; it goes to Claude Code, not redacted.
        stdout.write(json.dumps(headers))
        stdout.flush()
        return 0
    except wp_rest.HelperError as e:
        stderr.write(redact("elementor_mcp_headers: error: {}".format(e)) + "\n")
        return e.exit_code
    except Exception as e:  # Never let a traceback reach any log.
        stderr.write(redact("elementor_mcp_headers: error: unexpected {}: {}".format(type(e).__name__, e)) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
