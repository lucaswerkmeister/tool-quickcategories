.PHONY: check

check:
	flake8
	MYPYPATH=stubs/ find -name '*.py' -not -name 'test_*.py' -exec mypy -- {} +
	pytest
