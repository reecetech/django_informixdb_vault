"""Tests for django_informix_vault/base.py
"""
import random
import time

import pytest

from django_informixdb_vault.base import DatabaseWrapper as VaultDatabaseWrapper

from .thread_utils import PropagatingThread


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
