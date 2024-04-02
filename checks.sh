#!/bin/bash

# run all the checks and tests

set -e

poetry run black modules scripts

poetry run ruff check modules scripts

poetry run mypy modules scripts
