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
