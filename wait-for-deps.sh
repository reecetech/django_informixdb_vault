#!/bin/sh

set -euo pipefail

echo "* Checking Informix"
until $(nc -zv db 9088); do
    sleep 3
done
echo "* Informix available"

echo "* Checking Vault"
until $(nc -zv vault 8200); do
    sleep 3
done
echo "* Vault available"
