venv-repos: venv-repos/bin/activate

venv-repos: requirements.txt
	test -d venv-repos || virtualenv --no-site-packages venv-repos
	. venv-repos/bin/activate; pip install -Ur requirements.txt
	touch venv-repos/bin/activate
