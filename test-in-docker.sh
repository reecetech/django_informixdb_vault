#!/bin/bash
set -euo pipefail

export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

docker-compose -p ifxvault build

docker-compose -p ifxvault run test-runner tox
