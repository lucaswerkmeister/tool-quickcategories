.PHONY: check

check:
	flake8
# mypy disabled 2019-11-08 (cf. https://travis-ci.com/lucaswerkmeister/tool-quickcategories/builds/126371965);
# try reverting once https://github.com/python/mypy/commit/1be5487fff693d342153482627022f1fadcd63a8 is released
#	MYPYPATH=stubs/ mypy .
	pytest
