Repository Observer
===================

Simple script to generate a report on an organization’s Github repositories.

There are two functions in `lib.py` that operate on a decoded JSON
representation of a repository from Github’s API:

`is_current_repo()`

Return `True` for a current repo, `False` otherwise. Current repositories
were created after a cutoff date, or updated recently.

`is_compliant_repo()`

Return `True` for a compliant repo, `False` otherwise. Compliant repositories
have a valid README file.

Install
-------

This is a python script that relies on a few external packages listed in
`requirements.txt`. Install them with `pip` or run `make` to create a virtual
environment with installed dependencies.

Run
---

Running locally, writing to *stdout*:

    python get-readmes.py --help
    python get-readmes.py -u <github username> -p <github password> -o <github organization>

Deploying to Heroku, with five required environment variables configured and
a correct remote set up from Git:

    heroku config:set GITHUB_ORGANIZATION=<github organization name> \
                      GITHUB_USERNAME=<github account username> \
                      GITHUB_PASSWORD=<github account password> \
                      AWS_ACCESS_KEY_ID=<amazon access key> \
                      AWS_SECRET_ACCESS_KEY=<amazon secret key>
    
    git push heroku master

Output
------

Outputs a list of organization repositories with “pass” or “fail” flags.
