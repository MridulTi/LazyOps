# LazyOps

> Turn your scattered scripts into reusable, searchable, and shareable workflows.

## Why LazyOps?

Every engineer has a folder full of scripts:

```text
cleanup.sh
restart-pods.py
rotate_logs.sh
debug-nginx.sh
fix-permissions.sh
```

After a few months:

* You forget they exist.
* You can't remember their arguments.
* They're undocumented.
* They only work on your machine.
* Your teammates rewrite the same automation.

LazyOps solves this by adding a lightweight workflow layer on top of existing scripts.

No rewrites. No proprietary language. Just structure.

## Features

* 🚀 Run scripts as named workflows (`lazyops run pack/plugin`)
* 📦 Install workflow **packs** (aws, kubernetes, security, …) from a remote catalog
* 🔍 Search and list workflows across installed packs
* 🐍 Support multiple runtimes (Bash, Python, Node.js, executables)
* 📝 Interactive picker when you run `lazyops run` with no arguments
* ✅ Manifest validation before execution
* 🔖 Pin catalog version by git branch or tag (`source.ref`)
* 🤝 Workflows live in a separate repo — share and version them independently

## Architecture

LazyOps is a **CLI-only installer**. Workflows are fetched at runtime from a separate plugins repo:

| Repo | Role |
|------|------|
| [LazyOps](https://github.com/MridulTi/LazyOps) | CLI, config, fetch & run |
| [lazyops-plugins](https://github.com/MridulTi/lazyops-plugins) | Workflow catalog (packs + plugins) |

Each **pack** is a bundle (e.g. `aws`, `kubernetes`). Each **plugin** is one workflow folder under that pack. The git **branch or tag** on the plugins repo is the catalog **version**.

```text
lazyops-plugins/
└── plugins/
    └── aws/
        ├── pack.yaml
        └── addpatchclasstag/
            ├── workflow.yaml
            ├── script.sh
            └── README.md
```

Run a workflow:

```bash
lazyops run aws/addpatchclasstag
```

LazyOps fetches the plugin at your configured `source.ref`, validates the manifest, and executes the script.

## Installation

### From PyPI (recommended)

The PyPI package is **`lazyops-cli`** (the name `lazyops` is taken by another project). The command is still `lazyops`:

```bash
pipx install lazyops-cli
lazyops --help
```

Requires Python 3.10+ and `git` (used to fetch workflows at runtime).

### From source (development)

LazyOps runs from a project-local virtual environment (`.venv`). Do not install with system `pip`.

```bash
git clone https://github.com/MridulTi/LazyOps.git
cd LazyOps
bash setup.sh
source ~/.zshrc   # or ~/.bashrc — loads the lazyops alias
lazyops --help    # works from any directory
```

`setup.sh` adds a global shell alias pointing at the repo wrapper (which always uses `.venv`):

```bash
alias lazyops='/path/to/LazyOps/lazyops'
export LAZYOPS_ROOT='/path/to/LazyOps'
```

You can also run from the repo without the alias:

```bash
./lazyops --help
source .venv/bin/activate
```

## Quick start

Point LazyOps at the plugins catalog, enable packs, and run workflows:

```bash
# 1. Configure the plugins source (branch = version)
lazyops source init https://github.com/MridulTi/lazyops-plugins.git --ref v1.0.0

# 2. Enable packs you need
lazyops pack add aws
lazyops pack add kubernetes

# 3. Discover and run
lazyops list
lazyops search patch
lazyops run aws/addpatchclasstag
lazyops run                    # interactive: pick pack → pick plugin → confirm

# 4. Upgrade catalog version
lazyops source update --ref v1.2.0
```

For local development against a checkout of lazyops-plugins:

```bash
lazyops source init file:///path/to/lazyops-plugins --ref main
```

Config is stored at `~/.lazyops/config.yaml`:

```yaml
source:
  url: https://github.com/MridulTi/lazyops-plugins.git
  ref: v1.0.0
  path_prefix: plugins
packs:
  - aws
  - kubernetes
```

## Commands

| Command | Purpose |
|---------|---------|
| `lazyops source init <url> [--ref]` | Set plugins repo URL and version |
| `lazyops source show` | Show current source config |
| `lazyops source update --ref <ref>` | Bump catalog version |
| `lazyops pack add <pack>` | Enable a pack |
| `lazyops pack list` | List installed packs |
| `lazyops pack list <pack>` | List plugins in a pack |
| `lazyops pack remove <pack>` | Disable a pack |
| `lazyops run <pack>/<plugin> [args...]` | Fetch and run a workflow |
| `lazyops run` | Interactive workflow picker |
| `lazyops list` | List workflows in installed packs |
| `lazyops search <query>` | Search by name, id, or description |

## Example manifest

```yaml
id: addpatchclasstag

name: "Add Patch Class Tag"

description: "Add patch class tags to instances. Required env: AWS_REGION or REGION."

runtime: bash

entrypoint: script.sh

pack: aws

version: 1.0.0

inputs:
  - name: instance_id
    required: true
```

## Philosophy

Scripts should remain scripts.

LazyOps does not replace your automation. It makes it easier to organize, discover, document, and reuse — with a shared catalog your whole team can install and pin to a version.

## Roadmap

* [x] Workflow specification
* [x] Remote plugin catalog (source + packs)
* [x] Fetch and run workflows from git
* [x] Interactive CLI
* [x] Search and list
* [ ] Input validation
* [ ] Plugin runtimes
* [ ] Optional web dashboard

## Contributing

Contributions are welcome.

You can help by:

* Adding workflows to [lazyops-plugins](https://github.com/MridulTi/lazyops-plugins)
* Improving CLI documentation
* Supporting additional runtimes
* Reporting bugs
* Suggesting new features

## License

MIT License
