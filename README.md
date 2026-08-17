# QuickCategories

[This tool](https://quickcategories.toolforge.org/) allows users to add and remove categories from pages in batches.
For more information,
please see the tool’s [on-wiki documentation page](https://meta.wikimedia.org/wiki/QuickCategories).

## Toolforge setup

On Wikimedia Toolforge, this tool runs under the `quickcategories` tool name,
using the [Toolforge Components Service](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Deploy_your_tool) to coordinate
building a container with the [Toolforge Build Service](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Build_Service)
and then deploying that for the webservice and background runner.
The components configuration is in the `toolforge.yaml` file.

To start a new deployment,
run the following command on Toolforge after becoming the tool account:

```sh
toolforge components deployment create
```

This should automatically kick off an image build and restart the webservice and background runner at the end.

### Details and troubleshooting

To inspect the overall deployment status, run:

```sh
toolforge components deployment show
```

To debug the image build step, it may be useful to trigger an image build explicitly –
you can add `--ref=foobar` to build from the `foobar` branch instead of the `main` branch:

```sh
toolforge build start https://gitlab.wikimedia.org/toolforge-repos/quickcategories
```

The web frontent is a Flask WSGI app using gunicorn,
and runs as the `quickcategories` job,
which you may inspect with commands like these:

```sh
toolforge jobs show quickcategories
toolforge jobs logs quickcategories
kubectl get deployment quickcategories
kubectl exec -it deployment/quickcategories -- bash
```

The background runner runs the `background-runner` command from the `Procfile` as the `background-runner` job,
and can be inspected likewise:

```sh
toolforge jobs show background-runner
toolforge jobs logs background-runner
kubectl get deployment background-runner
kubectl exec -it deployment/background-runner -- bash
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
toolforge envvars create TOOL_OAUTH__CONSUMER_KEY 760ac52c957b3964253fbaa884f8abb8
```

```yaml
OAUTH:
    consumer_key: 760ac52c957b3964253fbaa884f8abb8
```

For the available configuration variables, see the `config.yaml.example` file.
(I think there might also be one or two additional configs that aren’t documented in there.)

### Update

To update the tool, run `toolforge components deployment create` as described above.

## Local development setup

You can also run the tool locally, which is much more convenient for development
(for example, Flask will automatically reload the application any time you save a file).

```
git clone https://gitlab.wikimedia.org/toolforge-repos/quickcategories.git
cd tool-quickcategories
pip3 install -r requirements.txt -r dev-requirements.txt
flask --debug run
```

If you want, you can do this inside some virtualenv too.

## Contributing

To send a patch, you can submit a
[pull request on GitHub](https://github.com/lucaswerkmeister/tool-quickcategories) or a
[merge request on GitLab](https://gitlab.wikimedia.org/toolforge-repos/quickcategories).
(E-mail / patch-based workflows are also acceptable.)

## License

The code in this repository is released under the AGPL v3, as provided in the `LICENSE` file.
