import typing
from unittest.mock import Mock, patch
import pytest
from src.capy_app.backend.modules.email import Email, EmailError, EmailSendError
from src.capy_app.config import settings


@pytest.fixture
def email_client() -> Email:
    return Email()


@pytest.fixture
def expected_data() -> typing.Dict[str, typing.Any]:
    return {
        "Messages": [
            {
                "From": {
                    "Email": settings.EMAIL_ADDRESS,
                    "Name": "CApy Verification",
                },
                "To": [
                    {
                        "Email": "test@example.com",
                    }
                ],
                "Subject": "Your CApy Verification Code",
                "TextPart": "Your Capy Verification Code is 123456",
            }
        ]
    }


def test_email_error_inheritance() -> None:
    assert issubclass(EmailSendError, EmailError)
    assert issubclass(EmailError, Exception)


def test_email_init() -> None:
    with patch("src.capy_app.backend.modules.email.Client") as mock_client:
        Email()
        mock_client.assert_called_once_with(
            auth=(settings.MAILJET_API_KEY, settings.MAILJET_API_SECRET), version="v3.1"
        )


def test_send_mail_success(
    email_client: Email, expected_data: typing.Dict[str, typing.Any]
) -> None:
    mock_response = Mock(status_code=200)
    mock_response.json.return_value = {"status": "success"}

    with patch.object(
        email_client.mailjet, "send", Mock(**{"create.return_value": mock_response})
    ):
        result = email_client.send_mail("test@example.com", "123456")

        email_client.mailjet.send.create.assert_called_once_with(data=expected_data)
        assert result == {"status": "success"}
        mock_response.json.assert_called_once()


def test_send_mail_http_error(email_client: Email) -> None:
    mock_response = Mock(status_code=400)
    mock_response.json.return_value = {"error": "bad request"}

    with patch.object(
        email_client.mailjet, "send", Mock(**{"create.return_value": mock_response})
    ):
        with pytest.raises(EmailSendError) as exc_info:
            email_client.send_mail("test@example.com", "123456")

        assert "Failed to send email: 400" in str(exc_info.value)
        assert "bad request" in str(exc_info.value)


def test_send_mail_exception_with_chaining(email_client: Email) -> None:
    original_error = Exception("API Error")

    with patch.object(
        email_client.mailjet, "send", Mock(**{"create.side_effect": original_error})
    ):
        with pytest.raises(EmailSendError) as exc_info:
            email_client.send_mail("test@example.com", "123456")

        assert "Error sending email: API Error" in str(exc_info.value)
        assert exc_info.value.__cause__ == original_error


def test_error_messages() -> None:
    error = EmailError("test error")
    assert str(error) == "test error"

    send_error = EmailSendError("send error")
    assert str(send_error) == "send error"
