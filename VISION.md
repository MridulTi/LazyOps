# Vision

## Mission

Create the easiest way for engineers to organize, discover, execute, and share reusable automation workflows without modifying the underlying scripts.

The project aims to transform scattered shell scripts, Python utilities, and one-off automation into structured, documented, and portable workflows that can be reused across machines and teams.

## Why this project exists

Most engineers accumulate hundreds of small scripts over time:

* Kubernetes debugging commands
* AWS maintenance tasks
* Log collection utilities
* Deployment helpers
* Cleanup jobs
* Onboarding scripts

These scripts are often:

* Hidden inside personal repositories
* Poorly documented
* Difficult to search
* Hard to share
* Forgotten after a few months

As a result, engineers repeatedly solve the same problems.

This project provides a lightweight execution and metadata layer on top of existing scripts, allowing them to become reusable workflows.

## Goals

* Keep automation simple and script-first.
* Allow engineers to add workflows without changing existing code.
* Make workflows discoverable through metadata and search.
* Support multiple scripting languages and runtimes.
* Encourage sharing and collaboration through portable workflow definitions.
* Remain lightweight enough to use as a daily CLI tool.

## Non-goals

This project intentionally does not aim to:

* Replace CI/CD systems.
* Replace Kubernetes operators.
* Replace orchestration platforms like Airflow or Argo Workflows.
* Execute distributed workflows across clusters.
* Become a configuration management system.
* Force users into a proprietary scripting language.
* Rewrite or interpret user scripts.
* Depend on AI to function.

AI may enhance the developer experience in the future but is not a core requirement.

## Philosophy

Scripts should remain scripts.

The project provides structure, documentation, discovery, validation, and execution while allowing engineers to continue using the languages and tools they already know.

Automation should reduce cognitive load, not introduce additional complexity.
