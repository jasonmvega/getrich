"""Credential helper for the classroom Alpaca scripts.

The helper checks several common environment-variable names used in older
student projects. If credentials are not available in the environment, it
prompts at runtime. The secret is never written to a file.
"""
import os
from getpass import getpass

KEY_NAMES = (
    "APCA_API_KEY_ID",
    "ALPACA_API_KEY",
    "ALPACA_KEY",
    "API_KEY",
    "KEY_ID",
)
SECRET_NAMES = (
    "APCA_API_SECRET_KEY",
    "ALPACA_SECRET_KEY",
    "ALPACA_SECRET",
    "SECRET_KEY",
)


def _first_environment_value(names):
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip(), name
    return None, None


def get_alpaca_credentials():
    key, key_name = _first_environment_value(KEY_NAMES)
    secret, secret_name = _first_environment_value(SECRET_NAMES)

    if key and secret:
        print(f"Using Alpaca credentials from environment variables {key_name} and {secret_name}.")
        return key, secret

    print("Alpaca credentials were not found in the usual environment-variable names.")
    print("You may paste your PAPER account credentials for this run. They will not be saved.")
    if not key:
        key = input("Alpaca API key: ").strip()
    if not secret:
        secret = getpass("Alpaca secret key: ").strip()

    if not key or not secret:
        raise RuntimeError("Alpaca API key and secret are required.")
    return key, secret
