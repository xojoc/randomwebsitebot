SHELL = /bin/bash -o pipefail
include .env
export

poetry_export:
	@poetry export -f requirements.txt --output requirements.txt

run:
	@poetry run ./docker-entrypoint.sh

cp: lint poetry_export
	@git commit -a
	@git push origin main

docker: poetry_export
	@docker build -t randomwebsitebot .
	@docker stop $$(docker ps -l -f name=randomwebsitebot --format '{{.ID}}')
	@docker run --rm --name randomwebsitebot --env-file .env randomwebsitebot
	@docker logs -f $$(docker ps -l -f name=randomwebsitebot --format '{{.ID}}')

dshell:
	docker exec -it $$(docker ps -l -f name=randomwebsitebot -q) bash

shell:
	poetry run python

lint:
	@poetry run flake8 --extend-ignore E501,E741,E203 | tac
	# @poetry run mypy --install-types --non-interactive .

# test:
# 	@poetry run python -Wa manage.py test --shuffle --noinput --keepdb
