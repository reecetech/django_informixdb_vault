from django.core.exceptions import ImproperlyConfigured
from django.db import (
    InternalError,
    OperationalError,
)

from django_informixdb import base

class DatabaseWrapper(base.DatabaseWrapper):

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
