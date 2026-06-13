# Workflow Specification

## Purpose

Each workflow consists of a directory containing executable logic and metadata.

The metadata is stored in `workflow.yaml`.

## Required Fields

```yaml
id: restart-pods

name: Restart Pods

description: Restart unhealthy Kubernetes deployments

runtime: bash

entrypoint: script.sh

version: 1.0.0
```

## Optional Fields

```yaml
author: Jane Doe

tags:
  - kubernetes
  - eks
  - debugging

homepage: https://example.com

repository: https://github.com/example/project

timeout: 300
```

## Inputs

```yaml
inputs:
  - name: namespace
    type: string
    required: true

  - name: deployment
    type: string
    required: true

  - name: force
    type: boolean
    default: false
```

The CLI prompts for missing required values.

## Outputs

Scripts should communicate using:

* stdout for normal output
* stderr for errors
* exit code 0 for success
* non-zero exit code for failure

The framework does not impose additional output formatting.

## Environment Variables

Each input is exported as an environment variable.

Example:

NAMESPACE=payments

DEPLOYMENT=api

FORCE=true

Reserved variables may include:

WORKFLOW_ID

WORKFLOW_ROOT

WORKFLOW_RUNTIME

WORKFLOW_VERSION

## Supported Runtimes

Initial support:

* bash
* sh
* python
* node
* executable

Planned future support:

* powershell
* go binaries
* ruby
* containerized execution

## Directory Layout

restart-pods/
├── workflow.yaml
├── script.sh
└── README.md

Additional files are permitted and are treated as workflow-local resources.

## Validation Rules

* Every workflow must contain exactly one workflow.yaml.
* Every workflow must define an id.
* Entrypoint must exist.
* Runtime must be supported.
* Duplicate IDs are not allowed.
