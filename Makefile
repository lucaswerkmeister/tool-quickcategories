.PHONY: check

check:
	find -name '*.py' -not -name 'test_*.py' -exec mypy -- {} +
	pytest
