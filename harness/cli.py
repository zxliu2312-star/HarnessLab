from __future__ import annotations

import argparse
import getpass
import sys

_SERVICE = "coding-agent-harness"
_USERNAME = "openai_api_key"


def _keyring_set(key: str) -> None:
    import keyring
    keyring.set_password(_SERVICE, _USERNAME, key)


def _keyring_get() -> str | None:
    try:
        import keyring
        return keyring.get_password(_SERVICE, _USERNAME)
    except Exception:
        return None


def _keyring_delete() -> bool:
    try:
        import keyring
        keyring.delete_password(_SERVICE, _USERNAME)
        return True
    except Exception:
        return False


def cmd_setup(args: argparse.Namespace) -> None:
    key = getpass.getpass("Enter your OpenAI API key (input hidden): ").strip()
    if not key:
        print("No key entered. Aborted.", file=sys.stderr)
        sys.exit(1)
    try:
        _keyring_set(key)
        print(f"Key stored in system keychain (prefix: {key[:4]}***)")
    except Exception as e:
        print(f"keyring unavailable ({e}). Falling back to .env file.")
        _write_env_file(key)


def cmd_key_status(args: argparse.Namespace) -> None:
    import os
    key = _keyring_get()
    if key:
        print(f"keychain: {key[:4]}{'*' * (len(key) - 4)}")
        return
    env_key = os.environ.get("OPENAI_API_KEY", "")
    if env_key:
        print(f"env var:  {env_key[:4]}{'*' * (len(env_key) - 4)}")
        return
    print("No API key found. Run: python -m harness.cli setup")


def cmd_key_clear(args: argparse.Namespace) -> None:
    deleted = _keyring_delete()
    if deleted:
        print("Key removed from system keychain.")
    else:
        print("No key found in keychain (or keyring unavailable).")


def _write_env_file(key: str) -> None:
    env_path = ".env"
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"OPENAI_API_KEY={key}\n")
        print(f"Key written to {env_path}. Make sure it is in .gitignore!")
    except OSError as e:
        print(f"Could not write .env: {e}", file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m harness.cli",
        description="Manage API credentials for Coding Agent Harness",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="Store API key in system keychain")
    sub.add_parser("key-status", help="Show stored key status (first 4 chars only)")
    sub.add_parser("key-clear", help="Remove API key from system keychain")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch = {
        "setup": cmd_setup,
        "key-status": cmd_key_status,
        "key-clear": cmd_key_clear,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
