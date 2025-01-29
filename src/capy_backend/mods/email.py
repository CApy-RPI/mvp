import os

from mailjet_rest import Client
from dotenv import load_dotenv

load_dotenv()

class Mailer:
    def __init__(self):
        self.API_KEY = os.environ.get("MAILJET_API_KEY")
        self.API_SECRET = os.environ.get("MAILJET_API_SECRET")
        self.mailjet = Client(auth=(self.API_KEY, self.API_SECRET), version='v3.1')
        self.Address = os.environ.get("EMAIL_ADDRESS")

    def send_mail(self, to_email, verification_code):
        data = {
            'Messages': [
                {
                    'From': {
                        "Email": self.Address,
                        "Name": "CApy Verification",
                    },
                    'To': [
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
        # if (result.status_code != 200):
        # 	idk do something