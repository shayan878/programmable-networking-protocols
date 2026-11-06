.PHONY: test lint p4-compile clean

test:
	python -m unittest discover -s tests -v

lint:
	ruff check .

p4-compile:
	mkdir -p build
	p4c --target bmv2 --arch v1model --std p4-16 -o build/main.json p4src/main.p4

clean:
	rm -rf build .ruff_cache __pycache__ tests/__pycache__ scripts/__pycache__
