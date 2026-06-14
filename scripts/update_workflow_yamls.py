#!/usr/bin/env python3
"""Update workflow.yaml files to match generalized/variablized scripts."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS = Path(__file__).parent.parent / "workflows"

# Explicit definitions for generalized workflows.
# inputs: positional CLI args (passed by lazyops run)
# env: documented required/optional environment variables
WORKFLOW_SPECS: dict[str, dict] = {
    "delete-peering-route": {
        "name": "Delete Peering Route",
        "description": "Clean peering route tables with JSON backup. DRY_RUN defaults to true.",
        "env": ["AWS_REGION or REGION", "DRY_RUN (default: true)"],
        "inputs": [{"name": "peering-file", "required": True}],
    },
    "decline-pr": {
        "name": "Decline PR",
        "description": "Decline Bitbucket pull requests listed one URL per line in a file.",
        "env": ["BB_USER", "BB_TOKEN", "MAX_WORKERS (optional)"],
        "inputs": [{"name": "pr-links-file", "required": True}],
    },
    "migrate-repo-particular-branch": {
        "name": "Migrate Repo Particular Branch",
        "description": "Migrate selected branches in Bitbucket repos using a JSON config file.",
        "env": ["BB_USER", "BB_TOKEN"],
        "inputs": [{"name": "config", "required": True}],
    },
    "migrate-repo-all-branch": {
        "name": "Migrate Repo All Branch",
        "description": "Migrate all branches in Bitbucket repos using a JSON config file.",
        "env": ["BB_USER", "BB_TOKEN"],
        "inputs": [{"name": "config", "required": True}],
    },
    "clone-repo": {
        "name": "Clone Repo",
        "description": "Clone Bitbucket repositories from a list file.",
        "inputs": [
            {"name": "ssh-base-url", "required": True},
            {"name": "repos-file", "required": True},
            {"name": "clone-dir", "required": True},
        ],
    },
    "update-lt": {
        "name": "Update Launch Template",
        "description": "Update ASG launch templates using a source-to-target AMI map JSON file.",
        "env": ["AWS_REGION or REGION"],
        "inputs": [
            {"name": "ami-map", "required": True},
            {"name": "asg-list", "required": True},
        ],
    },
    "nacl-entry-add": {
        "name": "NACL Entry Add",
        "description": "Add NACL allow rules for a CIDR across network ACLs.",
        "env": ["AWS_REGION or REGION"],
        "inputs": [
            {"name": "cidr", "required": True},
            {"name": "port", "required": False},
        ],
    },
    "userdata": {
        "name": "Userdata Bootstrap",
        "description": "EC2 user-data script to install ansible, telegraf, and pull provisioning script from S3.",
        "env": ["S3_CONFIG_URI (required, e.g. s3://bucket/scripts/provision.sh)"],
        "inputs": [],
    },
    "git-pull-update": {
        "name": "Git Pull Update",
        "description": "Replace git org strings in remote repos and run git pull over SSH.",
        "env": ["SSH_KEY_DIR", "GIT_OLD_ORG", "GIT_NEW_ORG", "DRY_RUN (default: true)", "MAX_WORKERS (optional)"],
        "inputs": [],
    },
    "check-platform": {
        "name": "Check Platform",
        "description": "SSH OS check on running EC2 instances matching a tag filter.",
        "env": ["AWS_REGION or REGION", "SSH_KEY_PATH", "EC2_TAG_FILTER"],
        "inputs": [],
    },
    "add-tags": {
        "name": "Add Tags",
        "description": "Apply EC2 tags from a file (Key=Value per line) to instance IDs.",
        "env": ["AWS_REGION or REGION"],
        "inputs": [
            {"name": "tags-file", "required": True},
            {"name": "instance-ids", "required": True},
        ],
    },
    "upload-s3-logs": {
        "name": "Upload S3 Logs",
        "description": "Upload compressed log archives to S3 with a configurable prefix.",
        "env": ["BACKUP_S3", "SRC_DIR", "S3_PREFIX", "SERVICE_NAME (optional)", "AWS_REGION (optional)"],
        "inputs": [],
    },
    "add-certificate-lb": {
        "name": "Add Certificate To LB",
        "description": "Attach an ACM certificate to HTTPS listeners on load balancers.",
        "env": ["DOMAIN (or pass as arg)", "AWS region from CLI config"],
        "inputs": [{"name": "domain", "required": True}],
    },
    "compare-yml": {
        "name": "Compare Yml",
        "description": "Compare nodegroup-name values between prod and DR helm values directories.",
        "inputs": [
            {"name": "prod-dir", "required": True},
            {"name": "dr-dir", "required": True},
        ],
    },
    "route53-domain-creation": {
        "name": "Route53 Domain Creation",
        "description": "Create Route53 CNAME records from a CSV file.",
        "env": ["DOMAIN_COLUMN (default: domain)", "ALB_COLUMN (default: alb_endpoint)"],
        "inputs": [{"name": "records-csv", "required": True}],
    },
    "ensure-lb-peering-routes": {
        "name": "Ensure LB Peering Routes",
        "description": "Verify and optionally add peering routes for load balancer subnets.",
        "env": ["AWS_REGION or REGION"],
        "inputs": [{"name": "target-cidr", "required": True}],
    },
    "asg-git-urls": {
        "name": "ASG Git URLs",
        "description": "Extract git URLs from Auto Scaling group user data.",
        "env": ["ASG_FILE (optional alternative to arg)"],
        "inputs": [{"name": "asg-list", "required": True}],
    },
    "run-qualys-for-roles": {
        "name": "Run Qualys For Roles",
        "description": "Assume IAM roles from a file and run the Qualys repair playbook for each.",
        "env": ["ROLE_ARNS_FILE (default: roles.txt)"],
        "inputs": [{"name": "roles-file", "required": False}],
    },
    "check-userdata-bitbucket-asg": {
        "name": "Check Userdata Bitbucket ASG",
        "description": "Find ASGs whose launch template user data contains a search string.",
        "env": ["SEARCH_TEXT"],
        "inputs": [],
    },
    "check-userdata-for-bitbucket": {
        "name": "Check Userdata For Bitbucket",
        "description": "Find EC2 instances whose user data contains a search string.",
        "env": ["SEARCH_TEXT"],
        "inputs": [],
    },
    "batch-start-linux-ami-patch-automation": {
        "name": "Batch Start Linux AMI Patch Automation",
        "description": "Start SSM automation for AMI patching across ASGs listed in a file.",
        "env": [
            "SSM_AUTOMATION_DOCUMENT",
            "AUTOMATION_ASSUME_ROLE_ARN (optional)",
            "AWS_REGION (optional)",
            "IAM_INSTANCE_PROFILE_NAME (optional)",
        ],
        "inputs": [{"name": "asg-list", "required": True}],
    },
    "iam-policy-update-multiple-accounts": {
        "name": "IAM Policy Update Multiple Accounts",
        "description": "Update inline IAM policy across multiple AWS accounts via SSO helper.",
        "env": ["POLICY_NAME", "SSO_HELPER_SCRIPT", "IAM_ROLE"],
        "inputs": [],
    },
    "check-asg-for-qualys-cortex-dashboard": {
        "name": "Check ASG For Qualys Cortex Dashboard",
        "description": "Verify Qualys/Cortex agents on IPs from a list file.",
        "env": [
            "SSH_KEY_DIR",
            "ACTIVATION_IDS_FILE (default: activation-ids.txt)",
            "DIST_IDS_FILE (default: dist-ids.txt)",
        ],
        "inputs": [{"name": "ips-file", "required": True}],
    },
    "cortex-qualys-siem-integration": {
        "name": "Cortex Qualys SIEM Integration",
        "description": "Install/configure Cortex, Qualys, and SIEM forwarding from env or config file.",
        "env": [
            "CONFIG_FILE (optional arg)",
            "SIEM_FORWARD_HOST",
            "NEXUS_BASE_URL",
            "QUALYS_SERVER_URI",
            "QUALYS_CUSTOMER_ID",
            "CORTEX_VALID_IDS",
            "ACTIVATION_IDS_JSON",
        ],
        "inputs": [{"name": "config-file", "required": False}],
    },
    "intenralbusiness": {
        "name": "Internal Business Build",
        "description": "Android build upload pipeline with optional S3 and Google Play publishing.",
        "env": [
            "S3_ANDROID_BUILDS_BUCKET (optional)",
            "S3_ANDROID_BUILDS_REGION or AWS_REGION",
            "GPLAY_SERVICE_ACCOUNT",
            "GPLAY_PACKAGE_NAME",
            "GPLAY_KEY_FILE",
        ],
        "inputs": [],
    },
    "manage-devadmin": {
        "name": "Manage Devadmin",
        "description": "Manage devadmin users across servers using team API and SSH.",
        "env": ["API_BASE_URL", "AWS_REGION (optional)"],
        "inputs": [],
    },
    "findstaticinstances": {
        "name": "Find Static Instances",
        "description": "List non-ASG EC2 instances in a region.",
        "env": ["AWS_REGION or REGION"],
        "inputs": [],
    },
    "list-static-ips": {
        "name": "List Static IPs",
        "description": "Export non-ASG EC2 instances to CSV.",
        "env": ["AWS_REGION or REGION"],
        "inputs": [{"name": "output-file", "required": False}],
    },
    "addpatchclasstag": {
        "name": "Add Patch Class Tag",
        "description": "Add patch class tags to instances.",
        "env": ["AWS_REGION or REGION"],
        "inputs": [],
    },
    "change-userdata": {
        "name": "Change Userdata",
        "description": "Update EC2 user data.",
        "env": ["AWS_REGION or REGION"],
        "inputs": [],
    },
    "check-asg-for-qualys-cortex": {
        "name": "Check ASG For Qualys Cortex",
        "description": "Verify Qualys/Cortex on target IPs.",
        "env": ["AWS_REGION or REGION"],
        "inputs": [{"name": "ips-file", "required": True}],
    },
    "check-user-data-ips": {
        "name": "Check User Data IPs",
        "description": "Check user data on instances from an IP list file.",
        "env": ["AWS_REGION or REGION"],
        "inputs": [{"name": "ips-file", "required": True}],
    },
    "checkunusedvolumes": {
        "name": "Check Unused Volumes",
        "description": "Audit unused EBS volumes, AMIs, snapshots, and security groups.",
        "env": ["AWS_REGION or REGION"],
        "inputs": [],
    },
    "lb-details": {
        "name": "LB Details",
        "description": "Show load balancer details in a region.",
        "env": ["AWS_REGION or REGION"],
        "inputs": [],
    },
    "setup-telegraf": {
        "name": "Setup Telegraf",
        "description": "Install telegraf on servers from a config file.",
        "env": ["AWS_REGION or REGION"],
        "inputs": [{"name": "servers-file", "required": True}],
    },
    "setup-cron": {
        "name": "Setup Cron",
        "description": "Setup cron jobs on remote servers.",
        "env": ["AWS_REGION or REGION", "SSH_USER (optional)"],
        "inputs": [],
    },
    "setup-redis-exporter": {
        "name": "Setup Redis Exporter",
        "description": "Install redis exporter on servers from a list file.",
        "inputs": [{"name": "servers-file", "required": True}],
    },
    "run-commands": {
        "name": "Run Commands",
        "description": "Run commands on servers listed in a config file.",
        "inputs": [{"name": "servers-file", "required": True}],
    },
    "chek-ips-exist": {
        "name": "Check IPs Exist",
        "description": "Verify IPs exist in EC2.",
        "inputs": [{"name": "ips-file", "required": True}],
    },
    "force-cortex-ips": {
        "name": "Force Cortex IPs",
        "description": "Force Cortex reinstall on IPs from a file.",
        "inputs": [{"name": "ips-file", "required": True}],
    },
    "bifercate-asg-static": {
        "name": "Bifurcate ASG Static",
        "description": "Split ASG/static instance lists into output CSV.",
        "inputs": [
            {"name": "input-file", "required": True},
            {"name": "output-file", "required": False},
        ],
    },
    "finalcostopt": {
        "name": "Final Cost Opt",
        "description": "Cost optimization analysis for AWS resources.",
        "env": ["AWS_REGION (or pass region as arg)"],
        "inputs": [{"name": "region", "required": False}],
    },
    "finalcostoptall": {
        "name": "Final Cost Opt All",
        "description": "Cost optimization analysis across AWS resources.",
        "env": ["AWS_REGION (or pass region as arg)"],
        "inputs": [{"name": "region", "required": False}],
    },
    "bitbucket-repos": {
        "name": "Bitbucket Repos",
        "description": "List Bitbucket repositories and access permissions.",
        "env": ["BITBUCKET_EMAIL", "BITBUCKET_TOKEN"],
        "inputs": [],
    },
    "bitbucket-repo-users": {
        "name": "Bitbucket Repo Users",
        "description": "Audit Bitbucket repository user access.",
        "env": ["BITBUCKET_EMAIL", "BITBUCKET_TOKEN"],
        "inputs": [],
    },
    "install-cortex-from-local": {
        "name": "Install Cortex From Local",
        "description": "Install Cortex agent from local packages via SSH.",
        "env": ["config file path as arg", "AWS_REGION", "SSH_KEY_DIR"],
        "inputs": [{"name": "config", "required": True}],
    },
    "install-qualys-from-local": {
        "name": "Install Qualys From Local",
        "description": "Install Qualys agent from local packages via SSH.",
        "env": ["config file path as arg", "AWS_REGION", "SSH_KEY_DIR"],
        "inputs": [{"name": "config", "required": True}],
    },
    "install-qualys-cortex-from-local": {
        "name": "Install Qualys Cortex From Local",
        "description": "Install Qualys and Cortex from local packages via SSH.",
        "env": ["config file path as arg", "AWS_REGION", "SSH_KEY_DIR"],
        "inputs": [{"name": "config", "required": True}],
    },
    "install-cortex-from-s3": {
        "name": "Install Cortex From S3",
        "description": "Install Cortex agent from S3 via SSH.",
        "env": ["S3_BUCKET_PATH", "AWS_REGION", "SSH_KEY_DIR"],
        "inputs": [{"name": "config", "required": True}],
    },
    "install-qualys-from-s3": {
        "name": "Install Qualys From S3",
        "description": "Install Qualys agent from S3 via SSH.",
        "env": ["S3_BUCKET_PATH", "AWS_REGION", "SSH_KEY_DIR"],
        "inputs": [{"name": "config", "required": True}],
    },
    "repair-qualys-from-s3": {
        "name": "Repair Qualys From S3",
        "description": "Repair/reinstall Qualys agent from S3 or local packages.",
        "env": ["S3_BUCKET_PATH", "AWS_REGION", "SSH_KEY_DIR", "QUALYS_LOCAL_PKG_DIR (optional)"],
        "inputs": [{"name": "config", "required": True}],
    },
    "jenkins-bitbucket-ssh-audit": {
        "name": "Jenkins Bitbucket SSH Audit",
        "description": "Audit Jenkins/Bitbucket SSH keys on EC2 instances.",
        "env": ["AWS_REGION", "SSH_KEY_DIR"],
        "inputs": [{"name": "config", "required": True}],
    },
    "cleanup-java": {
        "name": "Cleanup Java",
        "description": "Remove Oracle Java from servers or EC2 instances.",
        "env": ["AWS_REGION (optional)", "PRIORITY_KEY_PREFIXES (optional)"],
        "inputs": [],
    },
    "port-cidr-whitelisting-sg": {
        "name": "Port CIDR Whitelisting SG",
        "description": "Whitelist a CIDR and ports on security groups in a region.",
        "inputs": [
            {"name": "region", "required": True},
            {"name": "cidr", "required": True},
            {"name": "ports-csv", "required": True},
            {"name": "direction", "required": False},
            {"name": "protocol", "required": False},
            {"name": "concurrency", "required": False},
        ],
    },
    "sg-to-csv": {
        "name": "SG To CSV",
        "description": "Export inbound security group rules to CSV.",
        "inputs": [
            {"name": "sg-id", "required": True},
            {"name": "region", "required": True},
        ],
    },
    "fix-tmout": {
        "name": "Fix Tmout",
        "description": "Fix TMOUT readonly issue on remote servers.",
        "inputs": [
            {"name": "fix-username", "required": True},
            {"name": "fix-ssh-key", "required": True},
            {"name": "check-username", "required": True},
            {"name": "check-ssh-key", "required": True},
            {"name": "config-file", "required": False},
        ],
    },
    "backup-ami": {
        "name": "Backup AMI",
        "description": "Backup AMI from IPs in an input file.",
        "inputs": [{"name": "ips-file", "required": True}],
    },
    "restart-pods": {
        "name": "Restart Pods",
        "description": "Restart unhealthy Kubernetes deployments.",
        "inputs": [
            {"name": "namespace", "required": True},
            {"name": "deployment", "required": True},
        ],
    },
}


def to_title(workflow_id: str) -> str:
    return " ".join(w.capitalize() for w in workflow_id.split("-"))


def detect_runtime_and_entrypoint(workflow_dir: Path) -> tuple[str, str]:
    if (workflow_dir / "script.py").exists():
        return "python", "script.py"
    if (workflow_dir / "script.sh").exists():
        return "bash", "script.sh"
    return "bash", "script.sh"


def detect_inputs_from_script(script_path: Path) -> list[dict]:
    if not script_path.exists():
        return []
    text = script_path.read_text(encoding="utf-8", errors="replace")
    inputs: list[dict] = []

    usage = re.search(r"Usage:\s*\$0\s+(.+)", text)
    if usage:
        for arg in re.findall(r"<([^>]+)>", usage.group(1)):
            name = re.sub(r"[^a-z0-9]+", "-", arg.lower()).strip("-") or "arg"
            if not any(i["name"] == name for i in inputs):
                inputs.append({"name": name, "required": True})

    if script_path.suffix == ".sh":
        header = []
        for line in text.splitlines():
            if re.match(r"^\s*(function\s+\w+|[\w-]+\(\)\s*\{)", line):
                break
            header.append(line)
        header_text = "\n".join(header[:50])
        for var, pos in re.findall(r'^([A-Z_][A-Z0-9_]*)="\$\{?(\d+)\}?"', header_text, re.MULTILINE):
            name = var.lower().replace("_", "-")
            idx = int(pos)
            while len(inputs) < idx:
                inputs.append({"name": f"arg{len(inputs)+1}", "required": True})
            inputs[idx - 1] = {"name": name, "required": True}

    if script_path.suffix == ".py":
        if re.search(r"len\(sys\.argv\)\s*!=\s*2", text) and not inputs:
            inputs.append({"name": "file", "required": True})
        if re.search(r"len\(sys\.argv\)\s*!=\s*3", text) and len(inputs) < 2:
            inputs = [
                {"name": "arg1", "required": True},
                {"name": "arg2", "required": True},
            ]

    return inputs[:10]


def quote_yaml(value: str) -> str:
    """Return a YAML-safe quoted string."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_description(base: str, env: list[str] | None) -> str:
    if not env:
        return base
    return f"{base} Required env: {', '.join(env)}."


def render_yaml(
    workflow_id: str,
    name: str,
    description: str,
    runtime: str,
    entrypoint: str,
    inputs: list[dict],
) -> str:
    lines = [
        f"id: {workflow_id}",
        "",
        f"name: {quote_yaml(name)}",
        "",
        f"description: {quote_yaml(description)}",
        "",
        f"runtime: {runtime}",
        "",
        f"entrypoint: {entrypoint}",
        "",
        "version: 1.0.0",
    ]
    if inputs:
        lines.extend(["", "inputs:"])
        for inp in inputs:
            lines.append(f"  - name: {inp['name']}")
            if inp.get("required"):
                lines.append("    required: true")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    updated = 0
    for workflow_dir in sorted(WORKFLOWS.iterdir()):
        if not workflow_dir.is_dir():
            continue
        workflow_id = workflow_dir.name
        runtime, entrypoint = detect_runtime_and_entrypoint(workflow_dir)
        script_path = workflow_dir / entrypoint

        spec = WORKFLOW_SPECS.get(workflow_id, {})
        name = spec.get("name", to_title(workflow_id))
        base_desc = spec.get("description", name)
        description = build_description(base_desc, spec.get("env"))
        inputs = spec.get("inputs")
        if inputs is None:
            inputs = detect_inputs_from_script(script_path)

        yaml_path = workflow_dir / "workflow.yaml"
        yaml_path.write_text(
            render_yaml(workflow_id, name, description, runtime, entrypoint, inputs),
            encoding="utf-8",
        )
        updated += 1

    print(f"Updated {updated} workflow.yaml files")


if __name__ == "__main__":
    main()
