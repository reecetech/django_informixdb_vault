Django InformixDB Vault
=======================

Extends the database driver for Django `django_informixdb_dev` to retrieve credentials from a Hashicorp Vault service.


Assumptions
-----------

This driver expects the credentials to be stored in a KV v2 secret in Vault, as keys `username` and `password`.


Supported Authentication
------------------------

Two methods, with highest priority first:
- K8s JWT
- Basic Token


Settings Required
-----------------

Do not provide `USER` and `PASSWORD`.  Instead provide these settings:

============================  ===========  ===========
Setting                       Required     Description
============================  ===========  ===========
`VAULT_ADDR`                  Yes          The HTTPS endpoint for Vault
`VAULT_PATH`                  Yes          The path in Vault to the KV v2 secret storing the Informix credentials
`VAULT_K8S_AUTH_MOUNT_POINT`  No           The Vault mount point to use for Kubernetes authentication, default value: ``kubernetes``
`VAULT_K8S_JWT`               No           The path to the JWT in a K8s container, default vault: ``/var/run/secrets/kubernetes.io/serviceaccount/token``
`VAULT_K8S_ROLE`              Conditional  Provide the K8s role *if* using K8s JWT authentication to Vault
`VAULT_KVV2_MOUNT_POINT`      No           The Vault mount point to use for KVv2 secrets, default value: ``secret``
`VAULT_TOKEN`                 Conditional  Provide the token *if* using basic token authentication to Vault
============================  ===========  ===========
