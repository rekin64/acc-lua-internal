from types import SimpleNamespace

from telethon import errors

from vabot.login_flow import interactive_login


class FakeClient:
    """Client Telethon simulé : code « 12345 », mot de passe 2FA facultatif."""

    def __init__(self, password=None):
        self.password = password
        self.authorized = False
        self.connected = False
        self.calls = []

    def is_connected(self):
        return self.connected

    async def connect(self):
        self.connected = True

    async def is_user_authorized(self):
        return self.authorized

    async def send_code_request(self, phone):
        if not phone.startswith("+"):
            raise errors.PhoneNumberInvalidError(request=None)
        return SimpleNamespace(phone_code_hash="hash")

    async def sign_in(self, phone=None, code=None, *, password=None, phone_code_hash=None):
        self.calls.append((code, password))
        if password is not None:
            if password != self.password:
                raise errors.PasswordHashInvalidError(request=None)
            self.authorized = True
            return
        if code != "12345":
            raise errors.PhoneCodeInvalidError(request=None)
        if self.password:
            raise errors.SessionPasswordNeededError(request=None)
        self.authorized = True


def scripted(*answers):
    queue = list(answers)
    return lambda prompt: queue.pop(0)


async def test_login_with_code_retry():
    client = FakeClient()
    messages = []
    ok = await interactive_login(
        client, "+33600000000", ask_secret=scripted("00000", "1 2 3 4 5"), say=messages.append
    )
    assert ok and client.authorized
    assert any("incorrect" in m for m in messages)
    # Le code n'est jamais réaffiché
    assert not any("12345" in m for m in messages)


async def test_login_with_two_factor_password():
    client = FakeClient(password="secret")
    messages = []
    ok = await interactive_login(
        client, "+33600000000", ask_secret=scripted("12345", "faux", "secret"), say=messages.append
    )
    assert ok
    assert client.calls[-1] == (None, "secret")
    assert not any("secret" in m for m in messages)


async def test_invalid_phone_and_too_many_attempts():
    assert not await interactive_login(FakeClient(), "0600", say=lambda m: None)
    assert not await interactive_login(
        FakeClient(), "+33600000000", ask_secret=scripted("1", "2", "3"), say=lambda m: None
    )


async def test_already_authorized_does_nothing():
    client = FakeClient()
    client.authorized = True
    assert await interactive_login(client, ask=lambda p: 1 / 0)
