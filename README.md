# QuickCategories

[This tool](https://quickcategories.toolforge.org/) allows users to add and remove categories from pages in batches.
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
webservice start
```
If it’s acting up, try the same command with `restart` instead of `start`.
Both should pull their config from the `service.template` file,
which is symlinked from the source code directory into the tool home directory.

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
webservice stop
kubectl delete deployment quickcategories.background-runner

# update source code
cd ~/www/python/src
git fetch
git diff @ @{u} # inspect changes
git merge --ff-only @{u}

# update webservice venv
webservice shell
source ~/www/python/venv/bin/activate
pip-sync ~/www/python/src/requirements.txt
exit

# start new processes
webservice start
kubectl create -f deployment.yaml
```

## Local development setup

You can also run the tool locally, which is much more convenient for development
(for example, Flask will automatically reload the application any time you save a file).

```
git clone https://gitlab.wikimedia.org/toolforge-repos/quickcategories.git
cd tool-quickcategories
pip3 install -r requirements.txt
FLASK_ENV=development flask run
```

If you want, you can do this inside some virtualenv too.

## Contributing

To send a patch, you can submit a
[pull request on GitHub](https://github.com/lucaswerkmeister/tool-quickcategories) or a
[merge request on GitLab](https://gitlab.wikimedia.org/toolforge-repos/quickcategories).
(E-mail / patch-based workflows are also acceptable.)

## License

The code in this repository is released under the AGPL v3, as provided in the `LICENSE` file.
