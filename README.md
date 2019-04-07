# QuickCategories

[This tool](https://tools.wmflabs.org/quickcategories/) allows users to add and remove categories from pages in batches.
It is currently work-in-progress, and not usable yet.

For more information,
please see the tool’s [on-wiki documentation page](https://meta.wikimedia.org/wiki/User:Lucas_Werkmeister/QuickCategories).

## Toolforge setup

On Wikimedia Toolforge, this tool runs under the `quickcategories` tool name.
Source code resides in `~/www/python/src/`.

### Webservice

The web frontend of the tool runs as a standard Python web service,
with a virtual environment in `~/www/python/venv/`
and logs ending up in `~/uwsgi.log`.

If the web service is not running for some reason, run the following command:
```
webservice --backend=kubernetes python start
```
If it’s acting up, try the same command with `restart` instead of `start`.

### Background runner

The background runner for batches runs as a [Kubernetes continuous job](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Kubernetes#Kubernetes_continuous_jobs),
with a deployment described by the `deployment.yaml` file in the source code repository.
To inspect the current status, get the currently running pod via `kubectl get pods`;
you can then, for example, view its logs with `kubectl logs NAME`
or enter a debugging shell with `kubectl exec -it NAME bash`.

To stop the runner, use `kubectl delete deployment quickcategories.background-runner`.
You can start a new one with `kubectl create -f deployment.yaml`
(or `~/www/python/src/deployment.yaml` if you’re not in the source code directory).
It sets up its own virtual environment, so it should be ready after a minute or so.

### Update

The following commands should work to update the tool after becoming the tool account:

```
# stop current processes
webservice --backend=kubernetes python stop
kubectl delete deployment quickcategories.background-runner

# update source code
cd ~/www/python/src
git fetch
git diff @ @{u} # inspect changes
git merge --ff-only @{u}

# update webservice venv
webservice --backend=kubernetes python shell
source ~/www/python/venv/bin/activate
pip3 install --upgrade pip
pip3 install -r ~/www/python/src/requirements.txt
exit

# start new processes
webservice --backend=kubernetes python start
kubectl create -f deployment.yaml
```

## Local development setup

You can also run the tool locally, which is much more convenient for development
(for example, Flask will automatically reload the application any time you save a file).

```
git clone https://phabricator.wikimedia.org/source/tool-quickcategories.git
cd tool-quickcategories
pip3 install -r requirements.txt
FLASK_APP=app.py FLASK_ENV=development flask run
```

If you want, you can do this inside some virtualenv too.

## Contributing

To send a patch, you can use any of the following methods:

* [Submit a pull request on GitHub.](https://github.com/lucaswerkmeister/tool-quickcategories)
* Use `git send-email`.
  (Send the patch(es) to the email address from the Git commit history.)
* Upload the changes to a repository of your own and use `git request-pull` (same email address).
* Upload a diff on [GitHub Gist](https://gist.github.com/)
  and send the link to the tool’s maintainer(s) via email, Twitter, on-wiki message, or whatever.
* [Create a Diff on Phabricator.](https://phabricator.wikimedia.org/differential/diff/create/)
  Make sure to add @LucasWerkmeister as subscriber.

They’re listed in the maintainer(s)’ order of preference, from most to least preferred,
but feel free to use any of these methods as it best suits you.

## License

The code in this repository is released under the AGPL v3, as provided in the `LICENSE` file.
