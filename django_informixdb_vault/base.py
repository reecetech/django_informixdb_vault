"""django_informixdb_vault: Vault authenticated Django Informix database driver"""

# pylint: disable=logging-fstring-interpolation

import logging
import os

import hvac

from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError

from django_informixdb import base

logger = logging.getLogger(__name__)

class DatabaseWrapper(base.DatabaseWrapper):
    """
    django_informixdb_vault: Vault authenticated Django Informix database driver

    Extends the django_informixdb DatabaseWrapper class
    """

    DEFAULT_K8S_AUTH_MOUNT_POINT = 'kubernetes'
    DEFAULT_K8S_JWT = '/var/run/secrets/kubernetes.io/serviceaccount/token'

    DEFAULT_KVV2_MOUNT_POINT = 'secret'


    def _get_vault_uri(self):
        vault_uri = self.settings_dict.get('VAULT_ADDR', None)
        if not vault_uri and 'VAULT_ADDR' in os.environ:
            vault_uri = os.environ['VAULT_ADDR']

        return vault_uri

    def _get_k8s_role(self):
        role = self.settings_dict.get('VAULT_K8S_ROLE', None)
        if not role and 'VAULT_K8S_ROLE' in os.environ:
            role = os.environ['VAULT_K8S_ROLE']

        return role

    def _get_jwt_path(self):
        jwt_path = self.settings_dict.get('VAULT_K8S_JWT', None)
        if not jwt_path and 'VAULT_K8S_JWT' in os.environ:
            jwt_path = os.environ['VAULT_K8S_JWT']

        if not jwt_path:
            # Default value
            jwt_path = self.DEFAULT_K8S_JWT

        if not os.access(jwt_path, os.R_OK):
            raise ImproperlyConfigured(f"Kubernetes Vault JWT is not readable at path {jwt_path}")

        return jwt_path

    def _get_kvv2_mount_point(self):
        mount_point = self.settings_dict.get('VAULT_KVV2_MOUNT_POINT', None)
        if not mount_point and 'VAULT_KVV2_MOUNT_POINT' in os.environ:
            mount_point = os.environ['VAULT_KVV2_MOUNT_POINT']
        if not mount_point:
            mount_point = self.DEFAULT_KVV2_MOUNT_POINT

        return mount_point

    def _get_k8s_auth_mount_point(self):
        mount_point = self.settings_dict.get('VAULT_K8S_AUTH_MOUNT_POINT', None)
        if not mount_point and 'VAULT_K8S_AUTH_MOUNT_POINT' in os.environ:
            mount_point = os.environ['VAULT_K8S_AUTH_MOUNT_POINT']
        if not mount_point:
            mount_point = self.DEFAULT_K8S_AUTH_MOUNT_POINT

        return mount_point

    def _auth_via_k8s(self, client):
        role = self._get_k8s_role()
        jwt_path = self._get_jwt_path()

        with open(jwt_path, 'r', encoding='utf-8') as jwt_fh:
            jwt = jwt_fh.read()

        client.auth_kubernetes(role, jwt, mount_point=self._get_k8s_auth_mount_point())

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
            self._auth_via_k8s(hvac_client)
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

        client = self.get_authenticated_client()

        try:
            secrets_response = client.secrets.kv.v2.read_secret_version(
                path=vault_path,
                mount_point=self._get_kvv2_mount_point(),
            )

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
        """Returns connection parameters for Informix, with credentials from Vault"""
        # django_informixdb expects USER and PASSWORD, so fake them for now
        self.settings_dict['USER'] = ''
        self.settings_dict['PASSWORD'] = ''

        # parse/get conn_params from django_informixdb
        conn_params = super().get_connection_params()

        # We don't actually use USER and PASSWORD, so delete them
        del self.settings_dict['USER']
        del self.settings_dict['PASSWORD']

        username, password = self.get_credentials_from_vault()
        logger.info(
            f"Retrieved username ({username}) and password from Vault"
            f" for database server {self.settings_dict['SERVER']}"
        )

        conn_params['USER'] = username
        conn_params['PASSWORD'] = password

        return conn_params
