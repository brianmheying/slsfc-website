#!/usr/bin/env python3
"""Unit tests for the Elementor MCP headers helper, tool guard hook, and the
.mcp.json / .claude/settings.json configuration. Keychain is faked; nothing
touches the network.

Run:
    python3 -m unittest discover -s scripts -p 'test_*.py' -v
"""

import base64
import io
import json
import os
import subprocess
import sys
import unittest
import unittest.mock

sys.dont_write_bytecode = True  # Keep __pycache__ out of the working tree.
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

import elementor_mcp_headers as headers  # noqa: E402
import elementor_mcp_tool_guard as guard  # noqa: E402
import wp_rest  # noqa: E402

FAKE_PASSWORD = "abcd EFGH 1234 ijkl MNOP 5678"
FAKE_TOKEN = base64.b64encode(("claude-api:" + FAKE_PASSWORD).encode()).decode()
GOOD_ENV = {"CLAUDE_CODE_MCP_SERVER_URL": "https://slsfc.org/wp-json/elementor/mcp",
            "CLAUDE_CODE_MCP_SERVER_NAME": "elementor"}

ALLOW = [
    "elementor-get-page-structure",
    "elementor-get-default-styles",
    "elementor-get-widget-schema",
    "elementor-list-widget-schemas",
    "elementor-list-assets",
    "elementor-list-resources",
    "elementor-read-resource",
    "elementor-list-components",
    "elementor-list-posts",
]
ASK = [
    "elementor-build-composition",
    "elementor-manage-elements",
    "elementor-update-page-settings",
    "elementor-create-page",
    "elementor-create-preview-link",
]
DENY = [
    "elementor-publish-document",
    "elementor-manage-default-styles",
    "elementor-manage-component",
    "elementor-manage-global-variable",
    "elementor-manage-classes",
    "elementor-reorder-classes",
]
ALL_20 = ["mcp__elementor__" + n for n in ALLOW + ASK + DENY]


def run_headers(env, password_source=lambda: FAKE_PASSWORD):
    out, err = io.StringIO(), io.StringIO()
    code = headers.main(env=env, password_source=password_source, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def run_guard(raw):
    err = io.StringIO()
    code = guard.main(stdin=io.StringIO(raw), stderr=err)
    return code, err.getvalue()


def hook_input(tool_name, **extra):
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": {}}
    payload.update(extra)
    return json.dumps(payload)


class HeadersHelperTests(unittest.TestCase):

    def test_outputs_only_the_authorization_header_json(self):
        code, out, err = run_headers(GOOD_ENV)
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(json.loads(out), {"Authorization": "Basic " + FAKE_TOKEN})
        self.assertEqual(out, json.dumps({"Authorization": "Basic " + FAKE_TOKEN}))

    def test_refuses_any_other_server_url_without_reading_keychain(self):
        def must_not_run():
            self.fail("credential must not be read for a refused URL")

        bad_urls = [
            None, "",
            "https://slsfc.org/wp-json/elementor/mcp/",
            "http://slsfc.org/wp-json/elementor/mcp",
            "https://www.slsfc.org/wp-json/elementor/mcp",
            "https://slsfc.org/wp-json/mcp/mcp-adapter-default-server",
            "https://slsfc.org/wp-json/elementor/mcp?x=1",
            "https://evil.example/wp-json/elementor/mcp",
            "https://slsfc.org.evil.example/wp-json/elementor/mcp",
            "HTTPS://SLSFC.ORG/wp-json/elementor/mcp",
            " https://slsfc.org/wp-json/elementor/mcp",
        ]
        for url in bad_urls:
            env = {} if url is None else {"CLAUDE_CODE_MCP_SERVER_URL": url}
            code, out, err = run_headers(env, password_source=must_not_run)
            self.assertEqual(code, 1, url)
            self.assertEqual(out, "", url)
            self.assertIn("refusing", err)

    def test_credential_error_emits_nothing_on_stdout(self):
        def missing():
            raise wp_rest.CredentialError("credential not found")

        code, out, err = run_headers(GOOD_ENV, password_source=missing)
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertIn("credential not found", err)

    def test_unexpected_error_is_redacted_without_traceback(self):
        class Boom(Exception):
            pass

        def exploding_dumps(obj, *args, **kwargs):
            raise Boom("leak {} {} {}".format(FAKE_PASSWORD, FAKE_TOKEN, obj))

        with unittest.mock.patch.object(headers.json, "dumps", exploding_dumps):
            code, out, err = run_headers(GOOD_ENV)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        for secret in (FAKE_PASSWORD, FAKE_PASSWORD.replace(" ", ""), FAKE_TOKEN):
            self.assertNotIn(secret, err)
        self.assertIn("[REDACTED]", err)
        self.assertNotIn("Traceback", err)

    def test_password_only_reaches_stdout_inside_the_header(self):
        code, out, err = run_headers(GOOD_ENV)
        self.assertNotIn(FAKE_PASSWORD, out)
        self.assertNotIn(FAKE_PASSWORD, err)

    def test_script_refuses_as_a_subprocess_without_claude_code_env(self):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_MCP_SERVER_URL"}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run([sys.executable, os.path.join(SCRIPTS, "elementor_mcp_headers.py")],
                                capture_output=True, text=True, env=env, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("refusing", result.stderr)


class ToolGuardTests(unittest.TestCase):

    def test_all_20_reviewed_tools_defer_to_permission_rules(self):
        self.assertEqual(len(ALL_20), 20)
        for name in ALL_20:
            code, err = run_guard(hook_input(name))
            self.assertEqual(code, 0, name)
            self.assertEqual(err, "", name)

    def test_unknown_elementor_tools_are_blocked(self):
        for name in [
            "mcp__elementor__elementor-list-site-parts",
            "mcp__elementor__elementor-manage-site-parts",
            "mcp__elementor__elementor-list-posts-v2",
            "mcp__elementor__elementor-LIST-POSTS",
            "mcp__elementor__",
            "mcp__elementor__ elementor-list-posts",
            "mcp__elementor__elementor-list-posts\n",
        ]:
            code, err = run_guard(hook_input(name))
            self.assertEqual(code, 2, repr(name))
            self.assertIn("unreviewed Elementor MCP tool", err)

    def test_malformed_input_fails_closed(self):
        for raw in ["", "not json", "[]", "null", "42", '"mcp__elementor__x"', "{}",
                    json.dumps({"tool_name": None}), json.dumps({"tool_name": 123}),
                    json.dumps({"tool_name": ""}), json.dumps({"tool_name": ["mcp__elementor__x"]}),
                    json.dumps({"tool": "mcp__elementor__elementor-list-posts"})]:
            code, err = run_guard(raw)
            self.assertEqual(code, 2, raw)
            self.assertIn("Blocked", err)

    def test_non_elementor_tools_are_not_affected(self):
        for name in ["Bash", "Read", "Edit", "WebFetch", "mcp__other__tool",
                     "mcp__elementorx__elementor-list-posts", "mcp__claude_ai_elementor__x"]:
            code, err = run_guard(hook_input(name))
            self.assertEqual(code, 0, name)
            self.assertEqual(err, "", name)

    def test_never_writes_a_permission_decision(self):
        # Any stdout (e.g. permissionDecision "allow") could weaken the rules.
        for name in ALL_20 + ["mcp__elementor__unknown", "Bash"]:
            out = io.StringIO()
            original = sys.stdout
            sys.stdout = out
            try:
                run_guard(hook_input(name))
            finally:
                sys.stdout = original
            self.assertEqual(out.getvalue(), "", name)

    def test_unexpected_exception_fails_closed(self):
        class ExplodingStdin:
            def read(self):
                raise RuntimeError("boom")

        err = io.StringIO()
        self.assertEqual(guard.main(stdin=ExplodingStdin(), stderr=err), 2)
        self.assertIn("failed unexpectedly", err.getvalue())

    def test_script_exit_codes_as_a_subprocess(self):
        script = os.path.join(SCRIPTS, "elementor_mcp_tool_guard.py")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        cases = [
            (hook_input("mcp__elementor__elementor-list-posts"), 0),
            (hook_input("mcp__elementor__elementor-new-tool"), 2),
            ("garbage", 2),
            (hook_input("Bash"), 0),
        ]
        for raw, expected in cases:
            result = subprocess.run([sys.executable, script], input=raw, capture_output=True,
                                    text=True, env=env, check=False)
            self.assertEqual(result.returncode, expected, raw)
            self.assertEqual(result.stdout, "", raw)

    def test_guard_contains_no_credential_access(self):
        with open(os.path.join(SCRIPTS, "elementor_mcp_tool_guard.py")) as f:
            source = f.read()
        for forbidden in ("wp_rest", "security", "Keychain(", "get_password", "urllib", "subprocess"):
            self.assertNotIn(forbidden, source)


class ConfigurationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, ".mcp.json")) as f:
            cls.mcp = json.load(f)
        with open(os.path.join(REPO, ".claude", "settings.json")) as f:
            cls.settings = json.load(f)
        cls.permissions = cls.settings["permissions"]

    def elementor_rules(self, kind):
        prefix = "mcp__elementor__"
        return {r for r in self.permissions.get(kind, []) if r.startswith(prefix)}

    def test_mcp_json_defines_only_the_elementor_http_server(self):
        servers = self.mcp["mcpServers"]
        self.assertEqual(set(servers), {"elementor"})
        server = servers["elementor"]
        self.assertEqual(server["type"], "http")
        self.assertEqual(server["url"], headers.EXPECTED_SERVER_URL)
        self.assertEqual(server["headersHelper"], "/usr/bin/python3 scripts/elementor_mcp_headers.py")
        self.assertEqual(set(server), {"type", "url", "headersHelper"})

    def test_mcp_json_contains_no_credential_material(self):
        with open(os.path.join(REPO, ".mcp.json")) as f:
            raw = f.read()
        for marker in ("Authorization", "Basic ", "Bearer", "password", "headers\"", "${", "env"):
            self.assertNotIn(marker, raw)

    def test_permission_classes_match_the_reviewed_lists(self):
        prefix = "mcp__elementor__"
        self.assertEqual(self.elementor_rules("allow"), {prefix + n for n in ALLOW})
        self.assertEqual(self.elementor_rules("ask"), {prefix + n for n in ASK})
        self.assertEqual(self.elementor_rules("deny"), {prefix + n for n in DENY})

    def test_permission_classes_partition_the_guard_allowlist(self):
        allow, ask, deny = (self.elementor_rules(k) for k in ("allow", "ask", "deny"))
        self.assertFalse(allow & ask or allow & deny or ask & deny)
        self.assertEqual(allow | ask | deny, guard.KNOWN_ELEMENTOR_TOOLS)
        self.assertEqual(set(ALL_20), guard.KNOWN_ELEMENTOR_TOOLS)

    def test_no_wildcard_elementor_allow_rule(self):
        for rule in self.permissions.get("allow", []):
            self.assertNotIn("*", rule)

    def test_headers_helper_execution_is_denied(self):
        deny = self.permissions["deny"]
        self.assertIn("Bash(python3 *elementor_mcp_headers*)", deny)
        self.assertIn("Bash(/usr/bin/python3 *elementor_mcp_headers*)", deny)
        self.assertIn("Bash(./scripts/elementor_mcp_headers.py*)", deny)

    def test_existing_rules_are_preserved(self):
        for rule in ["Read(./.env)", "Bash(security find-generic-password:*)", "Bash(git push --force:*)"]:
            self.assertIn(rule, self.permissions["deny"])
        for rule in ["Bash(curl:*)", "Bash(git commit:*)", "Bash(git push:*)", "Bash(gh pr merge:*)"]:
            self.assertIn(rule, self.permissions["ask"])

    def test_only_the_elementor_project_server_is_enabled(self):
        self.assertEqual(self.settings["enabledMcpjsonServers"], ["elementor"])
        self.assertNotIn("enableAllProjectMcpServers", self.settings)

    def test_guard_hook_is_registered_for_elementor_tools(self):
        entries = self.settings["hooks"]["PreToolUse"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["matcher"], "mcp__elementor__.*")
        hook = entries[0]["hooks"][0]
        self.assertEqual(hook["type"], "command")
        self.assertIn("scripts/elementor_mcp_tool_guard.py", hook["command"])
        self.assertTrue(hook["command"].startswith("/usr/bin/python3 "))


if __name__ == "__main__":
    unittest.main()
