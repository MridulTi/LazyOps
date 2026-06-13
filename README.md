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

* 🚀 Run scripts as named workflows
* 🔍 Search workflows by name or tags
* 📦 Keep scripts self-contained with metadata
* 🐍 Support multiple runtimes (Bash, Python, Node.js, executables)
* 📝 Interactive prompts for required inputs
* ✅ Manifest validation before execution
* 🤝 Easy to share and version-control

## Example

Directory structure:

```text
workflows/
└── restart-pods/
    ├── workflow.yaml
    ├── script.sh
    └── README.md
```

Run it:

```bash
lazyops run restart-pods
```

LazyOps reads the workflow definition, collects required inputs, and executes the script using the declared runtime.

## Example Manifest

```yaml
id: restart-pods

name: Restart Pods

description: Restart unhealthy Kubernetes deployments

runtime: bash

entrypoint: script.sh

inputs:
  - name: namespace
    required: true

  - name: deployment
    required: true
```

## Philosophy

Scripts should remain scripts.

LazyOps does not replace your automation. It makes it easier to organize, discover, document, and reuse.

## Roadmap

* [x] Workflow specification
* [ ] Local workflow execution
* [ ] Interactive CLI
* [ ] Search and validation
* [ ] Workflow packs
* [ ] Plugin runtimes
* [ ] Optional web dashboard

## Contributing

Contributions are welcome.

You can help by:

* Adding workflows
* Improving documentation
* Supporting additional runtimes
* Reporting bugs
* Suggesting new features

## License

MIT License
