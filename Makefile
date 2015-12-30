all: build

install:
		pip3 install --user twilio

build: install

analyze: test
		pep8 *.py
		pep257 *.py

test:
