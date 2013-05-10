venv-repos: venv-repos/bin/activate

venv-repos/bin/activate: requirements.txt
	test -d venv-repos || virtualenv --no-site-packages venv-repos
	. venv-repos/bin/activate; pip install -Ur requirements.txt
	touch venv-repos/bin/activate
