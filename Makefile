SHELL := /bin/sh

IMAGE ?= singbox-service:local
PRIVATE_CONFIG_DIR ?= .pi/pi-tmp/singbox-config
PASSWORD_FILE ?= key
PROFILE_DIR ?= profiles

.PHONY: help lint test check profiles build image

help:
	@printf '%s\n' \
		'profiles  Build encrypted profiles from private configuration snapshots' \
		'lint      Check shell syntax' \
		'test      Run focused tests' \
		'check     Run lint and tests' \
		'image     Build the Docker image'

profiles:
	python3 scripts/build_profiles.py \
		--input-dir "$(PRIVATE_CONFIG_DIR)" \
		--output-dir "$(PROFILE_DIR)" \
		--password-file "$(PASSWORD_FILE)"

lint:
	sh -n bin/singbox-service container/entrypoint.sh tests/test_service_rollback.sh
	python3 -m py_compile scripts/build_profiles.py tests/test_build_profiles.py

test:
	python3 -m unittest discover --start-directory tests --pattern 'test_*.py' --verbose
	sh tests/test_service_rollback.sh

check: lint test

image: profiles
	docker build --tag "$(IMAGE)" .

build: image
