import typing
from mailjet_rest import Client

from config import MAILJET_API_KEY, MAILJET_API_SECRET, EMAIL_ADDRESS


class EmailError(Exception):
    """Base exception for email-related errors."""

    pass


class EmailSendError(EmailError):
    """Exception raised when email sending fails."""

    pass


class Email:
    mailjet: Client

    def __init__(self) -> None:
        """Initialize the Mailer with Mailjet client."""
        self.mailjet = Client(
            auth=(MAILJET_API_KEY, MAILJET_API_SECRET), version="v3.1"
        )

    def send_mail(self, to_email: str, verification_code: str) -> typing.Any:
        """
        Send a verification email.

        Args:
            to_email: The recipient's email address.
            verification_code: The verification code to be sent.

        Returns:
            typing.Dict[str, typing.Any]: The response from Mailjet API if successful.

        Raises:
            EmailSendError: If email sending fails.
        """
        data = {
            "Messages": [
                {
                    "From": {
                        "Email": EMAIL_ADDRESS,
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

        try:
            result = self.mailjet.send.create(data=data)
            if result.status_code == 200:
                return result.json()
            raise EmailSendError(
                f"Failed to send email: {result.status_code} - {result.json()}"
            )
        except Exception as e:
            raise EmailSendError(f"Error sending email: {str(e)}") from e
