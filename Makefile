.PHONY: install update export

install:
	poetry install

update:
	poetry update

export:
	poetry export -f requirements.txt --output requirements.txt

sync: install update export
