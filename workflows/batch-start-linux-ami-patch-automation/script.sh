#!/usr/bin/env bash
#
# Read Auto Scaling group names from a file, resolve the AMI from each group's
# active launch template, deduplicate AMIs, and start SSM Automation executions
# (fire-and-forget — does not wait for completion).
#
# Instance-related parameters (InstanceType, SubnetId, SecurityGroupIds,
# IamInstanceProfileName) are read from each ASG and its launch template(s),
# unless overridden via environment variables.
#
# Usage:
#   export AWS_PROFILE=... AWS_REGION=ap-south-1   # or use --region
#   export SSM_AUTOMATION_DOCUMENT="YourCustomDocumentName"
#   ./batch_start_linux_ami_patch_automation.sh path/to/asg-names.txt
#
# Required env:
#   SSM_AUTOMATION_DOCUMENT  Name of the SSM Automation document (same account/region).
#
# Optional env (override ASG/launch-template discovery):
#   AUTOMATION_ASSUME_ROLE_ARN
#   IAM_INSTANCE_PROFILE_NAME
#   INCLUDE_PACKAGES
#   INSTANCE_TYPE
#   SUBNET_ID
#   SECURITY_GROUP_IDS       Comma-separated (no spaces)
#   TARGET_AMI_NAME          Optional; omit to use the document default
#   PRE_UPDATE_SCRIPT
#   POST_UPDATE_SCRIPT
#

set -uo pipefail

# ---------------------------------------------------------------------------
# Defaults (override via environment). No hardcoded account/subnet/SG/instance.
# ---------------------------------------------------------------------------
: "${SSM_AUTOMATION_DOCUMENT:?export SSM_AUTOMATION_DOCUMENT to your automation document name}"

AUTOMATION_ASSUME_ROLE_ARN="${AUTOMATION_ASSUME_ROLE_ARN:-}"
IAM_INSTANCE_PROFILE_NAME="${IAM_INSTANCE_PROFILE_NAME:-}"
INCLUDE_PACKAGES="${INCLUDE_PACKAGES:-all}"
INSTANCE_TYPE="${INSTANCE_TYPE:-}"
SUBNET_ID="${SUBNET_ID:-}"
SECURITY_GROUP_IDS="${SECURITY_GROUP_IDS:-}"
TARGET_AMI_NAME="${TARGET_AMI_NAME:-}"
PRE_UPDATE_SCRIPT="${PRE_UPDATE_SCRIPT:-none}"
POST_UPDATE_SCRIPT="${POST_UPDATE_SCRIPT:-none}"

# StringMap: single-line JSON string (passed through to the document as StringMap)
METADATA_OPTIONS_JSON="${METADATA_OPTIONS_JSON:-{\"HttpEndpoint\":\"enabled\",\"HttpTokens\":\"required\",\"HttpPutResponseHopLimit\":2}}"

EXCLUDE_PACKAGES="${EXCLUDE_PACKAGES:-openjdk*,telegraf,kibana,*corretto*,nodejs,elasticsearch,redis*,kafka,logstash,bind9,filebeat,docker*,containerd,nginx*,mysql*,mariadb*,postgresql*,tomcat*,jenkins}"

# ---------------------------------------------------------------------------

die() { echo "$*" >&2; exit 1; }

ASG_FILE="${1:-}"
[[ -n "$ASG_FILE" ]] || die "Usage: $0 <asg-names.txt>"
[[ -f "$ASG_FILE" ]] || die "File not found: $ASG_FILE"

command -v aws >/dev/null 2>&1 || die "aws CLI not found"
command -v jq >/dev/null 2>&1 || die "jq is required (brew install jq / apt install jq)"

# First non-empty subnet from ASG VPCZoneIdentifier (comma-separated).
first_subnet_from_asg_json() {
  echo "$1" | jq -r '
    .AutoScalingGroups[0].VPCZoneIdentifier
    | split(",")
    | map(gsub("^\\s+|\\s+$"; ""))
    | map(select(length > 0))
    | .[0] // empty
  '
}

# Instance type from MixedInstancesPolicy override row matching LaunchTemplateId (optional).
instance_type_from_mip_override() {
  local asg_json="$1" lt_id="$2"
  echo "$asg_json" | jq -r --arg id "$lt_id" '
    .AutoScalingGroups[0].MixedInstancesPolicy.Overrides[]?
    | select(.LaunchTemplateSpecification.LaunchTemplateId == $id)
    | .InstanceType // empty
    ' | head -n1
}

# From one launch-template version JSON: ImageId, InstanceType, SGs, IAM profile name.
# Security groups: LaunchTemplateData.SecurityGroupIds, else union of NetworkInterfaces[].Groups.
_ami_from_lt_version() {
  local id="$1" ver="$2"
  [[ -z "$ver" || "$ver" == "null" ]] && ver='$Latest'
  aws ec2 describe-launch-template-versions \
    --launch-template-id "$id" \
    --versions "$ver" \
    --output json 2>/dev/null
}

_extract_from_lt_version_json() {
  local lt_json="$1"

  echo "$lt_json" | jq -r '
    .LaunchTemplateVersions[0].LaunchTemplateData as $d |
    ($d.ImageId // empty) as $ami |
    ($d.InstanceType // empty) as $itype |
    (
      if ($d.SecurityGroupIds // [] | length) > 0 then
        $d.SecurityGroupIds
      else
        [ $d.NetworkInterfaces[]? | .Groups[]? ] | flatten | unique
      end
    ) as $sgs |
    (
      (($d.IamInstanceProfile // {}) | .Name // empty) as $n |
      if ($n | length) > 0 then $n
      else
        (($d.IamInstanceProfile // {}) | .Arn // "" | if length > 0 then split("/") | .[-1] else empty end)
      end
    ) as $prof |
    [$ami, $itype, ($sgs | join(",")), $prof] | @tsv
  '
}

# Resolve instance type: launch template first, else MixedInstancesPolicy override for this LT id.
_resolve_instance_type() {
  local asg_json="$1" lt_id="$2" lt_ver="$3" itype_from_lt="$4"
  local mip_type
  if [[ -n "$itype_from_lt" && "$itype_from_lt" != "null" ]]; then
    echo "$itype_from_lt"
    return
  fi
  mip_type=$(instance_type_from_mip_override "$asg_json" "$lt_id")
  if [[ -n "$mip_type" && "$mip_type" != "null" ]]; then
    echo "$mip_type"
    return
  fi
  echo ""
}

# For ASG: print lines "ami<TAB>instance_type<TAB>subnet_id<TAB>sg_csv<TAB>iam_profile"
# One line per distinct AMI from primary launch template and MixedInstancesPolicy overrides.
emit_instance_rows_for_asg() {
  local asg="$1"
  local json lt_id lt_ver n i ovr_ids ovr_vers ami itype lt_json row ami_part itype_part sg_part prof_part

  json=$(aws autoscaling describe-auto-scaling-groups \
    --auto-scaling-group-names "$asg" \
    --output json 2>/dev/null) || {
    echo "$0: describe-auto-scaling-groups failed for: $asg" >&2
    return 1
  }

  local group_count
  group_count=$(echo "$json" | jq '.AutoScalingGroups | length')
  if [[ "$group_count" -eq 0 ]]; then
    echo "$0: no such Auto Scaling group: $asg" >&2
    return 1
  fi

  local subnet
  subnet=$(first_subnet_from_asg_json "$json")
  if [[ -z "$subnet" || "$subnet" == "null" ]]; then
    echo "$0: ASG $asg has no subnets in VPCZoneIdentifier" >&2
    return 1
  fi

  lt_id=$(echo "$json" | jq -r '.AutoScalingGroups[0].LaunchTemplate.LaunchTemplateId // empty')
  lt_ver=$(echo "$json" | jq -r '.AutoScalingGroups[0].LaunchTemplate.Version // empty')

  if [[ -z "$lt_id" || "$lt_id" == "null" ]]; then
    lt_id=$(echo "$json" | jq -r '.AutoScalingGroups[0].MixedInstancesPolicy.LaunchTemplate.LaunchTemplateSpecification.LaunchTemplateId // empty')
    lt_ver=$(echo "$json" | jq -r '.AutoScalingGroups[0].MixedInstancesPolicy.LaunchTemplate.LaunchTemplateSpecification.Version // empty')
  fi

  if [[ -z "$lt_id" || "$lt_id" == "null" ]]; then
    echo "$0: ASG $asg has no LaunchTemplate / MixedInstancesPolicy launch template" >&2
    return 1
  fi

  _emit_one_lt() {
    local lid="$1" lver="$2"
    lt_json=$(_ami_from_lt_version "$lid" "$lver")
    if [[ -z "$lt_json" ]]; then
      echo "$0: describe-launch-template-versions failed for $lid" >&2
      return 1
    fi
    row=$(_extract_from_lt_version_json "$lt_json")
    IFS=$'\t' read -r ami_part itype_part sg_part prof_part <<<"$row"
    itype=$(_resolve_instance_type "$json" "$lid" "$lver" "$itype_part")
    if [[ -z "$ami_part" || "$ami_part" == "None" ]]; then
      return 0
    fi
    if [[ -z "$itype" ]]; then
      echo "$0: could not resolve InstanceType for ASG $asg launch template $lid (set INSTANCE_TYPE to override)" >&2
      return 1
    fi
    if [[ -z "$sg_part" ]]; then
      echo "$0: no security groups on launch template $lid for ASG $asg (set SECURITY_GROUP_IDS to override)" >&2
      return 1
    fi
    if [[ -z "$prof_part" ]]; then
      echo "$0: no IamInstanceProfile on launch template $lid for ASG $asg (set IAM_INSTANCE_PROFILE_NAME to override)" >&2
      return 1
    fi
    printf '%s\t%s\t%s\t%s\t%s\n' "$ami_part" "$itype" "$subnet" "$sg_part" "$prof_part"
  }

  _emit_one_lt "$lt_id" "$lt_ver" || return 1

  n=$(echo "$json" | jq '.AutoScalingGroups[0].MixedInstancesPolicy.Overrides // [] | length')
  for ((i = 0; i < n; i++)); do
    ovr_ids=$(echo "$json" | jq -r ".AutoScalingGroups[0].MixedInstancesPolicy.Overrides[$i].LaunchTemplateSpecification.LaunchTemplateId // empty")
    ovr_vers=$(echo "$json" | jq -r ".AutoScalingGroups[0].MixedInstancesPolicy.Overrides[$i].LaunchTemplateSpecification.Version // empty")
    if [[ -n "$ovr_ids" && "$ovr_ids" != "null" ]]; then
      _emit_one_lt "$ovr_ids" "$ovr_vers" || return 1
    fi
  done
}

# Build JSON parameters object for start-automation-execution
build_params_json() {
  local source_ami="$1"
  local inst_type="$2"
  local sub_id="$3"
  local sg_csv="$4"
  local iam_prof="$5"
  local role_arn="$6"
  local sg_array_json
  sg_array_json=$(
    echo "$sg_csv" | tr ',' '\n' |
      sed 's/^[[:space:]]*//;s/[[:space:]]*$//;/^$/d' |
      jq -R . | jq -s .
  )

  jq -n \
    --arg src "$source_ami" \
    --arg role "$role_arn" \
    --arg prof "$iam_prof" \
    --arg inc "$INCLUDE_PACKAGES" \
    --arg inst "$inst_type" \
    --arg sub "$sub_id" \
    --arg name "$TARGET_AMI_NAME" \
    --arg pre "$PRE_UPDATE_SCRIPT" \
    --arg post "$POST_UPDATE_SCRIPT" \
    --arg ex "$EXCLUDE_PACKAGES" \
    --arg meta "$METADATA_OPTIONS_JSON" \
    --argjson sgs "$sg_array_json" \
    '{
      SourceAmiId: [$src],
      AutomationAssumeRole: (if ($role | length) > 0 then [$role] else [] end),
      IamInstanceProfileName: [$prof],
      IncludePackages: [$inc],
      InstanceType: [$inst],
      SubnetId: [$sub],
      SecurityGroupIds: $sgs,
      PreUpdateScript: [$pre],
      PostUpdateScript: [$post],
      ExcludePackages: [$ex],
      MetadataOptions: [$meta]
    }
    + (if ($name | length) > 0 then {TargetAmiName: [$name]} else {} end)'
}

start_one_automation() {
  local ami="$1"
  local inst_type="$2"
  local sub_id="$3"
  local sg_csv="$4"
  local iam_prof="$5"
  local role_arn="$6"
  local params tmp out
  params=$(build_params_json "$ami" "$inst_type" "$sub_id" "$sg_csv" "$iam_prof" "$role_arn")
  tmp=$(mktemp)
  echo "$params" >"$tmp"

  echo "Starting automation for AMI=$ami (InstanceType=$inst_type SubnetId=$sub_id) ..."
  if out=$(aws ssm start-automation-execution \
    --document-name "$SSM_AUTOMATION_DOCUMENT" \
    --parameters "file://${tmp}" \
    --output json 2>&1); then
    echo "$out" | jq -r '"  execution: " + .AutomationExecutionId'
  else
    echo "  FAILED: $out" >&2
  fi
  rm -f "$tmp"
}

# Apply optional env overrides to ASG-derived fields.
apply_overrides() {
  local _itype="$1" _sub="$2" _sg="$3" _prof="$4"
  [[ -n "${INSTANCE_TYPE:-}" ]] && _itype="$INSTANCE_TYPE"
  [[ -n "${SUBNET_ID:-}" ]] && _sub="$SUBNET_ID"
  [[ -n "${SECURITY_GROUP_IDS:-}" ]] && _sg="$SECURITY_GROUP_IDS"
  [[ -n "${IAM_INSTANCE_PROFILE_NAME:-}" ]] && _prof="$IAM_INSTANCE_PROFILE_NAME"
  printf '%s\t%s\t%s\t%s\n' "$_itype" "$_sub" "$_sg" "$_prof"
}

SEEN_AMIS_FILE=$(mktemp)
trap 'rm -f "$SEEN_AMIS_FILE"' EXIT
STARTED=0

while IFS= read -r line || [[ -n "$line" ]]; do
  # trim and skip blanks / comments
  asg="${line#"${line%%[![:space:]]*}"}"
  asg="${asg%"${asg##*[![:space:]]}"}"
  [[ -z "$asg" || "$asg" =~ ^# ]] && continue

  echo "=== ASG: $asg ==="
  ROWS_TMP=$(mktemp)
  if ! emit_instance_rows_for_asg "$asg" >"$ROWS_TMP"; then
    echo "  (failed to resolve ASG/launch template context; skipping ASG)" >&2
    rm -f "$ROWS_TMP"
    continue
  fi
  while IFS= read -r _row; do
    [[ -z "$_row" ]] && continue
    IFS=$'\t' read -r ami itype sub_id sg_csv iam_prof <<<"$_row"
    _ov=$(apply_overrides "$itype" "$sub_id" "$sg_csv" "$iam_prof")
    IFS=$'\t' read -r itype sub_id sg_csv iam_prof <<<"$_ov"

    [[ -z "$ami" ]] && continue
    if grep -Fqx "$ami" "$SEEN_AMIS_FILE" 2>/dev/null; then
      echo "  AMI $ami already scheduled — skip duplicate"
      continue
    fi
    echo "$ami" >>"$SEEN_AMIS_FILE"
    start_one_automation "$ami" "$itype" "$sub_id" "$sg_csv" "$iam_prof" "${AUTOMATION_ASSUME_ROLE_ARN:-}"
    STARTED=$((STARTED + 1))
  done < <(sort -u "$ROWS_TMP")
  rm -f "$ROWS_TMP"
done <"$ASG_FILE"

echo "Done. Started $STARTED unique AMI automation run(s)."
