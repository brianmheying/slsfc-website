#!/usr/bin/env python3
"""Fail-closed PreToolUse hook for Elementor MCP tools.

Claude Code runs this before every `mcp__elementor__*` tool call (see the
hook in .claude/settings.json). It reads the hook input JSON from stdin and:

- exits 0 with no output for the 20 reviewed Elementor tools, deferring to
  the allow/ask/deny rules in .claude/settings.json (it never returns
  "allow", which would bypass those rules);
- exits 0 with no output for tools outside the `mcp__elementor__` namespace;
- exits 2 (block) for any other `mcp__elementor__` tool, such as one added
  by a future Elementor update;
- exits 2 (block) if the input is malformed or the tool name cannot be
  determined, or on any unexpected error.

It contains no credentials and does not access Keychain or the network.
"""

import json
import sys

ELEMENTOR_PREFIX = "mcp__elementor__"

# The 20 tools reviewed from the server's tools/list on 2026-10-02. Each is
# also listed in exactly one of permissions.allow, ask or deny.
KNOWN_ELEMENTOR_TOOLS = frozenset(ELEMENTOR_PREFIX + name for name in (
    # Read-only: allowed without prompting.
    "elementor-get-page-structure",
    "elementor-get-default-styles",
    "elementor-get-widget-schema",
    "elementor-list-widget-schemas",
    "elementor-list-assets",
    "elementor-list-resources",
    "elementor-read-resource",
    "elementor-list-components",
    "elementor-list-posts",
    # Mutating: explicit approval required.
    "elementor-build-composition",
    "elementor-manage-elements",
    "elementor-update-page-settings",
    "elementor-create-page",
    "elementor-create-preview-link",
    # Denied.
    "elementor-publish-document",
    "elementor-manage-default-styles",
    "elementor-manage-component",
    "elementor-manage-global-variable",
    "elementor-manage-classes",
    "elementor-reorder-classes",
))

BLOCK = 2
DEFER = 0


def decide(raw_input):
    """Return (exit_code, message) for the raw hook stdin text."""
    try:
        data = json.loads(raw_input)
    except ValueError:
        return BLOCK, "malformed hook input (not JSON)"
    if not isinstance(data, dict):
        return BLOCK, "malformed hook input (not an object)"
    tool_name = data.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        return BLOCK, "cannot determine tool name"
    if not tool_name.startswith(ELEMENTOR_PREFIX):
        return DEFER, None
    if tool_name in KNOWN_ELEMENTOR_TOOLS:
        return DEFER, None
    return BLOCK, "unreviewed Elementor MCP tool: {}".format(tool_name[:200])


def main(stdin=None, stderr=None):
    stdin = stdin or sys.stdin
    stderr = stderr or sys.stderr
    try:
        code, message = decide(stdin.read())
    except BaseException:  # Fail closed on anything unexpected.
        code, message = BLOCK, "tool guard failed unexpectedly"
    if code == BLOCK:
        stderr.write("Blocked by elementor_mcp_tool_guard: {}. "
                     "Only reviewed Elementor MCP tools may run.\n".format(message))
    return code


if __name__ == "__main__":
    try:
        exit_code = main()
    except BaseException:  # Fail closed; sys.exit stays outside the try.
        exit_code = BLOCK
    sys.exit(exit_code)
