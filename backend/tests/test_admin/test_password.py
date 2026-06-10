from app.admin.auth.password import hash_password, verify_password


def test_hash_and_verify():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True


def test_wrong_password():
    hashed = hash_password("secret123")
    assert verify_password("wrong", hashed) is False


def test_different_hashes():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
    assert verify_password("same", h1) is True
    assert verify_password("same", h2) is True
