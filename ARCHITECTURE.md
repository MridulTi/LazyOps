# Architecture

## Overview

The system consists of four primary components:

1. Registry
2. CLI
3. Runtime Executor
4. Workflow Definitions

The CLI discovers workflows from the registry, validates metadata, collects user input, and invokes the appropriate runtime.

## CLI Flow

1. User executes a command.
2. CLI loads configured workflow directories.
3. Workflow manifests are discovered and validated.
4. Requested workflow is selected.
5. Required inputs are collected.
6. Environment variables are prepared.
7. Appropriate runtime is selected.
8. Script is executed.
9. Output is streamed to the terminal.
10. Exit status is returned.

## Registry Layout

Example:

workflows/
├── restart-pods/
│   ├── workflow.yaml
│   ├── script.sh
│   └── README.md
│
├── cleanup-images/
│   ├── workflow.yaml
│   └── cleanup.py

Each workflow is self-contained and owns its metadata.

## Workflow Lifecycle

Author
→ Create folder
→ Add script
→ Add workflow.yaml
→ Validate
→ Execute
→ Share
→ Improve

No compilation or packaging step is required.

## Runtime Execution Model

The CLI never interprets business logic.

Instead, it dispatches execution to the declared runtime.

Examples:

runtime: bash
→ /bin/bash script.sh

runtime: python
→ python script.py

runtime: node
→ node app.js

runtime: executable
→ ./binary

The runtime is responsible for executing the workflow while the CLI manages discovery, validation, input collection, and environment preparation.

## Security Principles

* No workflow is executed without explicit user invocation.
* Scripts execute with the user's permissions.
* Workflows are isolated by directory.
* Metadata is validated before execution.
* The framework never silently downloads or runs remote code.

## Extensibility

Future versions may support:

* Plugin runtimes
* Workflow packs
* Remote registries
* Dashboard UI
* Execution history
* AI-assisted documentation generation
