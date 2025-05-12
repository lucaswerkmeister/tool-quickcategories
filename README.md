# QuickCategories

[This tool](https://quickcategories.toolforge.org/) allows users to add and remove categories from pages in batches.
For more information,
please see the tool’s [on-wiki documentation page](https://meta.wikimedia.org/wiki/User:Lucas_Werkmeister/QuickCategories).

## Toolforge setup

On Wikimedia Toolforge, this tool runs under the `quickcategories` tool name,
from a container built using the [Toolforge Build Service](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Build_Service).

### Image build

To build a new version of the image,
run the following command on Toolforge after becoming the tool account:

```sh
toolforge build start --use-latest-versions https://gitlab.wikimedia.org/toolforge-repos/quickcategories
```

The image will contain all the dependencies listed in `requirements.txt`,
as well as the commands specified in the `Procfile`.

### Webservice

The web frontend of the tool runs as a webservice using the `buildpack` type.
The web service runs the first command in the `Procfile` (`web`),
which runs the Flask WSGI app using gunicorn.

```
webservice start
```

Or, if the `~/service.template` file went missing:

```
webservice --mount=none buildservice start
```

If it’s acting up, try the same command with `restart` instead of `start`.

### Background runner

The background runner for batches runs as a [continuous job](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Jobs_framework#Creating_continuous_jobs),
as described in the `jobs.yaml` file.
To reload the jobs configuration, run the following command:

```sh
curl -sL 'https://gitlab.wikimedia.org/toolforge-repos/quickcategories/-/raw/main/jobs.yaml' | toolforge jobs load /dev/stdin
```

To inspect the job, you can use `toolforge jobs` commands:

```sh
toolforge jobs list
toolforge jobs show background-runner
toolforge jobs logs background-runner
```

Or underlying Kubernetes commands:

```sh
kubectl get deployments
kubectl get pods
kubectl logs background-runner-5b74775c8d-h9kcd # the hashes will vary
kubectl exec -it background-runner-5b74775c8d-h9kcd -- bash # ditto
```

### Configuration

The tool reads configuration from both the `config.yaml` file (if it exists)
and from any environment variables starting with `TOOL_*`.
The config file is more convenient for local development;
the environment variables are used on Toolforge:
list them with `toolforge envvars list`.
Nested dicts are specified with envvar names where `__` separates the key components,
and the tool lowercases keys in nested dicts,
so that e.g. the following are equivalent:

```sh
toolforge envvars create TOOL_OAUTH__CONSUMER_KEY 41ed6aa0a3983a8cd9ce4c2c7f93e58b
```

```yaml
OAUTH:
    consumer_key: 41ed6aa0a3983a8cd9ce4c2c7f93e58b
```

For the available configuration variables, see the `config.yaml.example` file.
(I think there might also be one or two additional configs that aren’t documented in there.)

### Update

To update the tool, build a new version of the image as described above,
then restart the webservice and background runner:

```sh
toolforge build start --use-latest-versions https://gitlab.wikimedia.org/toolforge-repos/quickcategories
webservice restart
toolforge jobs restart background-runner
```

## Local development setup

You can also run the tool locally, which is much more convenient for development
(for example, Flask will automatically reload the application any time you save a file).

```
git clone https://gitlab.wikimedia.org/toolforge-repos/quickcategories.git
cd tool-quickcategories
pip3 install -r requirements.txt
flask --debugrun
```

If you want, you can do this inside some virtualenv too.

## Contributing

To send a patch, you can submit a
[pull request on GitHub](https://github.com/lucaswerkmeister/tool-quickcategories) or a
[merge request on GitLab](https://gitlab.wikimedia.org/toolforge-repos/quickcategories).
(E-mail / patch-based workflows are also acceptable.)

## License

The code in this repository is released under the AGPL v3, as provided in the `LICENSE` file.
