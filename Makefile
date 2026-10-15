PY ?= python3
IMAGE ?= flaky-hunt:dev

.PHONY: test check mutants demo real gif image docker-check

test:            ## fast self-tests (seconds)
	$(PY) -m pytest -q -m "not slow"

check:           ## lint plus every self-test, including whole hunts of the planted suite
	$(PY) -m ruff check src tests scripts examples
	$(PY) -m ruff format --check src tests scripts examples
	$(PY) -m pytest -q

mutants:         ## each deliberately broken flaky-hunt must fail the self-tests
	$(PY) scripts/mutants.py

demo:            ## hunt the planted suite
	cd examples/planted && flaky-hunt run

real:            ## hunt real projects' suites, in Docker (tens of minutes)
	scripts/real.sh

image:
	docker build -f docker/Dockerfile -t $(IMAGE) .

docker-check: image
	docker run --rm $(IMAGE) make check mutants

gif: image
	docker build -f docs/demo.Dockerfile -t flaky-hunt-vhs:dev .
	docker run --rm -v $(CURDIR):/vhs -w /vhs flaky-hunt-vhs:dev docs/demo.tape
