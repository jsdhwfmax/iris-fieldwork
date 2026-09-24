"""Credential and startup guard tests; no network connection or real credentials."""

from contextlib import redirect_stderr, redirect_stdout
import getpass
import io
from pathlib import Path
import unittest
from unittest import mock

import start_installed as launcher


BACKEND = launcher.load_backend(Path(__file__).resolve().parent.parent)


class CredentialTests(unittest.TestCase):
    def select(self, env):
        return launcher.select_credentials(env, BACKEND.credentials)

    def test_supplied_pair_preserved_without_prompt_or_environment_mutation(self):
        original = {"IRIS_USERNAME": "operator", "IRIS_PASSWORD": " space password ", "OTHER": "kept"}
        before = dict(original)
        with mock.patch("builtins.input") as username, mock.patch.object(launcher.getpass, "getpass") as password:
            result = self.select(original)
        self.assertEqual(result, before)
        self.assertIsNot(result, original)
        self.assertEqual(original, before)
        username.assert_not_called()
        password.assert_not_called()

    def test_supplied_token_preserved_without_prompt(self):
        with mock.patch("builtins.input") as username, mock.patch.object(launcher.getpass, "getpass") as password:
            result = self.select({"IRIS_BEARER_TOKEN": "example-token"})
        self.assertEqual(result, {"IRIS_BEARER_TOKEN": "example-token"})
        username.assert_not_called()
        password.assert_not_called()

    def test_partial_pair_refused_without_prompt(self):
        for supplied in ({"IRIS_USERNAME": "operator"}, {"IRIS_PASSWORD": "secret-example"}):
            with self.subTest(keys=list(supplied)), mock.patch("builtins.input") as username:
                with self.assertRaisesRegex(ValueError, "Incomplete credentials") as caught:
                    self.select(supplied)
                self.assertNotIn("secret-example", str(caught.exception))
                username.assert_not_called()

    def test_conflicting_credentials_refused(self):
        for supplied in (
            {"IRIS_BEARER_TOKEN": "example-token", "IRIS_USERNAME": "operator"},
            {"IRIS_BEARER_TOKEN": "example-token", "IRIS_PASSWORD": "secret-example"},
            {"IRIS_BEARER_TOKEN": "", "IRIS_USERNAME": "operator", "IRIS_PASSWORD": "secret-example"},
        ):
            with self.subTest(keys=list(supplied)), self.assertRaisesRegex(ValueError, "Conflicting credentials"):
                self.select(supplied)

    def test_invalid_supplied_values_refused_without_secret_in_error(self):
        for supplied in (
            {"IRIS_BEARER_TOKEN": ""}, {"IRIS_BEARER_TOKEN": "secret token"},
            {"IRIS_BEARER_TOKEN": "secret\ntoken"}, {"IRIS_BEARER_TOKEN": "秘密"},
            {"IRIS_USERNAME": "bad:user", "IRIS_PASSWORD": "secret-example"},
            {"IRIS_USERNAME": "operator", "IRIS_PASSWORD": ""},
            {"IRIS_USERNAME": "operator", "IRIS_PASSWORD": "secret\nexample"},
        ):
            with self.subTest(keys=list(supplied)), self.assertRaisesRegex(ValueError, "Invalid credentials") as caught:
                self.select(supplied)
            self.assertNotIn("secret", str(caught.exception))

    def test_noninteractive_missing_credentials_refused(self):
        with mock.patch.object(launcher.sys.stdin, "isatty", return_value=False), mock.patch("builtins.input") as username:
            with self.assertRaisesRegex(ValueError, "No credentials in this non-interactive session"):
                self.select({})
            username.assert_not_called()

    def test_interactive_prompt_uses_memory_only(self):
        original = {"IRIS_BASE_URL": "http://127.0.0.1:52773"}
        with mock.patch.object(launcher.sys.stdin, "isatty", return_value=True), \
                mock.patch("builtins.input", return_value="operator") as username, \
                mock.patch.object(launcher.getpass, "getpass", return_value="example-password") as password:
            result = self.select(original)
        self.assertEqual(result["IRIS_USERNAME"], "operator")
        self.assertEqual(result["IRIS_PASSWORD"], "example-password")
        self.assertEqual(original, {"IRIS_BASE_URL": "http://127.0.0.1:52773"})
        username.assert_called_once()
        password.assert_called_once()

    def test_getpass_echo_fallback_refused(self):
        def unavailable(prompt):
            launcher.warnings.warn("Password input may be echoed.", getpass.GetPassWarning)
            self.fail("Password input must not continue after the warning")

        with mock.patch.object(launcher.sys.stdin, "isatty", return_value=True), \
                mock.patch("builtins.input", return_value="operator"), \
                mock.patch.object(launcher.getpass, "getpass", side_effect=unavailable):
            with self.assertRaisesRegex(ValueError, "Secure password input is unavailable"):
                self.select({})

    def test_prompt_eof_and_invalid_input_refused(self):
        with mock.patch.object(launcher.sys.stdin, "isatty", return_value=True), \
                mock.patch("builtins.input", side_effect=EOFError):
            with self.assertRaisesRegex(ValueError, "Credential input ended"):
                self.select({})
        with mock.patch.object(launcher.sys.stdin, "isatty", return_value=True), \
                mock.patch("builtins.input", return_value="bad:user"), \
                mock.patch.object(launcher.getpass, "getpass", return_value="example-password"):
            with self.assertRaisesRegex(ValueError, "entered IRIS username/password pair is invalid"):
                self.select({})


class StartupTests(unittest.TestCase):
    def fake_backend(self):
        backend = mock.Mock()
        backend.loopback_target = BACKEND.loopback_target
        backend.credentials = BACKEND.credentials
        return backend

    def test_passes_private_config_and_port_and_closes_on_interrupt(self):
        env = {"IRIS_USERNAME": "operator", "IRIS_PASSWORD": "example-password", "IRIS_BASE_URL": "http://127.0.0.1:1111"}
        before = dict(env)
        backend = self.fake_backend()
        server = backend.LocalServer.return_value
        server.serve_forever.side_effect = KeyboardInterrupt
        output = io.StringIO()
        with mock.patch.object(launcher, "load_backend", return_value=backend), redirect_stdout(output):
            launcher.main(["--iris-url", "https://localhost:52773", "--port", "8877"], env)
        config = backend.IRISClient.call_args.kwargs["env"]
        self.assertEqual(config, {**before, "IRIS_BASE_URL": "https://localhost:52773"})
        self.assertIsNot(config, env)
        self.assertEqual(env, before)
        backend.Gateway.assert_called_once_with(client=backend.IRISClient.return_value)
        backend.LocalServer.assert_called_once_with(gateway=backend.Gateway.return_value, port=8877)
        server.server_close.assert_called_once()
        self.assertEqual(output.getvalue(), "IRIS Fieldwork gateway: http://127.0.0.1:8877\n")

    def test_defaults_and_close_after_return(self):
        backend = self.fake_backend()
        with mock.patch.object(launcher, "load_backend", return_value=backend), redirect_stdout(io.StringIO()):
            launcher.main([], {"IRIS_BEARER_TOKEN": "example-token"})
        self.assertEqual(backend.IRISClient.call_args.kwargs["env"]["IRIS_BASE_URL"], "http://127.0.0.1:52773")
        self.assertEqual(backend.LocalServer.call_args.kwargs["port"], 8766)
        backend.LocalServer.return_value.server_close.assert_called_once()

    def test_environment_url_used_if_no_override(self):
        backend = self.fake_backend()
        with mock.patch.object(launcher, "load_backend", return_value=backend), redirect_stdout(io.StringIO()):
            launcher.main([], {"IRIS_BEARER_TOKEN": "example-token", "IRIS_BASE_URL": "http://[::1]:52774"})
        self.assertEqual(backend.IRISClient.call_args.kwargs["env"]["IRIS_BASE_URL"], "http://[::1]:52774")

    def test_rejects_unsafe_urls_before_prompt_or_server_creation(self):
        for url in (
            "http://0.0.0.0:52773", "http://192.168.0.1:52773", "http://example.com",
            "file:///etc/passwd", "http://operator:secret-example@127.0.0.1",
            "http://127.0.0.1:0", "http://127.0.0.1:65536", "http://127.0.0.1/private",
            "http://127.0.0.1/?query=value", "http://127.0.0.1/#fragment",
        ):
            backend = self.fake_backend()
            error = io.StringIO()
            with self.subTest(url=url), mock.patch.object(launcher, "load_backend", return_value=backend), \
                    mock.patch("builtins.input") as username, redirect_stderr(error):
                with self.assertRaises(SystemExit) as caught:
                    launcher.main(["--iris-url", url], {})
            self.assertEqual(caught.exception.code, 2)
            self.assertNotIn("secret-example", error.getvalue())
            username.assert_not_called()
            backend.LocalServer.assert_not_called()

    def test_invalid_ports_rejected_before_backend_import(self):
        for port in ("0", "-1", "65536", "1.5", "all"):
            with self.subTest(port=port), mock.patch.object(launcher, "load_backend") as load, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    launcher.main(["--port", port], {})
                self.assertEqual(caught.exception.code, 2)
                load.assert_not_called()

    def test_no_public_host_argument(self):
        with mock.patch.object(launcher, "load_backend") as load, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                launcher.main(["--host", "0.0.0.0"], {})
            load.assert_not_called()

    def test_bind_error_sanitized(self):
        backend = self.fake_backend()
        backend.LocalServer.side_effect = OSError("private detail should not be printed")
        error = io.StringIO()
        with mock.patch.object(launcher, "load_backend", return_value=backend), redirect_stderr(error):
            with self.assertRaises(SystemExit) as caught:
                launcher.main([], {"IRIS_BEARER_TOKEN": "example-token"})
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("Cannot listen on 127.0.0.1:8766", error.getvalue())
        self.assertNotIn("private detail", error.getvalue())
        self.assertNotIn("example-token", error.getvalue())

    def test_incomplete_package_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "app/backend.py is missing"):
            launcher.load_backend(Path(__file__).parent / "does-not-exist")


if __name__ == "__main__":
    unittest.main()
