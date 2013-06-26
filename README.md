Repository Observer
===================

Simple script to generate a report on an organization’s Github repositories
		and/or generate info about a list of repositories

There are two functions in `lib.py` that operate on a decoded JSON
representation of a repository from Github’s API:

`is_current_repo()`

Returns `True` for a current repo, `False` otherwise. Current repositories
were created after a cutoff date, or updated recently.

`is_compliant_repo()`

Returns `(boolean, string, list)` tuple for a repository readme.

First element will be `True` for a compliant repo, `False` otherwise.
Second element will be a commit hash for the repository or `None`.
Third element will be a list of strings with reasons for failure.
Compliant repositories have a valid README file.

There is a function in 'lib.py' that operates on a JSON config file 
containing a list of repos represented by their name/owner

Install
-------

This is a python script that relies on a few external packages listed in
`requirements.txt`. Install them with `pip` or run `make` to create a virtual
environment with installed dependencies.

Run
---

Running locally, writing to local HTML output:

    python work.py --help
    python work.py -u <github username> -p <github password> -o <github organization> output.html

Fetch repo data, writing to local JSON output:

	python work.py -c <json config file> output.html

Deploying to Heroku, with four required environment variables configured and
a correct remote set up from Git:

    heroku config:set GITHUB_USERNAME=<github account username> \
                      GITHUB_PASSWORD=<github account password> \
                      AWS_ACCESS_KEY_ID=<amazon access key> \
                      AWS_SECRET_ACCESS_KEY=<amazon secret key>
    
    git push heroku master

Output
------

Outputs a list of organization repositories with “pass” or “fail” flags.
