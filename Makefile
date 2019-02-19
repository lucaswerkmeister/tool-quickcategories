.PHONY: check

check:
	MYPYPATH=stubs/ find -name '*.py' -not -name 'test_*.py' -exec mypy -- {} +
	pytest
