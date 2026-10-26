.PHONY: run test seed validate
run:
	uvicorn backend.app.main:app --reload
test:
	pytest -q
seed:
	python3 -m backend.app.seed --scale starter --seed 20261022
validate:
	python3 -m backend.app.validate
