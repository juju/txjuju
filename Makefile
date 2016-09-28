PYTHON = python2

.PHONY: test
test:
	$(PYTHON) -m unittest discover -t $(shell pwd) -s $(shell pwd)/txjuju

.PHONY: coverage
coverage:
	# sudo apt-get install python-coverage
	$(PYTHON) -m coverage run --branch --source txjuju -m unittest discover -t . -s txjuju/tests
	$(PYTHON) -m coverage report

.PHONY: lint
lint:
	# sudo apt-get install python-flake8
	$(PYTHON) -m flake8 .

.PHONY: install-dev
install-dev:
	ln -s $(shell pwd)/txjuju /usr/local/lib/python2.7/dist-packages/txjuju
