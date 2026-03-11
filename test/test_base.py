"""Tests for django_informix_vault/base.py
"""
import random
import time

import pytest

from django.db import OperationalError
from django_informixdb_vault.base import DatabaseWrapper as VaultDatabaseWrapper

from .thread_utils import PropagatingThread

from datetime import datetime
from unittest.mock import MagicMock, mock_open


@pytest.fixture
def db_config():
    return {
        "ENGINE": "django_informixdb_vault",
        "SERVER": "informix",
        "NAME": "sysmaster",
        "VAULT_ADDR": "http://vault:8200",
        "VAULT_TOKEN": "test-token",
        "VAULT_PATH": "kv/ifx/creds"
    }


def test_get_connection_params_multiple_threads(db_config, mocker):
    """Test to catch thread safety issues with updating the settings_dict

    django_informix_vault/base.py's get_connection_params method
    modifies self.settings_dict from django.db.backends.base.BaseDatabaseWrapper
    """
    num_threads = 10
    db_conn = VaultDatabaseWrapper(db_config)
    conn_params = db_conn.get_connection_params()

    def slow_get_conn_params():
        # Sleep for pseudo-random number of seconds in the range [0.0, 1.0)
        time.sleep(random.random())
        return conn_params

    # Patch the non-vault parent class's get_connection_params method:
    mocker.patch(
        "django_informixdb.base.DatabaseWrapper.get_connection_params",
        side_effect=slow_get_conn_params,
    )

    def get_conn_params_worker():
        db_conn.get_connection_params()

    threads = []
    for tnum in range(num_threads):
        threads.append(PropagatingThread(target=get_conn_params_worker))
        threads[tnum].start()

    # Because we're using PropagatingThread, calling join on each thread
    # will raise any exception which was raised within the thread,
    # e.g. KeyError: 'USER'
    for tnum in range(num_threads):
        threads[tnum].join()


@pytest.fixture
def settings_dict():
    return {
        'VAULT_ADDR': 'http://localhost:8200',
        'VAULT_K8S_ROLE': 'test-role',
        'VAULT_PATH': 'secret/data/test',
        'NAME': 'eunice',
        'SERVER': 'server',
        'USER': "user",
        'PASSWORD': "password"
    }


@pytest.fixture
def db_wrapper(settings_dict):
    return VaultDatabaseWrapper(settings_dict)


def test_get_vault_uri(db_wrapper):
    assert db_wrapper._get_vault_uri() == 'http://localhost:8200'


def test_get_k8s_role(db_wrapper):
    assert db_wrapper._get_k8s_role() == 'test-role'


def test_get_kvv2_mount_point_default(db_wrapper):
    assert db_wrapper._get_kvv2_mount_point() == 'secret'


def test_get_k8s_auth_mount_point_default(db_wrapper):
    assert db_wrapper._get_k8s_auth_mount_point() == 'kubernetes'


def test_get_maximum_credential_lifetime_default(db_wrapper):
    assert db_wrapper._get_maximum_credential_lifetime() == 3600


def test_auth_via_k8s(mocker, db_wrapper):
    mock_client = MagicMock()
    mocker.patch('builtins.open', mock_open(read_data='test-jwt'))
    mocker.patch('os.access', return_value=True)

    db_wrapper._auth_via_k8s(mock_client)

    mock_client.auth.kubernetes.login.assert_called_once_with(
        role='test-role',
        jwt='test-jwt',
        mount_point='kubernetes'
    )


def test_get_authenticated_client_with_k8s(mocker, db_wrapper):
    mock_client = MagicMock()
    mocker.patch('hvac.Client', return_value=mock_client)
    mocker.patch(
        'builtins.open',
        mock_open(read_data='mocked-jwt-content')
    )
    mocker.patch('os.access', return_value=True)
    mock_client.is_authenticated.return_value = True

    client = db_wrapper.get_authenticated_client()

    assert client == mock_client
    mock_client.auth.kubernetes.login.assert_called_once()


def test_get_authenticated_client_with_token(mocker, settings_dict):
    settings_dict.pop('VAULT_K8S_ROLE')
    settings_dict['VAULT_TOKEN'] = 'test-token'
    db_wrapper = VaultDatabaseWrapper(settings_dict)

    mock_client = MagicMock()
    mocker.patch('hvac.Client', return_value=mock_client)
    mock_client.is_authenticated.return_value = True

    client = db_wrapper.get_authenticated_client()
    assert client == mock_client
    assert mock_client.token == 'test-token'
    mock_client.auth.kubernetes.login.assert_not_called()


def test_get_authenticated_client_raises_exception(
    mocker, db_wrapper
):
    mock_client = MagicMock()
    mocker.patch('hvac.Client', return_value=mock_client)
    mocker.patch(
        'builtins.open',
        mock_open(read_data='mocked-jwt-content')
    )
    mocker.patch('os.access', return_value=True)
    mock_client.is_authenticated.return_value = False

    with pytest.raises(OperationalError):
        db_wrapper.get_authenticated_client()


def test_get_credentials_from_vault(mocker, db_wrapper):
    mock_client = MagicMock()
    mocker.patch('hvac.Client', return_value=mock_client)
    mock_client.is_authenticated.return_value = True
    mock_client.secrets.kv.v2.read_secret_version.return_value = {
        'data': {'data': {'username': 'test-user', 'password': 'test-pass'}}
    }
    mocker.patch(
        'builtins.open',
        mock_open(read_data='mocked-jwt-content')
    )
    mocker.patch('os.access', return_value=True)

    username, password = db_wrapper.get_credentials_from_vault()

    assert username == 'test-user'
    assert password == 'test-pass'


def test_get_credentials_from_vault_raises_exception(mocker, db_wrapper):
    from hvac.exceptions import Forbidden
    mock_client = MagicMock()
    mocker.patch('hvac.Client', return_value=mock_client)
    mock_client.secrets.kv.v2.read_secret_version.side_effect = Forbidden("Vault error")
    mocker.patch(
        'builtins.open',
        mock_open(read_data='mocked-jwt-content')
    )
    mocker.patch('os.access', return_value=True)

    with pytest.raises(OperationalError):
        db_wrapper.get_credentials_from_vault()


def test_get_connection_params(mocker, db_wrapper):
    # Mock the get_credentials_from_vault method
    mocker.patch.object(db_wrapper, 'get_credentials_from_vault',
                        return_value=('test-user', 'test-pass'))

    # Mock threading lock to avoid actual threading behavior
    mocker.patch('threading.Lock', return_value=mocker.MagicMock())

    # Call the method
    conn_params = db_wrapper.get_connection_params()

    # Assert the connection parameters include the mocked credentials
    assert conn_params['USER'] == 'test-user'
    assert conn_params['PASSWORD'] == 'test-pass'


def test_credentials_need_refresh(mocker, db_wrapper):
    # Mock the maximum credential lifetime
    mocker.patch.object(db_wrapper, '_get_maximum_credential_lifetime',
                        return_value=3600)

    # Set the start time to a fixed datetime
    start_time = datetime(2023, 1, 1, 12, 0, 0)
    db_wrapper.settings_dict['CREDENTIALS_START_TIME'] = start_time

    # Mock datetime.now to simulate time passage
    mocker.patch('django_informixdb_vault.base.datetime', wraps=datetime)
    mocker.patch('django_informixdb_vault.base.datetime.now',
                 return_value=datetime(2023, 1, 1, 13, 0, 0))

    # Assert that credentials need refresh after 1 hour
    assert db_wrapper._credentials_need_refresh() is True

    # Mock datetime.now to simulate a time within the lifetime
    mocker.patch('django_informixdb_vault.base.datetime.now',
                 return_value=datetime(2023, 1, 1, 12, 30, 0))

    # Assert that credentials do not need refresh within the lifetime
    assert db_wrapper._credentials_need_refresh() is False