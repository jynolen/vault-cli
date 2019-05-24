import pytest

from vault_cli import client, exceptions


@pytest.mark.parametrize(
    "backend, mock",
    [
        ("requests", "vault_cli.requests.RequestsVaultClient"),
        ("hvac", "vault_cli.hvac.HVACVaultClient"),
    ],
)
def test_get_client_from_kwargs(mocker, backend, mock):
    c = mocker.patch(mock)
    client.get_client_from_kwargs(backend, a=1)

    c.assert_called_with(a=1)


def test_get_client_from_kwargs_custom(mocker):
    backend = mocker.MagicMock()
    client.get_client_from_kwargs(backend, a=1)

    backend.assert_called_with(a=1)


def test_get_client_from_kwargs_bad(mocker):
    with pytest.raises(ValueError):
        client.get_client_from_kwargs("nope")


def test_get_client(mocker):
    mocker.patch(
        "vault_cli.settings.build_config_from_files", return_value={"url": "yay"}
    )
    backend = mocker.Mock()

    c = client.get_client(backend=backend, yo=True)

    backend.assert_called_with(yo=True, url="yay")
    assert backend.return_value == c


@pytest.mark.parametrize(
    "error, expected",
    [
        ("oh no", '''status=404 error="oh no"'''),
        ("""{"errors": ["damn", "gosh"]}""", '''status=404 error="damn\ngosh"'''),
    ],
)
def test_vault_api_exception(error, expected):
    exc_str = str(exceptions.VaultAPIException(404, error))

    assert exc_str == expected


@pytest.mark.parametrize(
    "func, args",
    [
        ("_init_session", "url verify"),
        ("_authenticate_token", "token"),
        ("_authenticate_certificate", "certificate"),
        ("_authenticate_userpass", "username password"),
        ("list_secrets", "path"),
        ("get_secret", "path"),
        ("delete_secret", "path"),
        ("_set_secret", "path value"),
    ],
)
def test_vault_client_base_not_implemented(func, args):
    class TestVaultClient(client.VaultClientBase):
        def __init__(self):
            pass

    c = TestVaultClient()

    with pytest.raises(NotImplementedError):
        getattr(c, func)(**{name: None for name in args.split()})


def test_vault_client_base_call_init_session():
    called_with = {}

    class TestVaultClient(client.VaultClientBase):
        def _init_session(self, **kwargs):
            called_with.update(kwargs)

        def _authenticate_token(self, *args, **kwargs):
            pass

    TestVaultClient(
        verify=False,
        url="yay",
        token="go",
        base_path=None,
        certificate=None,
        username=None,
        password=None,
        ca_bundle=None,
    )

    assert called_with == {"verify": False, "url": "yay"}


@pytest.mark.parametrize(
    "test_kwargs, expected",
    [
        ({"token": "yay"}, ["token", "yay"]),
        ({"username": "a", "password": "b"}, ["userpass", "a", "b"]),
        ({"certificate": "cert"}, ["certificate", "cert"]),
    ],
)
def test_vault_client_base_authenticate(test_kwargs, expected):
    auth_params = []

    class TestVaultClient(client.VaultClientBase):
        def _init_session(self, **kwargs):
            pass

        def _authenticate_token(self, token):
            auth_params.extend(["token", token])

        def _authenticate_certificate(self, certificate):
            auth_params.extend(["certificate", certificate])

        def _authenticate_userpass(self, username, password):
            auth_params.extend(["userpass", username, password])

    kwargs = {"token": None, "username": None, "password": None, "certificate": None}
    kwargs.update(test_kwargs)
    TestVaultClient(verify=False, url=None, base_path=None, ca_bundle=None, **kwargs)

    assert auth_params == expected


def test_vault_client_base_username_without_password():
    class TestVaultClient(client.VaultClientBase):
        def _init_session(self, **kwargs):
            pass

    with pytest.raises(ValueError):
        TestVaultClient(
            username="yay",
            password=None,
            verify=False,
            url="yay",
            token=None,
            base_path=None,
            certificate=None,
            ca_bundle=None,
        )


def test_vault_client_base_no_auth():
    class TestVaultClient(client.VaultClientBase):
        def _init_session(self, **kwargs):
            pass

    with pytest.raises(ValueError):
        TestVaultClient(
            username=None,
            password=None,
            verify=False,
            url="yay",
            token=None,
            base_path=None,
            certificate=None,
            ca_bundle=None,
        )


def test_vault_client_set_ca_bundle(mocker):

    session_kwargs = {}

    class TestVaultClient(client.VaultClientBase):
        def _init_session(self, **kwargs):
            session_kwargs.update(kwargs)

    with pytest.raises(ValueError):
        TestVaultClient(
            verify=True,
            ca_bundle="yay",
            username=None,
            password=None,
            url=None,
            token=None,
            base_path=None,
            certificate=None,
        )

    assert session_kwargs["verify"] == "yay"


def test_vault_client_set_ca_bundle_no_bundle():

    session_kwargs = {}

    class TestVaultClient(client.VaultClientBase):
        def _init_session(self, **kwargs):
            session_kwargs.update(kwargs)

    with pytest.raises(ValueError):
        TestVaultClient(
            verify=True,
            ca_bundle=None,
            username=None,
            password=None,
            url=None,
            token=None,
            base_path=None,
            certificate=None,
        )

    assert session_kwargs["verify"] is True


def test_vault_client_set_ca_bundle_no_verify():

    session_kwargs = {}

    class TestVaultClient(client.VaultClientBase):
        def _init_session(self, **kwargs):
            session_kwargs.update(kwargs)

    with pytest.raises(ValueError):
        TestVaultClient(
            verify=False,
            ca_bundle="yay",
            username=None,
            password=None,
            url=None,
            token=None,
            base_path=None,
            certificate=None,
        )

    assert session_kwargs["verify"] is False


def test_vault_client_base_browse_recursive_secrets():
    class TestVaultClient(client.VaultClientBase):
        def __init__(self):
            pass

        def list_secrets(self, path):
            return {"": ["a", "b/"], "b": ["c"]}[path]

        def get_secret(self, path):
            return {"a": "secret-a", "b/c": "secret-bc"}[path]

    result = list(TestVaultClient()._browse_recursive_secrets(""))

    assert result == ["a", "b/c"]


def test_vault_client_base_browse_recursive_secrets_single_secret():
    class TestVaultClient(client.VaultClientBase):
        def __init__(self):
            pass

        def list_secrets(self, path):
            return {"a": []}[path]

    result = list(TestVaultClient()._browse_recursive_secrets("a"))

    assert result == ["a"]


@pytest.mark.parametrize("method_name", ["get_all", "get_all_secrets"])
def test_vault_client_base_get_all_secrets(method_name):
    class TestVaultClient(client.VaultClientBase):
        def __init__(self):
            pass

        def list_secrets(self, path):
            return {"": ["a/", "b"], "a": ["c"]}[path]

        def get_secret(self, path):
            return {"a/c": "secret-ac", "b": "secret-b"}[path]

    get_all_secrets = getattr(TestVaultClient(), method_name)

    result = get_all_secrets("a", "")

    assert result == {"a": {"c": "secret-ac"}, "b": "secret-b"}

    result = get_all_secrets("a")

    assert result == {"a": {"c": "secret-ac"}}


def test_vault_client_base_get_secrets():
    class TestVaultClient(client.VaultClientBase):
        def __init__(self):
            pass

        def list_secrets(self, path):
            return {"": ["a/", "b"], "a": ["c"], "b": []}[path]

        def get_secret(self, path):
            return {"a/c": "secret-ac", "b": "secret-b"}[path]

    result = TestVaultClient().get_secrets("a")

    assert result == {"a/c": "secret-ac"}

    result = TestVaultClient().get_secrets("b")

    assert result == {"b": "secret-b"}


def test_vault_client_base_delete_all_secrets():
    deleted = []

    class TestVaultClient(client.VaultClientBase):
        def __init__(self):
            pass

        def delete_secret(self, path):
            deleted.append(path)

        def list_secrets(self, path):
            return {"": ["a/", "b/"], "a": ["c"], "b": ["d"]}[path]

    result = TestVaultClient().delete_all_secrets("a", "b")
    next(result)

    assert deleted == []

    next(result)

    assert deleted == ["a/c"]

    list(result)

    assert deleted == ["a/c", "b/d"]


def test_vault_client_base_context_manager():
    class TestVaultClient(client.VaultClientBase):
        def __init__(self):
            pass

    client_obj = TestVaultClient()

    with client_obj as c:
        assert c is client_obj


def test_vault_client_set_secret():

    written = {}
    tested_get = []
    tested_list = []

    class TestVaultClient(client.VaultClientBase):
        def __init__(self):
            pass

        def _set_secret(self, path, value):
            written[path] = value

        def list_secrets(self, path):
            tested_list.append(path)
            return []

        def get_secret(self, path):
            tested_get.append(path)
            raise exceptions.VaultSecretDoesNotExist(404, "nooooo")

    TestVaultClient().set_secret("a/b", "c")

    assert written == {"a/b": "c"}
    assert set(tested_get) == {"a/b", "a"}
    assert tested_list == ["a/b"]


def test_vault_client_set_secret_overwrite():

    written = {}
    tested_get = []
    tested_list = []

    class TestVaultClient(client.VaultClientBase):
        def __init__(self):
            pass

        def _set_secret(self, path, value):
            written[path] = value

        def list_secrets(self, path):
            tested_list.append(path)
            return []

        def get_secret(self, path):
            tested_get.append(path)
            return "lol"

    with pytest.raises(exceptions.VaultOverwriteSecretError):
        TestVaultClient().set_secret("a/b", "c")

    assert written == {}
    assert set(tested_get) == {"a/b"}
    assert tested_list == []


def test_vault_client_set_secret_overwrite_force():

    written = {}
    tested_get = []
    tested_list = []

    class TestVaultClient(client.VaultClientBase):
        def __init__(self):
            pass

        def _set_secret(self, path, value):
            written[path] = value

        def list_secrets(self, path):
            tested_list.append(path)
            return []

        def get_secret(self, path):
            tested_get.append(path)
            try:
                return {"a/b": "lol"}[path]
            except KeyError:
                raise exceptions.VaultSecretDoesNotExist(404, "nooooo")

    TestVaultClient().set_secret("a/b", "c", force=True)

    assert written == {"a/b": "c"}
    assert set(tested_get) == {"a/b", "a"}
    assert tested_list == ["a/b"]


def test_vault_client_set_secret_when_there_are_existing_secrets_beneath_path():

    written = {}
    tested_get = []
    tested_list = []

    class TestVaultClient(client.VaultClientBase):
        def __init__(self):
            pass

        def _set_secret(self, path, value):
            written[path] = value

        def list_secrets(self, path):
            tested_list.append(path)
            return ["d/"]

        def get_secret(self, path):
            tested_get.append(path)
            raise exceptions.VaultSecretDoesNotExist(404, "nooooo")

    with pytest.raises(exceptions.VaultMixSecretAndFolder):
        TestVaultClient().set_secret("a/b", "c")

    assert written == {}
    assert tested_get == ["a/b"]
    assert tested_list == ["a/b"]


def test_vault_client_set_secret_when_a_parent_is_an_existing_secret():

    written = {}
    tested_get = []
    tested_list = []

    class TestVaultClient(client.VaultClientBase):
        def __init__(self):
            pass

        def _set_secret(self, path, value):
            written[path] = value

        def list_secrets(self, path):
            tested_list.append(path)
            return []

        def get_secret(self, path):
            tested_get.append(path)
            try:
                return {"a": "lol"}[path]
            except KeyError:
                raise exceptions.VaultSecretDoesNotExist(404, "nooooo")

    with pytest.raises(exceptions.VaultMixSecretAndFolder):
        TestVaultClient().set_secret("a/b", "c")

    assert written == {}
    assert set(tested_get) == {"a/b", "a"}
    assert tested_list == ["a/b"]


@pytest.mark.parametrize("force_value", [True, False])
def test_vault_client_move_secrets(force_value):
    written = {}
    deleted = []

    class TestVaultClient(client.VaultClientBase):
        def __init__(self):
            pass

        def set_secret(self, path, value, force=False):
            assert force is force_value
            written[path] = value

        def delete_secret(self, path):
            deleted.append(path)

        def get_secrets(self, path):
            return {"foo/hello": "world", "foo/yay/haha": "baz"}

    result = list(TestVaultClient().move_secrets("foo", "barbar", force=force_value))

    assert result == [
        ("foo/hello", "barbar/hello"),
        ("foo/yay/haha", "barbar/yay/haha"),
    ]
    assert written == {"barbar/hello": "world", "barbar/yay/haha": "baz"}
    assert deleted == ["foo/hello", "foo/yay/haha"]
