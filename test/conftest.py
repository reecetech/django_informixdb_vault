import hvac
import pytest
from django.conf import settings


def pytest_configure():
    settings.configure(
        ROOT_URLCONF="test.urls",
        MIDDLEWARE=(),
        INSTALLED_APPS=(
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "test.datatypes",
        ),
        DATABASES={
            "default": {
                "ENGINE": "django_informixdb_vault",
                "SERVER": "informix",
                "NAME": "adapter",
                "VAULT_ADDR": "http://vault:8200",
                "VAULT_TOKEN": "test-token",
                "VAULT_PATH": "kv/ifx/creds",
            },
        },
    )


@pytest.fixture(autouse=True)
def configure_caplog(caplog):
    caplog.set_level("INFO")

@pytest.fixture(scope='module', autouse=True)
def ifx_secret():
    client = hvac.Client(url='http://vault:8200')
    client.token = 'test-token'
    if not client.is_authenticated():
        raise RuntimeError('Dev vault not working as expected')
    client.secrets.kv.v2.create_or_update_secret(
        path='kv/ifx/creds',
        secret={
            'username': 'informix',
            'password': 'in4mix',
        },
    )
