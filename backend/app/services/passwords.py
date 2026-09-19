from typing import Optional
import bcrypt

COMMON_PASSWORDS = {
    "12345678",
    "123456789",
    "password",
    "password1",
    "qwerty123",
    "iloveyou",
    "admin123",
    "abcd1234",
    "11111111",
    "1q2w3e4r",
}


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def validate_password(password: str, email: str = "") -> Optional[str]:
    """
    Validate password requirements:
    - 8 to 64 characters
    - At least one letter and one digit
    - Not in a small blocklist of common passwords
    - Not equal to the part of the email before '@'

    Returns None on success, or a clear failure message string.
    """
    if not password:
        return "Password is required."

    if password.lower() in COMMON_PASSWORDS:
        return "This password is too common. Please choose a stronger password."

    if len(password) < 8 or len(password) > 64:
        return "Password must be between 8 and 64 characters long."

    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_letter and has_digit):
        return "Password must contain at least one letter and one digit."

    if email and "@" in email:
        local_part = email.split("@")[0].strip().lower()
        if local_part and password.lower() == local_part:
            return "Password cannot be your email username."

    return None
