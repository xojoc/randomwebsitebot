SHELL = /bin/bash -o pipefail
include .env
export

poetry_export:
	@poetry export -f requirements.txt --output requirements.txt

run:
	@poetry run ./docker-entrypoint.sh

pre-commit: lint test poetry_export
	@git add requirements.txt

cp: lint test
	@git commit -a
	@git push origin main
	@git status

d: poetry_export
	@docker build -t randomwebsitebot .
	-docker stop $$(docker ps -l -f name=randomwebsitebot --format '{{.ID}}')
	@docker run --rm --name randomwebsitebot --env-file .env randomwebsitebot
	@docker logs -f $$(docker ps -l -f name=randomwebsitebot --format '{{.ID}}')

dshell:
	docker exec -it $$(docker ps -l -f name=randomwebsitebot -q) bash

shell:
	poetry run python

lint:
	@poetry run ruff check . | tac

test:
	@poetry run python -m unittest

update:
	poetry self update
	poetry update
	poetry types update
