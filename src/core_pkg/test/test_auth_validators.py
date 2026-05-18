"""
Tests for the auth validation and password hashing helpers.
"""

import pytest

from core_pkg.dbservices.accessor_dbservice import (
    hash_password,
    validate_description_format,
    validate_login_format,
    validate_name_format,
    validate_password_strength,
    validate_role_name_format,
    verify_password,
)
from core_pkg.exceptions import ValidationError
from core_pkg.systemconstants import DatabaseConstants


# password hashing

def test_hash_password_roundtrip():
    hashed = hash_password("Secret123")
    assert verify_password("Secret123", hashed) is True
    assert verify_password("Secret124", hashed) is False


def test_hash_password_produces_unique_hashes():
    # bcrypt uses a random salt, so hashing the same password twice
    # must never yield the same digest.
    assert hash_password("Secret123") != hash_password("Secret123")


#validate_password_strength

def test_password_strength_accepts_compliant_password():
    # Lower + upper + digit, length within bounds - should not raise.
    validate_password_strength("Secret123")


@pytest.mark.parametrize(
    "password, reason",
    [
        ("Aa1", "too short"),
        ("a" * (DatabaseConstants.MAX_PASSWORD_LENGTH + 1) + "A1", "too long"),
        ("secret123", "no uppercase"),
        ("SECRET123", "no lowercase"),
        ("SecretPwd", "no digit"),
    ],
)
def test_password_strength_rejects_invalid(password, reason):
    with pytest.raises(ValidationError):
        validate_password_strength(password)


#validate_login_format

def test_login_format_accepts_lowercase_alphanumeric():
    validate_login_format("admin01")


@pytest.mark.parametrize(
    "login",
    [
        "abc",                  # too short (min is 5)
        "Admin01",              # uppercase not allowed
        "admin 01",             # space not allowed
        "admin-01",             # dash not allowed
    ],
)
def test_login_format_rejects_invalid(login):
    with pytest.raises(ValidationError):
        validate_login_format(login)


#name / description length checks

def test_name_format_rejects_too_short_and_too_long():
    with pytest.raises(ValidationError):
        validate_name_format("ab")  # below MIN_NAME_LENGTH

    with pytest.raises(ValidationError):
        validate_name_format("x" * (DatabaseConstants.MAX_NAME_LENGTH + 1))


def test_description_format_rejects_overlong():
    # Empty description is fine, only the upper bound is enforced.
    validate_description_format("")
    with pytest.raises(ValidationError):
        validate_description_format("x" * (DatabaseConstants.MAX_DESCRIPTION_LENGTH + 1))


# validate_role_name_format

def test_role_name_is_sanitised_to_lowercase():
    # Trims whitespace and lowercases - keeps role lookups consistent regardless
    # of how the operator typed the name in the UI.
    assert validate_role_name_format("  Admin  ") == "admin"


def test_role_name_rejects_empty_and_invalid_chars():
    with pytest.raises(ValidationError):
        validate_role_name_format("")

    with pytest.raises(ValidationError):
        validate_role_name_format("admin1")  # digits not allowed in role names
