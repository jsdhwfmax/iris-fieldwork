#!/usr/bin/env python3
"""Start an installed IRIS Fieldwork package on this machine's loopback interface.

Run with Python 3.10 or later on the operating system hosting the installed IRIS
package. Existing IRIS_USERNAME/IRIS_PASSWORD or IRIS_BEARER_TOKEN environment
variables are used without changing them. If no credentials are supplied, an
interactive terminal prompts for an existing IRIS account. Nothing is saved.
The gateway runs in the foreground; Ctrl+C closes it. It creates no IRIS users,
starts no background service, and never binds to a public network interface.
"""

import argparse
import getpass
import importlib.util
import os
from pathlib import Path
import sys
import warnings


CREDENTIAL_KEYS = ("IRIS_USERNAME", "IRIS_PASSWORD", "IRIS_BEARER_TOKEN")


def load_backend(root):
    """Load the gateway beside this launcher, including its local dependencies."""
    app = Path(root) / "app"
    source = app / "backend.py"
    if not source.is_file():
        raise ValueError("The installed package is incomplete: app/backend.py is missing.")
    name = "_fieldwork_installed_backend"
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves annotations through sys.modules during module loading.
    previous = sys.modules.get(name)
    sys.modules[name] = module
    sys.path.insert(0, str(app))
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
        raise
    finally:
        sys.path.pop(0)
    return module


def select_credentials(env, validate):
    """Return a private configuration copy; never modify the caller's environment."""
    config = dict(env)
    supplied = {key for key in CREDENTIAL_KEYS if key in config}
    if "IRIS_BEARER_TOKEN" in supplied and supplied != {"IRIS_BEARER_TOKEN"}:
        raise ValueError(
            "Conflicting credentials: set IRIS_BEARER_TOKEN alone, or set both "
            "IRIS_USERNAME and IRIS_PASSWORD without IRIS_BEARER_TOKEN."
        )
    if supplied and "IRIS_BEARER_TOKEN" not in supplied and supplied != {
        "IRIS_USERNAME", "IRIS_PASSWORD"
    }:
        raise ValueError(
            "Incomplete credentials: set both IRIS_USERNAME and IRIS_PASSWORD, "
            "or unset both to use the interactive prompt."
        )
    if supplied:
        try:
            validate(config)
        except ValueError:
            raise ValueError(
                "Invalid credentials: use a nonempty valid IRIS_BEARER_TOKEN, "
                "or a nonempty IRIS_USERNAME/IRIS_PASSWORD pair. "
                "The username cannot contain a colon; control characters are not allowed."
            ) from None
        return config

    if not sys.stdin.isatty():
        raise ValueError(
            "No credentials in this non-interactive session. Set IRIS_USERNAME and "
            "IRIS_PASSWORD, or IRIS_BEARER_TOKEN, before starting the launcher; "
            "alternatively run it in an interactive terminal."
        )
    try:
        config["IRIS_USERNAME"] = input("Existing IRIS username: ")
        # getpass normally warns and echoes when secure terminal input is absent.
        # Refuse that fallback before it can read a password.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            config["IRIS_PASSWORD"] = getpass.getpass("IRIS password (not saved): ")
    except getpass.GetPassWarning:
        raise ValueError(
            "Secure password input is unavailable. Use a terminal with hidden "
            "password input or supply credentials through the environment."
        ) from None
    except EOFError:
        raise ValueError("Credential input ended before completion; the gateway was not started.") from None
    try:
        validate(config)
    except ValueError:
        raise ValueError("The entered IRIS username/password pair is invalid; the gateway was not started.") from None
    return config


def valid_port(value):
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("port must be an integer between 1 and 65535") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be an integer between 1 and 65535")
    return port


def main(argv=None, env=None):
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--iris-url", default=env.get("IRIS_BASE_URL", "http://127.0.0.1:52773"),
        metavar="URL", help="HTTP(S) loopback IRIS origin (default: IRIS_BASE_URL or http://127.0.0.1:52773)",
    )
    parser.add_argument("--port", type=valid_port, default=8766, help="local gateway port (default: 8766)")
    args = parser.parse_args(argv)
    try:
        backend = load_backend(Path(__file__).resolve().parent.parent)
        backend.loopback_target(args.iris_url)
        config = select_credentials(env, backend.credentials)
        config["IRIS_BASE_URL"] = args.iris_url
    except ValueError as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        parser.exit(130, "\nCredential input cancelled; the gateway was not started.\n")

    client = backend.IRISClient(env=config)
    gateway = backend.Gateway(client=client)
    try:
        server = backend.LocalServer(gateway=gateway, port=args.port)
    except OSError:
        parser.exit(1, f"Cannot listen on 127.0.0.1:{args.port}; the port may be in use or unavailable.\n")
    print(f"IRIS Fieldwork gateway: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
