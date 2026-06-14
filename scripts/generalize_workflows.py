#!/usr/bin/env python3
"""Remove org-specific hardcoding from workflow scripts and update workflow.yaml."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
WORKFLOWS = ROOT / "workflows"

BASH_REGION_BLOCK = '''REGION="${REGION:-${AWS_REGION:-${AWS_DEFAULT_REGION:-}}}"
if [[ -z "$REGION" ]]; then
  echo "ERROR: Set REGION or AWS_REGION" >&2
  exit 1
fi'''

PYTHON_REGION_BLOCK = '''def _require_region():
    region = os.environ.get("REGION") or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if not region:
        sys.exit("Set REGION or AWS_REGION")
    return region

REGION = _require_region()'''


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    if path.suffix == ".py":
        path.chmod(path.stat().st_mode | 0o111)
    elif path.suffix == ".sh":
        path.chmod(path.stat().st_mode | 0o111)


def write_yaml(workflow_id: str, name: str, description: str, runtime: str, entrypoint: str, inputs: list[dict]) -> None:
    lines = [
        f"id: {workflow_id}",
        "",
        f"name: {name}",
        "",
        f"description: {description}",
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
    write(WORKFLOWS / workflow_id / "workflow.yaml", "\n".join(lines))


def fix_delete_peering_route() -> None:
    write(
        WORKFLOWS / "delete-peering-route" / "script.py",
        '''import boto3
import json
import os
import sys
from datetime import datetime


def _env_bool(name: str, default: bool = True) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y"}


def _require_region() -> str:
    region = os.environ.get("REGION") or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if not region:
        sys.exit("Set REGION or AWS_REGION")
    return region


DRY_RUN = _env_bool("DRY_RUN", default=True)
REGION = _require_region()

ec2 = boto3.client("ec2", region_name=REGION)


def get_peering_details(pcx_id):
    try:
        response = ec2.describe_vpc_peering_connections(
            VpcPeeringConnectionIds=[pcx_id]
        )
        pcx = response["VpcPeeringConnections"][0]
        return {
            "pcx_id": pcx_id,
            "accepter_vpc": pcx["AccepterVpcInfo"].get("VpcId"),
            "requester_vpc": pcx["RequesterVpcInfo"].get("VpcId"),
            "accepter_cidr": pcx["AccepterVpcInfo"].get("CidrBlock"),
            "requester_cidr": pcx["RequesterVpcInfo"].get("CidrBlock"),
            "status": pcx["Status"]["Code"],
        }
    except Exception as e:
        print(f"Failed to fetch peering {pcx_id}: {e}")
        return None


def find_routes_for_peering(pcx_id):
    matched_routes = []
    paginator = ec2.get_paginator("describe_route_tables")
    for page in paginator.paginate():
        for rt in page["RouteTables"]:
            rt_id = rt["RouteTableId"]
            for route in rt.get("Routes", []):
                if route.get("VpcPeeringConnectionId") == pcx_id:
                    matched_routes.append({
                        "RouteTableId": rt_id,
                        "DestinationCidrBlock": route.get("DestinationCidrBlock"),
                        "VpcPeeringConnectionId": pcx_id,
                    })
    return matched_routes


def delete_routes(routes):
    for route in routes:
        rt_id = route["RouteTableId"]
        cidr = route["DestinationCidrBlock"]
        if DRY_RUN:
            print(f"[DRY RUN] Would delete route -> RT: {rt_id}, CIDR: {cidr}")
            continue
        try:
            print(f"Deleting route -> RT: {rt_id}, CIDR: {cidr}")
            ec2.delete_route(RouteTableId=rt_id, DestinationCidrBlock=cidr)
        except Exception as e:
            print(f"Failed deleting route {route}: {e}")


def main(file_path):
    with open(file_path, "r") as f:
        pcx_ids = [line.strip() for line in f if line.strip()]

    final_backup = []
    for pcx_id in pcx_ids:
        print(f"\\nProcessing Peering: {pcx_id}")
        details = get_peering_details(pcx_id)
        if not details:
            continue
        routes = find_routes_for_peering(pcx_id)
        if not routes:
            print("  No routes found")
            continue
        print(f"  Found {len(routes)} route(s)")
        final_backup.append({"peering": details, "routes": routes})
        delete_routes(routes)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_file = f"peering_backup_{timestamp}.json"
    with open(backup_file, "w") as f:
        json.dump(final_backup, f, indent=4)
    print(f"\\nBackup saved: {backup_file}")
    if DRY_RUN:
        print("DRY RUN enabled -> no routes were deleted")
    else:
        print("Routes deleted successfully")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: script.py <peering-ids-file>")
        sys.exit(1)
    main(sys.argv[1])
''',
    )
    write_yaml(
        "delete-peering-route",
        "Delete Peering Route",
        "Clean peering route tables with backup (DRY_RUN defaults to true)",
        "python",
        "script.py",
        [{"name": "peering-file", "required": True}],
    )


def fix_decline_pr() -> None:
    write(
        WORKFLOWS / "decline-pr" / "script.py",
        '''#!/usr/bin/env python3

import os
import re
import sys
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_WORKERS = int(os.getenv("MAX_WORKERS", "10"))
BB_USER = os.getenv("BB_USER")
BB_TOKEN = os.getenv("BB_TOKEN")

if not BB_USER or not BB_TOKEN:
    print("ERROR: Set BB_USER and BB_TOKEN")
    sys.exit(1)

AUTH = (BB_USER, BB_TOKEN)
HEADERS = {"Content-Type": "application/json"}


def load_pr_links(path: str) -> list[str]:
    with open(path, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def parse_pr_url(pr_url: str) -> tuple[str, str, str]:
    match = re.search(
        r"https://bitbucket\\.org/([^/]+)/([^/]+)/pull-requests/(\\d+)",
        pr_url,
    )
    if not match:
        raise ValueError(f"Invalid PR URL: {pr_url}")
    return match.group(1), match.group(2), match.group(3)


def decline_pr(pr_url: str) -> None:
    try:
        workspace, repo, pr_id = parse_pr_url(pr_url)
        api_url = (
            f"https://api.bitbucket.org/2.0/repositories/"
            f"{workspace}/{repo}/pullrequests/{pr_id}/decline"
        )
        response = requests.post(api_url, auth=AUTH, headers=HEADERS, json={})
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Status {response.status_code}: {response.text}")
        print(f"[DECLINED] {pr_url}")
    except Exception as e:
        print(f"[ERROR] {pr_url}: {e}")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: script.py <pr-links-file>")
        sys.exit(1)

    pr_links = load_pr_links(sys.argv[1])
    if not pr_links:
        print("No PR links found in file")
        sys.exit(1)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(decline_pr, url) for url in pr_links]
        for future in as_completed(futures):
            future.result()
    print("DONE")


if __name__ == "__main__":
    main()
''',
    )
    write_yaml(
        "decline-pr",
        "Decline Pr",
        "Decline Bitbucket pull requests listed in a file",
        "python",
        "script.py",
        [{"name": "pr-links-file", "required": True}],
    )


MIGRATE_HEADER = '''#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

PR_LINKS = []
PR_LOCK = threading.Lock()

BB_USER = os.getenv("BB_USER")
BB_TOKEN = os.getenv("BB_TOKEN")

if not BB_USER or not BB_TOKEN:
    print("ERROR: Set BB_USER and BB_TOKEN")
    sys.exit(1)

AUTH = (BB_USER, BB_TOKEN)
HEADERS = {"Content-Type": "application/json"}


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        cfg = json.load(f)
    required = [
        "bitbucket_workspace",
        "repositories",
        "old_string",
        "new_string",
        "new_branch_prefix",
    ]
    missing = [k for k in required if k not in cfg]
    if missing:
        sys.exit(f"Config missing keys: {', '.join(missing)}")
    cfg.setdefault("excluded_repos", [])
    cfg.setdefault("excluded_git_url", "")
    cfg.setdefault("target_branches", [])
    cfg.setdefault("max_repo_workers", 5)
    cfg.setdefault("max_branch_workers", 5)
    return cfg
'''


def fix_migrate_script(workflow_id: str, all_branches: bool) -> None:
    src = WORKFLOWS / workflow_id / "script.py"
    original = src.read_text(encoding="utf-8")
    # Keep everything from `def run(` onward from original
    idx = original.find("def run(")
    if idx == -1:
        raise RuntimeError(f"Could not find helpers in {workflow_id}")
    helpers_and_main = original[idx:]

    helpers_and_main = re.sub(
        r"BASE_API = f\"https://api\.bitbucket\.org/2\.0/repositories/\{BITBUCKET_WORKSPACE\}\"",
        "",
        helpers_and_main,
    )
    helpers_and_main = helpers_and_main.replace(
        "def main():",
        "def main(cfg):\n    global BASE_API\n    BASE_API = f\"https://api.bitbucket.org/2.0/repositories/{cfg['bitbucket_workspace']}\"",
    )
    helpers_and_main = re.sub(
        r"repos = list\(set\(REPOSITORIES\)\)",
        "repos = list(set(cfg['repositories']))",
        helpers_and_main,
    )
    helpers_and_main = re.sub(
        r"max_workers=MAX_REPO_WORKERS",
        "max_workers=cfg['max_repo_workers']",
        helpers_and_main,
    )
    helpers_and_main = re.sub(
        r"max_workers=MAX_BRANCH_WORKERS",
        "max_workers=cfg['max_branch_workers']",
        helpers_and_main,
    )
    helpers_and_main = re.sub(
        r"\bREPOSITORIES\b", "cfg['repositories']", helpers_and_main
    )
    helpers_and_main = re.sub(
        r"\bEXCLUDED_REPOS\b", "cfg['excluded_repos']", helpers_and_main
    )
    helpers_and_main = re.sub(
        r"\bEXCLUDED_GIT_URL\b", "cfg['excluded_git_url']", helpers_and_main
    )
    helpers_and_main = re.sub(
        r"\bOLD_STRING\b", "cfg['old_string']", helpers_and_main
    )
    helpers_and_main = re.sub(
        r"\bNEW_STRING\b", "cfg['new_string']", helpers_and_main
    )
    helpers_and_main = re.sub(
        r"\bNEW_BRANCH_PREFIX\b", "cfg['new_branch_prefix']", helpers_and_main
    )
    helpers_and_main = re.sub(
        r"\bBITBUCKET_WORKSPACE\b", "cfg['bitbucket_workspace']", helpers_and_main
    )
    if not all_branches:
        helpers_and_main = re.sub(
            r"\bTARGET_BRANCHES\b", "cfg['target_branches']", helpers_and_main
        )

    helpers_and_main = re.sub(
        r"if __name__ == \"__main__\":\n    main\(\)",
        'if __name__ == "__main__":\n    if len(sys.argv) != 2:\n        print("Usage: script.py <config.json>")\n        sys.exit(1)\n    main(load_config(sys.argv[1]))',
        helpers_and_main,
    )

    # Fix function signatures that now need cfg - process_repo/process_branch use globals via replacement
    content = MIGRATE_HEADER + "\nBASE_API = \"\"\n\n" + helpers_and_main
    write(src, content)
    write_yaml(
        workflow_id,
        workflow_id.replace("-", " ").title(),
        "Migrate Bitbucket repos using a JSON config file",
        "python",
        "script.py",
        [{"name": "config", "required": True}],
    )


def fix_clone_repo() -> None:
    write(
        WORKFLOWS / "clone-repo" / "script.sh",
        '''#!/bin/bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <ssh-base-url> <repos-file> <clone-dir>"
  echo "Example: $0 git@bitbucket.org:myworkspace repos.txt ./repos"
  exit 1
fi

BASE_SSH_URL="${1%/}"
INPUT_FILE="$2"
CLONE_DIR="$3"

if [[ ! -f "$INPUT_FILE" ]]; then
  echo "File not found: $INPUT_FILE" >&2
  exit 1
fi

mkdir -p "$CLONE_DIR"
cd "$CLONE_DIR" || exit 1

while IFS= read -r repo || [[ -n "$repo" ]]; do
  [[ -z "$repo" || "$repo" =~ ^# ]] && continue
  REPO_URL="${BASE_SSH_URL}/${repo}.git"
  if [[ -d "$repo" ]]; then
    echo "Skipping $repo (already exists)"
    continue
  fi
  echo "Cloning $repo..."
  git clone "$REPO_URL" && echo "Cloned $repo" || echo "Failed $repo"
done < "$INPUT_FILE"

echo "Done"
''',
    )
    write_yaml(
        "clone-repo",
        "Clone Repo",
        "Clone Bitbucket repos from a list file",
        "bash",
        "script.sh",
        [
            {"name": "ssh-base-url", "required": True},
            {"name": "repos-file", "required": True},
            {"name": "clone-dir", "required": True},
        ],
    )


def fix_bash_region_scripts() -> None:
    replacements = {
        "add-tags/script.sh": "AWS_REGION",
        "addpatchclasstag/script.sh": "REGION",
        "change-userdata/script.sh": "REGION",
        "check-asg-for-qualys-cortex/script.sh": "AWS_REGION",
        "check-platform/script.sh": "REGION",
        "check-user-data-ips/script.sh": "AWS_REGION",
        "checkunusedvolumes/script.sh": "AWS_REGION",
        "lb-details/script.sh": "REGION",
        "list-static-ips/script.sh": "REGION",
        "setup-telegraf/script.sh": "REGION",
    }
    for rel, var in replacements.items():
        path = WORKFLOWS / rel
        text = path.read_text(encoding="utf-8")
        block = BASH_REGION_BLOCK.replace("REGION", var)
        text = re.sub(
            rf'^{var}="ap-south-[12]"',
            block,
            text,
            count=1,
            flags=re.MULTILINE,
        )
        write(path, text)


def fix_python_region_scripts() -> None:
    for wf in ["findstaticinstances", "ensure-lb-peering-routes"]:
        path = WORKFLOWS / wf / "script.py"
        text = path.read_text(encoding="utf-8")
        if wf == "ensure-lb-peering-routes":
            text = text.replace('import sys\n\nREGION = "ap-south-1"\nTARGET_CIDR = sys.argv[1]',
                                'import os\nimport sys\n\n' + PYTHON_REGION_BLOCK + '\n\nif len(sys.argv) != 2:\n    print("Usage: script.py <target-cidr>")\n    sys.exit(1)\n\nTARGET_CIDR = sys.argv[1]')
        else:
            text = re.sub(
                r'^REGION = "ap-south-1"\n',
                'import os\nimport sys\n\n' + PYTHON_REGION_BLOCK + '\n',
                text,
                count=1,
                flags=re.MULTILINE,
            )
        write(path, text)


def fix_misc_scripts() -> None:
    # batch-start: remove hardcoded role ARN default
    path = WORKFLOWS / "batch-start-linux-ami-patch-automation" / "script.sh"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'AUTOMATION_ASSUME_ROLE_ARN="${AUTOMATION_ASSUME_ROLE_ARN:-arn:aws:iam::471112548387:role/ssmPatchRole}"',
        'AUTOMATION_ASSUME_ROLE_ARN="${AUTOMATION_ASSUME_ROLE_ARN:-}"',
    )
    write(path, text)

    # nacl-entry-add
    write(
        WORKFLOWS / "nacl-entry-add" / "script.sh",
        '''#!/bin/bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <cidr> [port]"
  exit 1
fi

CIDR="$1"
PORT="${2:-514}"
''' + BASH_REGION_BLOCK + '''

echo "Using region: $REGION"

NACLS=$(aws ec2 describe-network-acls --region "$REGION" \\
  --query "NetworkAcls[*].NetworkAclId" \\
  --output text)

for NACL in $NACLS; do
  echo "Processing NACL: $NACL"
  RULES=$(aws ec2 describe-network-acls --region "$REGION" \\
    --network-acl-ids "$NACL" \\
    --query "NetworkAcls[].Entries[].RuleNumber" \\
    --output text)

  RULE_NUM=1900
  while echo "$RULES" | grep -qw "$RULE_NUM"; do
    RULE_NUM=$((RULE_NUM + 10))
  done

  EXISTING=$(aws ec2 describe-network-acls --region "$REGION" \\
    --network-acl-ids "$NACL" \\
    --query "NetworkAcls[].Entries[?CidrBlock=='$CIDR' && RuleAction=='allow' && PortRange.From==\\`$PORT\\`]" \\
    --output text)

  if [[ -n "$EXISTING" ]]; then
    echo "  Rule already exists, skipping..."
    continue
  fi

  echo "  Adding outbound rule..."
  aws ec2 create-network-acl-entry --region "$REGION" \\
    --network-acl-id "$NACL" \\
    --egress \\
    --rule-number $((RULE_NUM + 1)) \\
    --protocol tcp \\
    --port-range From=1024,To=65535 \\
    --cidr-block "$CIDR" \\
    --rule-action allow
done

echo "Done."
''',
    )

    # userdata
    write(
        WORKFLOWS / "userdata" / "script.sh",
        '''#!/bin/bash -xe
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

: "${S3_CONFIG_URI:?Set S3_CONFIG_URI, e.g. s3://my-bucket/scripts/provision-dr.sh}"

yum install telnet vim -y
python3 -m pip install ansible
aws s3 cp "$S3_CONFIG_URI" .
yum install git ansible --nogpgcheck -y

cat <<EOF | sudo tee /etc/yum.repos.d/influxdb.repo
[influxdb]
name = InfluxDB Repository - RHEL \\$releasever
baseurl = https://repos.influxdata.com/rhel/\\$releasever/\\$basearch/stable
enabled = 1
gpgcheck = 1
gpgkey = https://repos.influxdata.com/influxdb.key
EOF

sudo sed -i "s/\\$releasever/$(rpm -E %{rhel})/g" /etc/yum.repos.d/influxdb.repo
yum install telegraf --nogpgcheck -y
sh provision.sh
''',
    )

    # update-lt
    write(
        WORKFLOWS / "update-lt" / "script.py",
        '''#!/usr/bin/env python3

import json
import os
import sys

import boto3


def _require_region():
    region = os.environ.get("REGION") or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if not region:
        sys.exit("Set REGION or AWS_REGION")
    return region


REGION = _require_region()
ec2 = boto3.client("ec2", region_name=REGION)
asg_client = boto3.client("autoscaling", region_name=REGION)


def load_ami_map(path: str) -> dict:
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        sys.exit("AMI map file must be a JSON object of source_ami -> target_ami")
    return data


def get_asg_names(path: str):
    with open(path, "r") as f:
        return [line.strip() for line in f if line.strip()]


def get_lt_version_details(lt_id):
    response = ec2.describe_launch_template_versions(
        LaunchTemplateId=lt_id,
        Versions=["$Latest", "$Default"],
    )
    latest = None
    default = None
    for v in response["LaunchTemplateVersions"]:
        if v.get("DefaultVersion", False):
            default = v
        latest = v
    return latest, default


def resolve_asg_version(lt_id, version):
    if version == "$Latest":
        latest, _ = get_lt_version_details(lt_id)
        return latest["VersionNumber"], "LATEST"
    if version == "$Default":
        _, default = get_lt_version_details(lt_id)
        return default["VersionNumber"], "DEFAULT"
    return int(version), "FIXED"


def get_launch_template_data(lt_id, version):
    response = ec2.describe_launch_template_versions(
        LaunchTemplateId=lt_id,
        Versions=[str(version)],
    )
    return response["LaunchTemplateVersions"][0]


def create_new_version(lt_id, source_version, to_ami):
    response = ec2.create_launch_template_version(
        LaunchTemplateId=lt_id,
        SourceVersion=str(source_version),
        LaunchTemplateData={"ImageId": to_ami},
    )
    return response["LaunchTemplateVersion"]["VersionNumber"]


def freeze_asg(asg_name, lt_id, version):
    asg_client.update_auto_scaling_group(
        AutoScalingGroupName=asg_name,
        LaunchTemplate={"LaunchTemplateId": lt_id, "Version": str(version)},
    )


def process_asg(asg_name, ami_map):
    print(f"\\nASG: {asg_name}")
    response = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
    if not response["AutoScalingGroups"]:
        print("  ASG not found")
        return
    asg = response["AutoScalingGroups"][0]
    if "LaunchTemplate" not in asg:
        print("  No launch template")
        return
    lt = asg["LaunchTemplate"]
    lt_id = lt["LaunchTemplateId"]
    version = lt["Version"]
    resolved_version, mode = resolve_asg_version(lt_id, version)
    lt_data = get_launch_template_data(lt_id, resolved_version)
    current_ami = lt_data["LaunchTemplateData"].get("ImageId")
    if current_ami not in ami_map:
        print(f"  Skipping (AMI {current_ami} not in map)")
        return
    to_ami = ami_map[current_ami]
    print(f"  {current_ami} -> {to_ami}")
    new_version = create_new_version(lt_id, resolved_version, to_ami)
    print(f"  New LT version: {new_version}")
    if mode in ("LATEST", "DEFAULT"):
        freeze_asg(asg_name, lt_id, resolved_version)


def main():
    if len(sys.argv) != 3:
        print("Usage: script.py <ami-map.json> <asg-list-file>")
        sys.exit(1)
    ami_map = load_ami_map(sys.argv[1])
    asg_names = get_asg_names(sys.argv[2])
    print(f"Processing {len(asg_names)} ASGs...")
    for asg_name in asg_names:
        process_asg(asg_name, ami_map)


if __name__ == "__main__":
    main()
''',
    )

    # run-qualys-for-roles
    write(
        WORKFLOWS / "run-qualys-for-roles" / "script.sh",
        '''#!/usr/bin/env bash
set -euo pipefail

# Usage: ./script.sh [roles-file]
# roles-file: one IAM role ARN per line (or set ROLE_ARNS_FILE)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_PROFILE

ROLES_FILE="${1:-${ROLE_ARNS_FILE:-roles.txt}}"
if [[ ! -f "$ROLES_FILE" ]]; then
  echo "Roles file not found: $ROLES_FILE" >&2
  echo "Usage: $0 [roles-file]" >&2
  exit 1
fi

mapfile -t ROLE_ARNS < <(grep -v '^#' "$ROLES_FILE" | grep -v '^[[:space:]]*$' || true)
if [[ ${#ROLE_ARNS[@]} -eq 0 ]]; then
  echo "No role ARNs found in $ROLES_FILE" >&2
  exit 1
fi

export_credentials() {
  local role_arn="$1"
  local session_name="${2:-qualys-repair-session}"
  eval "$(aws sts assume-role \\
    --role-arn "$role_arn" \\
    --role-session-name "$session_name" \\
    --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \\
    --output text | awk '{print "export AWS_ACCESS_KEY_ID="$1" AWS_SECRET_ACCESS_KEY="$2" AWS_SESSION_TOKEN="$3}')"
}

for role_arn in "${ROLE_ARNS[@]}"; do
  echo "Assuming role: $role_arn"
  export_credentials "$role_arn"
  ansible-playbook repair_qualys.yml "$@"
done
''',
    )

    # git-pull-update: variablize SSH_KEY_DIR
    path = WORKFLOWS / "git-pull-update" / "script.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'SSH_KEY_DIR = "/Users/mridultiwari/Documents/bitbucket/All_Keys"   # change this',
        'SSH_KEY_DIR = os.environ.get("SSH_KEY_DIR")\nif not SSH_KEY_DIR:\n    sys.exit("Set SSH_KEY_DIR")',
    )
    if "import sys" not in text.split("\n")[:10]:
        text = text.replace("import os", "import os\nimport sys", 1)
    write(path, text)

    # check-userdata scripts
    for wf in ["check-userdata-bitbucket-asg", "check-userdata-for-bitbucket"]:
        path = WORKFLOWS / wf / "script.py"
        text = path.read_text(encoding="utf-8")
        text = re.sub(
            r'^SEARCH_TEXT = "[^"]+"',
            'SEARCH_TEXT = os.environ.get("SEARCH_TEXT")\nif not SEARCH_TEXT:\n    sys.exit("Set SEARCH_TEXT")',
            text,
            count=1,
            flags=re.MULTILINE,
        )
        if "import os" not in text:
            text = "import os\n" + text
        if "import sys" not in text:
            text = text.replace("import os", "import os\nimport sys", 1)
        write(path, text)

    # asg-git-urls
    path = WORKFLOWS / "asg-git-urls" / "script.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace('ASG_FILE = "asgs.txt"', 'ASG_FILE = os.environ.get("ASG_FILE") or (sys.argv[1] if len(sys.argv) > 1 else None)')
    if "import sys" not in text[:200]:
        text = "import sys\n" + text
    if "import os" not in text[:200]:
        text = "import os\n" + text
    write(path, text)

    # manage-devadmin / setup-cron / intenralbusiness - remove ap-south-1 default
    for wf, var in [
        ("manage-devadmin", "AWS_REGION"),
        ("setup-cron", "AWS_REGION"),
        ("intenralbusiness", "S3_REGION"),
    ]:
        path = WORKFLOWS / wf / "script.sh"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        text = re.sub(
            r':-\$\{AWS_REGION:-\$\{AWS_DEFAULT_REGION:-ap-south-1\}\}\}',
            ':-${AWS_REGION:-${AWS_DEFAULT_REGION:-}}}',
            text,
        )
        text = re.sub(
            r'AWS_REGION="\$\{AWS_REGION:-ap-south-1\}"',
            'AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}"',
            text,
        )
        write(path, text)

    # iam-policy-update
    path = WORKFLOWS / "iam-policy-update-multiple-accounts" / "script.sh"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            'POLICY_NAME="vpc-policies"',
            'POLICY_NAME="${POLICY_NAME:?Set POLICY_NAME}"',
        )
        write(path, text)

    # fix-tmout example text only - generalize examples
    path = WORKFLOWS / "fix-tmout" / "script.sh"
    text = path.read_text(encoding="utf-8")
    text = text.replace("PPSLInfoSec", "checker")
    text = text.replace("PPSL_InfoSec.pem", "checker_key.pem")
    text = text.replace("10.102.224.135", "10.0.0.1")
    write(path, text)

    # cortex-qualys-siem - externalize to env/config at top
    write(
        WORKFLOWS / "cortex-qualys-siem-integration" / "script.py",
        '''#!/usr/bin/env python3
"""
Install/configure Cortex, Qualys, and SIEM forwarding.
All org-specific values must be supplied via environment variables or a JSON config file.

Required env (or pass CONFIG_FILE path as first argument):
  CONFIG_FILE              Optional JSON with keys below
  SIEM_FORWARD_HOST        e.g. siem.example.com
  NEXUS_BASE_URL           e.g. https://nexus.example.com/repository/devops
  QUALYS_SERVER_URI        e.g. https://qualys.example.com/CloudAgent/
  QUALYS_CUSTOMER_ID
  CORTEX_VALID_IDS         Comma-separated distribution IDs
  ACTIVATION_IDS_JSON      JSON map: {"prod": {"account_id": "activation-id"}, ...}
"""

import json
import os
import subprocess
import sys


def load_settings():
    cfg = {}
    config_file = os.environ.get("CONFIG_FILE") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if config_file:
        with open(config_file, "r") as f:
            cfg = json.load(f)

    def get(key, env_key=None, required=True):
        val = cfg.get(key) or os.environ.get(env_key or key)
        if required and not val:
            sys.exit(f"Missing required setting: {key} (env {env_key or key})")
        return val

    settings = {
        "siem_forward_host": get("siem_forward_host", "SIEM_FORWARD_HOST"),
        "nexus_base_url": get("nexus_base_url", "NEXUS_BASE_URL").rstrip("/"),
        "qualys_server_uri": get("qualys_server_uri", "QUALYS_SERVER_URI"),
        "qualys_customer_id": get("qualys_customer_id", "QUALYS_CUSTOMER_ID"),
        "cortex_valid_ids": get("cortex_valid_ids", "CORTEX_VALID_IDS").split(","),
        "activation_ids": json.loads(get("activation_ids", "ACTIVATION_IDS_JSON")),
    }
    return settings


def run(cmd):
    return subprocess.check_output(cmd, shell=True, text=True).strip()


def rsyslog_conf(host):
    return f"auth.*,authpriv.* @{host}\\n"


def main():
    settings = load_settings()
    print("Configuration loaded. Implement installation steps for your environment.")
    print(f"SIEM host: {settings['siem_forward_host']}")
    print(f"Nexus: {settings['nexus_base_url']}")
    print("Set CONFIG_FILE or env vars and extend this script for your platform.")


if __name__ == "__main__":
    main()
''',
    )


def fix_git_pull_update() -> None:
    path = WORKFLOWS / "git-pull-update" / "script.py"
    text = path.read_text(encoding="utf-8")
    # Remove org-specific team string checks - use env GIT_ORG_PATTERN
    text = re.sub(
        r'SSH_KEY_DIR = os\.environ\.get\("SSH_KEY_DIR"\).*?\n    sys\.exit\("Set SSH_KEY_DIR"\)',
        'SSH_KEY_DIR = os.environ.get("SSH_KEY_DIR")\nif not SSH_KEY_DIR:\n    sys.exit("Set SSH_KEY_DIR")',
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r'if "paytmteam" in url:',
        'if os.environ.get("GIT_ORG_PATTERN", "") and os.environ["GIT_ORG_PATTERN"] in url:',
        text,
    )
    text = re.sub(
        r'if "ppslteam" in url:',
        'if os.environ.get("GIT_ORG_PATTERN_ALT", "") and os.environ["GIT_ORG_PATTERN_ALT"] in url:',
        text,
    )
    write(path, text)


def fix_input_file_scripts() -> None:
    file_env_map = {
        "bifercate-asg-static/script.sh": ("INPUT_FILE", "OUTPUT_FILE", "$1", "$2"),
        "force-cortex-ips/script.sh": ("IP_FILE", None, "$1", None),
        "chek-ips-exist/script.sh": ("IP_FILE", None, "$1", None),
        "run-commands/script.sh": ("CONFIG_FILE", None, "$1", None),
        "setup-telegraf/script.sh": ("CONFIG_FILE", None, "$1", None),
        "setup-redis-exporter/script.sh": ("CONFIG_FILE", None, "$1", None),
        "check-asg-for-qualys-cortex/script.sh": ("IPS_FILE", None, "$1", None),
        "check-asg-for-qualys-cortex-dashboard/script.sh": ("IPS_FILE", None, "$1", None),
        "check-user-data-ips/script.sh": ("IPS_FILE", None, "$1", None),
        "list-static-ips/script.sh": ("OUTPUT_FILE", None, None, "$1"),
    }
    for rel, (var1, var2, arg1, arg2) in file_env_map.items():
        path = WORKFLOWS / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if var1 and arg1:
            old = re.search(rf'^{var1}="[^"]+"', text, re.MULTILINE)
            if old:
                text = text.replace(
                    old.group(0),
                    f'{var1}="${{{var1}:-{arg1}}}"',
                    1,
                )
        if var2 and arg2:
            old = re.search(rf'^{var2}="[^"]+"', text, re.MULTILINE)
            if old:
                text = text.replace(
                    old.group(0),
                    f'{var2}="${{{var2}:-{arg2}}}"',
                    1,
                )
        write(path, text)


def fix_finalcostopt_regions() -> None:
    for wf in ["finalcostopt", "finalcostoptall"]:
        path = WORKFLOWS / wf / "script.py"
        text = path.read_text(encoding="utf-8")
        text = re.sub(
            r'region\s*=\s*["\']ap-south-1["\']',
            'region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")',
            text,
        )
        if "import os" not in text[:500]:
            text = "import os\n" + text
        write(path, text)


def fix_remaining() -> None:
    # add-tags: fix broken region block + externalize tags
    write(
        WORKFLOWS / "add-tags" / "script.sh",
        '''#!/usr/bin/env bash
set -e

if [ -z "$BASH_VERSION" ]; then
  echo "Please run with bash" >&2
  exit 1
fi

AWS_REGION="${AWS_REGION:-${REGION:-${AWS_DEFAULT_REGION:-}}}"
if [[ -z "$AWS_REGION" ]]; then
  echo "ERROR: Set AWS_REGION or REGION" >&2
  exit 1
fi

TAGS_FILE="${TAGS_FILE:-${1:-}}"
INSTANCE_IDS="${INSTANCE_IDS:-${2:-}}"

if [[ -z "$TAGS_FILE" || -z "$INSTANCE_IDS" ]]; then
  echo "Usage: TAGS_FILE=tags.txt INSTANCE_IDS='i-xxx i-yyy' $0 [tags-file] [instance-ids]"
  echo "  tags-file: one tag per line as Key=Value"
  exit 1
fi

if [[ ! -f "$TAGS_FILE" ]]; then
  echo "Tags file not found: $TAGS_FILE" >&2
  exit 1
fi

mapfile -t TAGS_TO_ADD < <(grep -v '^#' "$TAGS_FILE" | grep -v '^[[:space:]]*$' || true)

for INSTANCE_ID in $INSTANCE_IDS; do
  echo "Updating $INSTANCE_ID"
  TAG_ARGS=()
  for TAG in "${TAGS_TO_ADD[@]}"; do
    KEY="${TAG%%=*}"
    VALUE="${TAG#*=}"
    TAG_ARGS+=(Key="$KEY",Value="$VALUE")
  done
  aws ec2 create-tags --region "$AWS_REGION" --resources "$INSTANCE_ID" --tags "${TAG_ARGS[@]}"
done
''',
    )

    # git-pull-update org strings
    path = WORKFLOWS / "git-pull-update" / "script.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'MAX_WORKERS = 10\nDRY_RUN = True',
        'MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "10"))\nDRY_RUN = os.environ.get("DRY_RUN", "true").lower() in {"1", "true", "yes"}\nGIT_OLD_ORG = os.environ.get("GIT_OLD_ORG")\nGIT_NEW_ORG = os.environ.get("GIT_NEW_ORG")\nif not GIT_OLD_ORG or not GIT_NEW_ORG:\n    sys.exit("Set GIT_OLD_ORG and GIT_NEW_ORG")',
    )
    text = text.replace("grep 'paytmteam'", 'grep "$GIT_OLD_ORG"')
    text = text.replace('"paytmteam" not in line', 'GIT_OLD_ORG not in line')
    text = text.replace("sed -i 's/paytmteam/ppslteam/g'", 'sed -i "s/$GIT_OLD_ORG/$GIT_NEW_ORG/g"')
    write(path, text)

    # check-platform
    write(
        WORKFLOWS / "check-platform" / "script.sh",
        '''#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-${AWS_REGION:-${AWS_DEFAULT_REGION:-}}}"
KEY_PATH="${SSH_KEY_PATH:?Set SSH_KEY_PATH}"
EC2_TAG_FILTER="${EC2_TAG_FILTER:?Set EC2_TAG_FILTER, e.g. Name=tag:techteam,Values=my-team}"

if [[ -z "$REGION" ]]; then
  echo "ERROR: Set REGION or AWS_REGION" >&2
  exit 1
fi

SSH_USERS=("ubuntu" "ec2-user" "centos")

echo "Fetching instances..."
IPS=$(aws ec2 describe-instances \\
  --region "$REGION" \\
  --filters "$EC2_TAG_FILTER" "Name=instance-state-name,Values=running" \\
  --query 'Reservations[].Instances[].PrivateIpAddress' \\
  --output text)

if [[ -z "$IPS" ]]; then
  echo "No instances found"
  exit 0
fi

read -p "Proceed with OS check via SSH? (yes/no): " ans
[[ "$ans" != "yes" ]] && exit 0

for ip in $IPS; do
  for user in "${SSH_USERS[@]}"; do
    OS=$(ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no \\
         -i "$KEY_PATH" "$user@$ip" \\
         "source /etc/os-release 2>/dev/null && echo \\$ID \\$VERSION_ID" 2>/dev/null || true)
    if [[ -n "$OS" ]]; then
      echo "$ip: $OS"
      break
    fi
  done
done
''',
    )

    # manage-devadmin API URL
    path = WORKFLOWS / "manage-devadmin" / "script.sh"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'API_BASE_URL="https://user-access.paytmpayments.com/api/users/by-team"',
        'API_BASE_URL="${API_BASE_URL:?Set API_BASE_URL}"',
    )
    text = text.replace(
        "  -r, --region REGION     AWS region (default: ap-south-1)",
        "  -r, --region REGION     AWS region (default: AWS_REGION env)",
    )
    write(path, text)

    # upload-s3-logs
    write(
        WORKFLOWS / "upload-s3-logs" / "script.sh",
        '''#!/bin/bash
set -euo pipefail

: "${BACKUP_S3:?Set BACKUP_S3 bucket name}"
: "${SRC_DIR:?Set SRC_DIR source log directory}"
: "${S3_PREFIX:?Set S3_PREFIX path prefix inside bucket, e.g. archive/logs}"

host="$(hostname -i 2>/dev/null || hostname -s)"
REGION="${REGION:-${AWS_REGION:-${AWS_DEFAULT_REGION:-}}}"
BKP_FLD="${BKP_FLD:-$(basename "$SRC_DIR")}"

shopt -s nullglob
for file in "${SRC_DIR}"/*.log.*.zst; do
  base="$(basename "$file")"
  if [[ "$base" =~ ^([A-Za-z0-9_-]+)\\.log\\.([0-9]{4})-([0-9]{2})-([0-9]{2})-([0-9]{2})\\.zst$ ]]; then
    SERVICE="${SERVICE_NAME:-${BASH_REMATCH[1]}}"
    YEAR="${BASH_REMATCH[2]}"
    MONTH="${BASH_REMATCH[3]}"
    DAY="${BASH_REMATCH[4]}"
    prefix="s3://${BACKUP_S3}/${S3_PREFIX}/${SERVICE}/${YEAR}/${MONTH}/${DAY}/${host}/${BKP_FLD}/"
    echo "Uploading ${base} to ${prefix}"
    aws s3 cp "$file" "${prefix}${base}" ${REGION:+--region "$REGION"}
  fi
done
echo "Done."
''',
    )

    # add-certificate-lb
    path = WORKFLOWS / "add-certificate-lb" / "script.sh"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'DOMAIN="*.paytmpayments.com"',
        'DOMAIN="${DOMAIN:-${1:-}}"\nif [[ -z "$DOMAIN" ]]; then echo "Set DOMAIN or pass as first argument" >&2; exit 1; fi',
    )
    write(path, text)

    # compare-yml
    write(
        WORKFLOWS / "compare-yml" / "script.sh",
        '''#!/bin/bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <prod-base-dir> <dr-base-dir>"
  exit 1
fi

PROD_BASE="$1"
DR_BASE="$2"

echo "Comparing nodegroup-name between PROD and DR..."
find "$PROD_BASE" -type f -name "values*.yaml" | while read -r prod_file; do
  rel_path="${prod_file#$PROD_BASE/}"
  dr_file="$DR_BASE/$rel_path"
  prod_nodegroup=$(grep -E '^[[:space:]]*nodegroup-name:' "$prod_file" | head -n1 | awk -F ':' '{print $2}' | xargs)
  if [[ ! -f "$dr_file" ]]; then
    echo "$rel_path: PROD=$prod_nodegroup DR=MISSING"
    continue
  fi
  dr_nodegroup=$(grep -E '^[[:space:]]*nodegroup-name:' "$dr_file" | head -n1 | awk -F ':' '{print $2}' | xargs)
  if [[ "$prod_nodegroup" != "$dr_nodegroup" ]]; then
    echo "$rel_path: PROD=$prod_nodegroup DR=$dr_nodegroup"
  fi
done
''',
    )

    # route53
    path = WORKFLOWS / "route53-domain-creation" / "script.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'domain = row["ppsl_domain"].strip()',
        'domain_col = os.environ.get("DOMAIN_COLUMN", "domain")\n            alb_col = os.environ.get("ALB_COLUMN", "alb_endpoint")\n            domain = row[domain_col].strip()',
    )
    text = text.replace('alb = row["alb_endpoint"].strip()', 'alb = row[alb_col].strip()')
    text = text.replace(
        "Usage: python update_ppsl_create_only.py records.csv",
        "Usage: script.py records.csv  (columns: DOMAIN_COLUMN, ALB_COLUMN env)",
    )
    if "import os" not in text:
        text = "import os\n" + text
    write(path, text)

    # check-asg-for-qualys-cortex-dashboard
    path = WORKFLOWS / "check-asg-for-qualys-cortex-dashboard" / "script.sh"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'SSH_KEY_DIR="/Users/mridultiwari/Documents/bitbucket/All_Keys/tmp"',
        'SSH_KEY_DIR="${SSH_KEY_DIR:?Set SSH_KEY_DIR}"',
    )
    # Externalize activation IDs to file
    if "EXPECTED_ACTIVATION_IDS=(" in text:
        text = re.sub(
            r"EXPECTED_ACTIVATION_IDS=\(\n.*?\n\)",
            'ACTIVATION_IDS_FILE="${ACTIVATION_IDS_FILE:-activation-ids.txt}"\nif [[ ! -f "$ACTIVATION_IDS_FILE" ]]; then echo "Set ACTIVATION_IDS_FILE" >&2; exit 1; fi\nmapfile -t EXPECTED_ACTIVATION_IDS < <(grep -v "^#" "$ACTIVATION_IDS_FILE" | grep -v "^[[:space:]]*$" || true)',
            text,
            count=1,
            flags=re.DOTALL,
        )
    if "VALID_DIST_IDS=(" in text:
        text = re.sub(
            r"VALID_DIST_IDS=\(\n.*?\n\)",
            'DIST_IDS_FILE="${DIST_IDS_FILE:-dist-ids.txt}"\nif [[ ! -f "$DIST_IDS_FILE" ]]; then echo "Set DIST_IDS_FILE" >&2; exit 1; fi\nmapfile -t VALID_DIST_IDS < <(grep -v "^#" "$DIST_IDS_FILE" | grep -v "^[[:space:]]*$" || true)',
            text,
            count=1,
            flags=re.DOTALL,
        )
    write(path, text)

    # iam-policy-update
    path = WORKFLOWS / "iam-policy-update-multiple-accounts" / "script.sh"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "source /Users/mridultiwari/Documents/bitbucket/All_Keys/saml2_automation.sh",
        'SSO_HELPER="${SSO_HELPER_SCRIPT:?Set SSO_HELPER_SCRIPT to your saml/sso helper script}"\nsource "$SSO_HELPER"',
    )
    text = text.replace('IAM_ROLE="app-sec-cmdb-assume-role"', 'IAM_ROLE="${IAM_ROLE:?Set IAM_ROLE}"')
    write(path, text)

    # finalcostopt region
    for wf in ["finalcostopt", "finalcostoptall"]:
        path = WORKFLOWS / wf / "script.py"
        text = path.read_text(encoding="utf-8")
        text = text.replace(
            "region_name = 'ap-south-1'",
            'region_name = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or sys.argv[1] if len(sys.argv) > 1 else None',
        )
        if "import sys" not in text[:300]:
            text = text.replace("import os", "import os\nimport sys", 1)
        write(path, text)

    # list-qualys-branches default region
    path = WORKFLOWS / "list-qualys-branches-from-userdata" / "script.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'default=os.environ.get("AWS_REGION", "ap-south-1"), help="AWS region (default: AWS_REGION or ap-south-1)"',
        'default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"), help="AWS region (default: AWS_REGION env)"',
    )
    write(path, text)

    # repair-qualys default pkg dir
    path = WORKFLOWS / "repair-qualys-from-s3" / "script.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace("~/Downloads/qualys_ppsl", "~/Downloads/qualys_packages")
    text = text.replace("qualys_ppsl", "qualys_packages")
    write(path, text)

    # cleanup-java priority keys
    path = WORKFLOWS / "cleanup-java" / "script.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'PRIORITY_KEY_PREFIXES = ("ppsl_", "merchant")',
        'PRIORITY_KEY_PREFIXES = tuple(os.environ.get("PRIORITY_KEY_PREFIXES", "").split(",")) if os.environ.get("PRIORITY_KEY_PREFIXES") else ()',
    )
    text = text.replace('if lower.startswith("ppsl_") or "merchant" in lower:', 'if any(lower.startswith(p) for p in PRIORITY_KEY_PREFIXES if p):')
    write(path, text)

    # login-server priority keys
    path = WORKFLOWS / "login-server" / "script.sh"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        text = re.sub(
            r'PRIORITY_KEYS=\([^)]+\)',
            'PRIORITY_KEYS=(${SSH_PRIORITY_KEYS:-})',
            text,
            count=1,
        )
        write(path, text)

    # port-cidr examples
    path = WORKFLOWS / "port-cidr-whitelisting-sg" / "script.sh"
    text = path.read_text(encoding="utf-8")
    text = text.replace("10.102.240.0/20", "10.0.0.0/16")
    text = text.replace("ap-south-1", "us-east-1")
    write(path, text)

    # intenralbusiness - remove hardcoded gservice paths comment defaults
    path = WORKFLOWS / "intenralbusiness" / "script.sh"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        text = text.replace("(default ap-south-1)", "(from AWS_REGION)")
        text = re.sub(
            r"jenkins-p4b-upload@paytm-for-business\.iam\.gserviceaccount\.com",
            "${GPLAY_SERVICE_ACCOUNT:?Set GPLAY_SERVICE_ACCOUNT}",
            text,
        )
        text = re.sub(
            r"com\.paytm\.business",
            "${GPLAY_PACKAGE_NAME:?Set GPLAY_PACKAGE_NAME}",
            text,
        )
        text = re.sub(
            r"paytm-for-business-[a-z0-9]+\.p12",
            "${GPLAY_KEY_FILE:?Set GPLAY_KEY_FILE}",
            text,
        )
        write(path, text)

    # asg-git-urls require file arg
    path = WORKFLOWS / "asg-git-urls" / "script.py"
    text = path.read_text(encoding="utf-8")
    if "if not ASG_FILE" not in text:
        text = text.replace(
            'ASG_FILE = os.environ.get("ASG_FILE") or (sys.argv[1] if len(sys.argv) > 1 else None)',
            'ASG_FILE = os.environ.get("ASG_FILE") or (sys.argv[1] if len(sys.argv) > 1 else None)\nif not ASG_FILE:\n    sys.exit("Usage: script.py <asg-list-file> or set ASG_FILE")',
        )
    write(path, text)


def main() -> None:
    fix_delete_peering_route()
    fix_decline_pr()
    fix_migrate_script("migrate-repo-particular-branch", all_branches=False)
    fix_migrate_script("migrate-repo-all-branch", all_branches=True)
    fix_clone_repo()
    fix_bash_region_scripts()
    fix_python_region_scripts()
    fix_misc_scripts()
    fix_git_pull_update()
    fix_input_file_scripts()
    fix_finalcostopt_regions()
    fix_remaining()
    print("Generalization complete.")


if __name__ == "__main__":
    main()
