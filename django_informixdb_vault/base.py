"""django_informixdb_vault: Vault authenticated Django Informix database driver"""

import os

import hvac

from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError

from django_informixdb import base

class DatabaseWrapper(base.DatabaseWrapper):
    """
    django_informixdb_vault: Vault authenticated Django Informix database driver

    Extends the django_informixdb DatabaseWrapper class
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.vault_client = None
        if 'vault_client' in kwargs:
            self.vault_client = kwargs['vault_client']
        else:
            self.vault_client = self.get_authenticated_client()

    def _get_vault_uri(self):
        vault_uri = self.settings_dict.get('VAULT_ADDR', None)
        if not vault_uri and 'VAULT_ADDR' in os.environ:
            vault_uri = os.environ['VAULT_ADDR']

        return vault_uri

    @staticmethod
    def _auth_via_k8s(client, role):
        try:
            # TODO: make the path configurable
            with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'rb') as jwt_fh:
                jwt = jwt_fh.read()

            client.auth_kubernetes(role, jwt)
        except IOError:
            pass

    def _auth_via_token(self, client):
        vault_token = self.settings_dict.get('VAULT_TOKEN', None)
        if not vault_token and 'VAULT_TOKEN' in os.environ:
            vault_token = os.environ['VAULT_TOKEN']

        client.token = vault_token

    def get_authenticated_client(self):
        """Gets an authenticated Vault client.  Raises an exception if the client is not authenticated."""
        vault_uri = self._get_vault_uri()
        if not vault_uri:
            raise ImproperlyConfigured('VAULT_ADDR is a required setting for a Vault authenticated informix connection')

        hvac_client = hvac.Client(url=vault_uri)

        if self.settings_dict.get('VAULT_K8S_ROLE', None):
            self._auth_via_k8s(hvac_client, self.settings_dict['VAULT_K8S_ROLE'])
        elif os.access('/var/run/secrets/kubernetes.io/serviceaccount/token', os.R_OK):
            raise ImproperlyConfigured('Kubernetes Vault JWT available, but VAULT_K8S_ROLE not configured in settings')
        else:
            self._auth_via_token(hvac_client)

        try:
            if not hvac_client.is_authenticated():
                raise OperationalError(
                    'Vault client failed to authenticate, provide JWT via K8s '
                    'or basic token via VAULT_TOKEN in settings.  Ensure the credientials are valid and authorised.'
                )
        except hvac.exceptions.VaultError as err:
            msg = err.args[0]
            raise OperationalError(msg)

        return hvac_client

    def _get_vault_path(self):
        vault_path = self.settings_dict.get('VAULT_PATH', None)
        if not vault_path and 'VAULT_PATH' in os.environ:
            vault_path = os.environ['VAULT_PATH']

        return vault_path

    def get_credentials_from_vault(self):
        """Gets a username and password pair from Vault."""
        vault_path = self._get_vault_path()
        if not vault_path:
            raise ImproperlyConfigured('VAULT_PATH is a required setting for a Vault authenticated informix connection')

        try:
            secrets_response = self.vault_client.secrets.kv.v2.read_secret_version(path=vault_path)

            if 'data' not in secrets_response:
                raise OperationalError('Response from Vault did not include required data')
            if 'data' not in secrets_response['data']:
                raise OperationalError('Response from Vault did not include required data')

            secrets_data = secrets_response['data']['data']
            if 'username' not in secrets_data and 'password' not in secrets_data:
                raise OperationalError('Response from Vault did not include a username and password')
            if 'username' not in secrets_data:
                raise OperationalError('Response from Vault did not include a username')
            if 'password' not in secrets_data:
                raise OperationalError('Response from Vault did not include a password')

        except hvac.exceptions.InvalidPath:
            raise OperationalError(f"No data found at path '{vault_path}'")
        except hvac.exceptions.Forbidden as err:
            msg = err.args[0]
            raise OperationalError(msg)
        except hvac.exceptions.VaultError as err:
            msg = err.args[0]
            raise OperationalError(msg)

        return secrets_data['username'], secrets_data['password']

    def get_connection_params(self):
        # django_informixdb expects USER and PASSWORD, so fake them for now
        self.settings_dict['USER'] = ''
        self.settings_dict['PASSWORD'] = ''

        # parse/get conn_params from django_informixdb
        conn_params = super().get_connection_params()

        # We don't actually use USER and PASSWORD, so delete them
        del self.settings_dict['USER']
        del self.settings_dict['PASSWORD']

        username, password = self.get_credentials_from_vault()

        conn_params['USER'] = username
        conn_params['PASSWORD'] = password

        return conn_params
