PYTHON = python2

.PHONY: test
test:
	$(PYTHON) -m unittest discover -t $(shell pwd) -s $(shell pwd)/txjuju
