from mailjet_rest import Client
from typing import Optional

from config import MAILJET_API_KEY, MAILJET_API_SECRET, EMAIL_ADDRESS


class Email:
    def __init__(self):
        """
        Initialize the Mailer with Mailjet client.
        """
        self.mailjet = Client(
            auth=(MAILJET_API_KEY, MAILJET_API_SECRET), version="v3.1"
        )

    def send_mail(self, to_email: str, verification_code: str) -> Optional[dict]:
        """
        Send a verification email.

        Args:
            to_email (str): The recipient's email address.
            verification_code (str): The verification code to be sent.

        Returns:
            Optional[dict]: The response from Mailjet API if successful, None otherwise.
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

        result = self.mailjet.send.create(data=data)
        if result.status_code == 200:
            return result.json()
        else:
            print(f"Failed to send email: {result.status_code} - {result.json()}")
            return None
