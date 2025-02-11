import typing
import logging
from mailjet_rest import Client

from config import settings


class EmailError(Exception):
    """Base exception for email-related errors."""

    pass


class EmailSendError(EmailError):
    """Exception raised when email sending fails."""

    pass


class Email:
    logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        """Initialize the Mailer with Mailjet client."""
        self.mailjet = Client(
            auth=(settings.MAILJET_API_KEY, settings.MAILJET_API_SECRET), version="v3.1"
        )

    def send_mail(self, to_email: str, verification_code: str) -> typing.Any:
        """
        Send a verification email.

        Args:
            to_email: The recipient's email address.
            verification_code: The verification code to be sent.

        Returns:
            typing.Any: The response from Mailjet API if successful.

        Raises:
            EmailSendError: If email sending fails.
        """
        data = {
            "Messages": [
                {
                    "From": {
                        "Email": settings.MAILJET_EMAIL_ADDRESS,
                        "Name": "CApy Verification",
                    },
                    "To": [
                        {
                            "Email": to_email,
                        }
                    ],
                    "Subject": "Your CApy Verification Code",
                    "TextPart": f"Your Capy Verification Code is {verification_code}",
                }
            ]
        }

        result = self.mailjet.send.create(data=data)
        if result.status_code == 200:
            return result.json()
        err =  EmailSendError(
            f"Failed to send email: {result.status_code} - {result.json()}"
        )
        self.logger.exception(err, stack_info=True)
        raise err
