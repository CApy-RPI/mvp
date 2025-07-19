import sys
import types

# Provide dummy backend email module to avoid external dependency
backend = types.ModuleType("backend")
modules = types.ModuleType("modules")
email_module = types.ModuleType("email")


class DummyEmail:
    def send_mail(self, *_, **__):  # pragma: no cover - simple dummy
        return True


email_module.Email = DummyEmail
modules.email = email_module
backend.modules = modules
sys.modules.setdefault("backend", backend)
sys.modules.setdefault("backend.modules", modules)
sys.modules.setdefault("backend.modules.email", email_module)

from capy_app.frontend.cogs.features.profile_handlers import EmailVerifier


def test_generate_code_length_and_digits() -> None:
    verifier = EmailVerifier()
    code = verifier.generate_code(1, "test@example.com")
    assert len(code) == 6
    assert code.isdigit()


def test_verify_code_success_and_cleanup() -> None:
    verifier = EmailVerifier()
    user_id = 2
    code = verifier.generate_code(user_id, "other@example.com")
    assert verifier.verify_code(user_id, code)
    assert not verifier.verify_code(user_id, code)


def test_verify_code_failure() -> None:
    verifier = EmailVerifier()
    user_id = 3
    code = verifier.generate_code(user_id, "third@example.com")
    wrong_code = "000000" if code != "000000" else "111111"
    assert not verifier.verify_code(user_id, wrong_code)
