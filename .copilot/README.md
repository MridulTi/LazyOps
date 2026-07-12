# LazyOps Built-in Workflow Handoff

This document is intended for an AI coding agent that will implement the feature request described below.

## Feature Goal

Transform LazyOps from a generic workflow runner into a platform for operational automation by adding first-class built-in workflows that are discoverable, reusable, and executed through the same runtime engine.

The CLI should remain thin. It should resolve user-facing commands like:

```bash
lazyops aws trace api.example.com
lazyops aws logs payment-api
lazyops aws ssh payment-api
lazyops k8s restart-pods
lazyops nginx trace
lazyops terraform summary
```

into existing workflow definitions and run them through the existing execution path.

## Core Philosophy

- Everything is a workflow.
- The workflow engine is the single execution mechanism.
- The CLI should not contain business logic.
- Built-in workflows should be organized by category and discovered recursively.
- The registry should be extensible so future plugin/pack installs are possible without hardcoding categories.

## Desired Architecture

### 1. Thin CLI layer

The command layer should only do routing and argument normalization.

Example:

```bash
lazyops aws trace api.example.com
```

should behave like:

```bash
lazyops run aws/trace --domain api.example.com
```

or equivalently be resolved to the same internal execution path.

### 2. Generic workflow engine

The current runtime execution model should stay as the only execution mechanism.

The CLI should not embed AWS-specific logic. It should only:

- resolve the workflow target,
- pass arguments through,
- invoke the existing execution engine.

### 3. Built-in workflow registry

Workflows should live under a local tree such as:

```text
workflows/
  aws/
    trace/
      workflow.yaml
      main.py
    logs/
      workflow.yaml
      main.py
  kubernetes/
    restart-pods/
      workflow.yaml
  nginx/
    trace/
      workflow.yaml
  terraform/
    summary/
      workflow.yaml
```

The registry should discover workflows recursively rather than relying on a hardcoded list of categories.

## Current Repository State

The repository already has a generic workflow execution model:

- [lazyops_cli/cli.py](../lazyops_cli/cli.py) wires the CLI entrypoint.
- [commands/run.py](../commands/run.py) implements the main workflow execution flow.
- [registry/discover.py](../registry/discover.py) currently discovers local workflow folders in a simple way.

The current implementation already supports running workflows through the generic path:

```bash
lazyops run <pack>/<plugin>
```

The task is to extend that model so that namespaced CLI commands can map to the same execution path.

## Implementation Notes for the Agent

### Important constraints

- Do not hardcode AWS or Kubernetes logic into the CLI runner.
- Do not create a second execution path.
- Keep the routing layer thin.
- Preserve the existing generic behavior of `lazyops run`.
- Make the registry discovery generic and recursive.

### Recommended implementation approach

1. Add a local built-in workflow discovery mechanism
   - Discover workflows under a local `workflows/` directory.
   - Support nested folders like `aws/trace`.
   - Treat each workflow folder as a self-contained unit.

2. Add a resolver for namespaced CLI commands
   - Example: `aws trace` should map to `aws/trace`.
   - Example: `k8s restart-pods` should map to `kubernetes/restart-pods` if desired.
   - The router should be generic and based on workflow IDs or paths.

3. Reuse the existing runner
   - Once the target workflow is resolved, call the same logic used by `lazyops run`.
   - Avoid branching into a separate execution path.

4. Add a first built-in workflow
   - Start with AWS Trace.
   - For the first iteration, it can simply do DNS lookup and print the result.
   - Later it can be expanded to include account, region, ELB, target group, and log/SSH shortcuts.

## First Milestone: Built-in AWS Trace

The first workflow should be:

```text
workflows/aws/trace/
```

Initial behavior:

- accept a domain argument,
- perform a DNS lookup,
- print the resolved result,
- exit successfully.

This gives the architecture a working end-to-end example without overbuilding the first version.

## Suggested Workflow Format

Each workflow should include:

```yaml
id: trace
name: AWS Trace
description: Investigate a domain in the AWS context
runtime: python
entrypoint: main.py
version: 1.0.0
```

The workflow folder should remain self-contained and may include:

- `workflow.yaml`
- `main.py`
- `README.md`
- any other local assets

## Acceptance Criteria

The feature is considered complete when:

- `lazyops run aws/trace ...` works through the existing engine.
- `lazyops aws trace ...` resolves to the same workflow and executes it.
- The routing layer is thin and does not contain operational logic.
- Workflows are discovered recursively from the built-in directory.
- The design is extensible for future packs/plugins.

## Suggested Files to Inspect

- [lazyops_cli/cli.py](../lazyops_cli/cli.py)
- [commands/run.py](../commands/run.py)
- [registry/discover.py](../registry/discover.py)
- [registry/fetch.py](../registry/fetch.py)
- [registry/paths.py](../registry/paths.py)
- [README.md](../README.md)
- [ARCHITECTURE.md](../ARCHITECTURE.md)
- [WORKFLOW_SPEC.md](../WORKFLOW_SPEC.md)

## Suggested Next Steps

1. Add a local workflow discovery mechanism under `workflows/`.
2. Implement a generic resolver that maps a command path like `aws trace` to a workflow identifier.
3. Route the resolved workflow into the existing run execution path.
4. Create the first built-in workflow under `workflows/aws/trace`.
5. Add tests or a minimal verification script.

## Notes for Future Extensibility

This should eventually support:

- plugin installation via `lazyops install ...`
- remote pack discovery
- recursive registry scanning
- namespace-based command routing
- built-in and external workflows coexisting cleanly

The key design principle is:

> Keep the core engine generic and keep commands thin.
