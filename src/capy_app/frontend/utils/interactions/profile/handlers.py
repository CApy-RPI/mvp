"""Profile-specific handlers."""

import random
from typing import Any
from backend.modules.email import Email

class EmailVerifier:
    """Handler for email verification codes."""
    
    def __init__(self):
        self._codes = {}
        self._email_client = Email()

    def generate_code(self, user_id: int, email: str) -> str:
        """Generate and store verification code for user."""
        code = "".join(str(random.randint(0, 9)) for _ in range(6))
        self._codes[user_id] = (code, email)
        return code

    def verify_code(self, user_id: int, code: str) -> bool:
        """Verify the provided code matches stored code."""
        if user_id not in self._codes:
            return False
        stored_code, _ = self._codes[user_id]
        is_valid = code == stored_code
        if is_valid:
            del self._codes[user_id]
        return is_valid

    def send_verification_email(self, user_id: int, email: str) -> bool:
        """Send verification email to user."""
        code = self.generate_code(user_id, email)
        return self._email_client.send_mail(email, code)


async def validate_profile_data(modal: Any) -> tuple[bool, str]:
    """Validate profile modal input data.
    
    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    if not modal.children[2].value.isdigit():
        return False, "Invalid graduation year!"
    if not modal.children[3].value.isdigit():
        return False, "Invalid student ID!"
    if not modal.children[4].value.endswith("edu"):
        return False, "Invalid School email!"
    return True, ""
