.PHONY: help install dev lint test

SHELL := /bin/bash

help:
	@echo "install   Install dependencies"
	@echo "dev       Run dev server"
	@echo "lint      Format + lint"
	@echo "test      Run tests"

install:
	poetry install

dev:
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8002

lint:
	poetry run ruff format .
	poetry run ruff check .

test:
	poetry run pytest
