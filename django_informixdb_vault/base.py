import os

import hvac

from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError

from django_informixdb import base

class DatabaseWrapper(base.DatabaseWrapper):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.vault_client = None
        if 'vault_client' in kwargs:
            self.vault_client = kwargs['vault_client']
        else:
            self.vault_client = self.get_authenticated_client()

    def _get_vault_uri(self):
        vault_uri = self.settings_dict.get('VAULT_ADDR', None)
        if vault_uri is None and 'VAULT_ADDR' in os.environ:
            vault_uri = os.environ['VAULT_ADDR']

        return vault_uri

    @staticmethod
    def _auth_via_k8s(client, role):
        try:
            with open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'rb') as jwt_fh:
                jwt = jwt_fh.read()

            client.auth_kubernetes(role, jwt)
        except IOError:
            pass

    def _auth_via_token(self, client):
        vault_token = self.settings_dict.get('VAULT_TOKEN', None)
        if vault_token is None and 'VAULT_TOKEN' in os.environ:
            vault_token = os.environ['VAULT_TOKEN']

        client.token = vault_token

    def get_authenticated_client(self):
        vault_uri = self._get_vault_uri()
        if vault_uri is None:
            raise ImproperlyConfigured('vault_uri is a required setting for a Vault authenticated informix connection')

        hvac_client = hvac.Client(url=vault_uri)

        if self.settings_dict.get('VAULT_K8S_ROLE', None):
            self._auth_via_k8s(hvac_client, self.settings_dict['VAULT_K8S_ROLE'])
        elif os.access('/var/run/secrets/kubernetes.io/serviceaccount/token', os.R_OK):
            raise ImproperlyConfigured('Kubernetes Vault JWT available, but VAULT_K8S_ROLE not configured in settings')
        else:
            self._auth_via_token(hvac_client)

        try:
            if not hvac_client.is_authenticated():
                raise ImproperlyConfigured(
                    'Vault client failed to authenticate, provide JWT via K8s or basic token via settings'
                )
        except hvac.exceptions.VaultError as err:
            msg = err.args[0]
            raise OperationalError(msg)

        return hvac_client

    def get_connection_params(self):
        # django_informixdb expects USER and PASSWORD, so fake them for now
        self.settings_dict['USER'] = ''
        self.settings_dict['PASSWORD'] = ''

        # parse/get conn_params from django_informixdb
        conn_params = super().get_connection_params()

        # We don't actually use USER and PASSWORD, so delete them
        del self.settings_dict['USER']
        del self.settings_dict['PASSWORD']

        # XXX: TODO: implement vault lookup here
        # XXX: TODO: set conn_params['USER'] and conn_params['PASSWORD'] to values from vault here

        # XXX: hardcode just for testing, remove after the above is implemented
        conn_params['USER'] = "informix"
        conn_params['PASSWORD'] = "in4mix"

        return conn_params
