"""Profile-specific handlers for email verification.

This module provides functionality for handling email verification codes
and sending verification emails to users.

#TODO: Add rate limiting for verification attempts
#TODO: Add email validation before sending codes
#TODO: Add cleanup mechanism for expired codes
#! Email verification is critical for security
"""

import random
import typing

from backend.modules.email import Email


class EmailVerifier:
    """Handler for email verification codes and verification process."""

    def __init__(self) -> None:
        """Initialize email verifier with empty code storage."""
        self._codes: typing.Dict[int, typing.Tuple[str, str]] = {}
        self._email_client = Email()

    def generate_code(self, user_id: int, email: str) -> str:
        """Generate and store verification code for user.

        Args:
            user_id: The Discord user ID
            email: The email address to verify

        Returns:
            str: The generated verification code
        """
        code = "".join(str(random.randint(0, 9)) for _ in range(6))
        self._codes[user_id] = (code, email)
        return code

    def verify_code(self, user_id: int, code: str) -> bool:
        """Verify the provided code matches stored code.

        Args:
            user_id: The Discord user ID
            code: The verification code to check

        Returns:
            bool: True if code is valid, False otherwise
        """
        if user_id not in self._codes:
            return False
        stored_code, _ = self._codes[user_id]
        is_valid = code == stored_code
        if is_valid:
            del self._codes[user_id]
        return is_valid

    def send_verification_email(
        self, user_id: int, email: str
    ) -> typing.Dict[str, typing.Any]:
        """Send verification email to user.

        Args:
            user_id: The Discord user ID
            email: The email address to send to

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        code = self.generate_code(user_id, email)
        return self._email_client.send_mail(email, code)
