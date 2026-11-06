.PHONY: install test lint p4-compile mininet mininet-test clean

install:
	python3 -m pip install -e .

test:
	python3 -m unittest discover -s tests -v

lint:
	ruff check .

p4-compile:
	mkdir -p build
	p4c --target bmv2 --arch v1model --std p4-16 -o build/main.json p4src/main.p4

mininet: p4-compile
	sudo python3 topology/run_mininet.py

mininet-test: p4-compile
	sudo python3 topology/run_mininet.py --test

clean:
	rm -rf build received .ruff_cache .pytest_cache dist *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
