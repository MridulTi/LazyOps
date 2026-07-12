#!/usr/bin/env python3
"""
Trace domain → load balancer → backend EC2 instance IPs.

DNS-first (nslookup), CMDB inventory cross-reference, AWS ELBv2 target health.
"""
from __future__ import annotations

import argparse
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("Missing dependency: requests (pip install requests)", file=sys.stderr)
    sys.exit(1)

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    print("Missing dependency: boto3 (pip install boto3)", file=sys.stderr)
    sys.exit(1)


LB_HOST_RE = re.compile(
    r"\.(elb\.[a-z0-9-]+\.amazonaws\.com|amazonaws\.com)\.?$",
    re.IGNORECASE,
)
CNAME_LINE_RE = re.compile(
    r"(?i)(?:canonical name|alias)\s*[=:]\s*(\S+)",
)
A_LINE_RE = re.compile(
    r"(?i)^name:\s*\S+\s*\n(?:.*\n)*?Address(?:es)?:\s*(\d+\.\d+\.\d+\.\d+)",
    re.MULTILINE,
)
IP_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")


@dataclass
class DnsHop:
    name: str
    record_type: str
    value: str


@dataclass
class BackendTarget:
    target_group: str
    instance_id: str
    private_ip: str
    state: str
    name_tag: str = ""
    patch_class: str = ""
    source: str = "aws"


@dataclass
class TraceResult:
    domain: str
    cmdb_url: str
    dns_chain: list[DnsHop] = field(default_factory=list)
    lb_hostname: str = ""
    lb_ips: list[str] = field(default_factory=list)
    alb_match: dict[str, Any] | None = None
    backends: list[BackendTarget] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cmdb_available: bool = True


def normalize_domain(raw: str) -> str:
    raw = raw.strip()
    if "://" in raw:
        raw = urlparse(raw).netloc or urlparse(raw).path
    raw = raw.split("/")[0].split(":")[0]
    return raw.rstrip(".").lower()


def is_lb_hostname(host: str) -> bool:
    return bool(LB_HOST_RE.search(host.rstrip(".")))


def run_nslookup(name: str) -> str:
    if shutil.which("nslookup"):
        proc = subprocess.run(
            ["nslookup", name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            return proc.stdout
        combined = (proc.stdout or "") + (proc.stderr or "")
        if combined.strip():
            return combined
    if shutil.which("dig"):
        proc = subprocess.run(
            ["dig", "+short", name, "CNAME"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        cname = proc.stdout.strip().splitlines()
        proc_a = subprocess.run(
            ["dig", "+short", name, "A"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        lines = []
        for c in cname:
            if c.strip():
                lines.append(f"canonical name = {c.strip().rstrip('.')}")
        for a in proc_a.stdout.strip().splitlines():
            if a.strip() and re.match(r"^\d", a.strip()):
                lines.append(f"Address: {a.strip()}")
        if lines:
            return "\n".join(lines)
    try:
        infos = socket.getaddrinfo(name, None, proto=socket.IPPROTO_TCP)
        addrs = sorted({item[4][0] for item in infos})
        return "\n".join(f"Address: {a}" for a in addrs)
    except socket.gaierror as exc:
        raise RuntimeError(f"DNS lookup failed for {name}: {exc}") from exc


def parse_nslookup_output(name: str, text: str) -> tuple[str | None, list[str]]:
    cname = None
    ips: list[str] = []
    for m in CNAME_LINE_RE.finditer(text):
        cname = m.group(1).rstrip(".").lower()
    for m in A_LINE_RE.finditer(text):
        ips.append(m.group(1))
    if not ips:
        for line in text.splitlines():
            if "can't find" in line.lower() or "nxdomain" in line.lower():
                continue
            if name.lower() in line.lower() and "address" in line.lower():
                for ip in IP_RE.findall(line):
                    ips.append(ip)
            elif re.match(r"^Address(es)?:\s*", line, re.I):
                for ip in IP_RE.findall(line):
                    ips.append(ip)
    ips = list(dict.fromkeys(ips))
    return cname, ips


def resolve_dns_chain(domain: str, max_depth: int = 10) -> tuple[list[DnsHop], str, list[str]]:
    chain: list[DnsHop] = []
    lb_hostname = ""
    lb_ips: list[str] = []
    current = domain
    seen: set[str] = set()

    for _ in range(max_depth):
        if current in seen:
            break
        seen.add(current)

        try:
            out = run_nslookup(current)
        except RuntimeError as exc:
            if not chain:
                raise
            break

        cname, ips = parse_nslookup_output(current, out)
        if cname:
            chain.append(DnsHop(current, "CNAME", cname))
            if is_lb_hostname(cname):
                lb_hostname = cname
            current = cname
            continue
        if ips:
            chain.append(DnsHop(current, "A", ", ".join(ips)))
            if is_lb_hostname(current):
                lb_hostname = current
                lb_ips = ips
            break
        break

    if lb_hostname and not lb_ips:
        try:
            _, lb_ips = parse_nslookup_output(lb_hostname, run_nslookup(lb_hostname))
        except RuntimeError:
            pass

    return chain, lb_hostname, lb_ips


def cmdb_get(base_url: str, path: str, timeout: int = 60) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_cmdb_albs(base_url: str) -> list[dict[str, Any]]:
    data = cmdb_get(base_url, "/api/alb/")
    return list(data.get("results") or [])


def fetch_cmdb_ec2(base_url: str) -> list[dict[str, Any]]:
    data = cmdb_get(base_url, "/api/ec2/")
    return list(data.get("results") or [])


def fetch_cmdb_route53(base_url: str) -> list[dict[str, Any]]:
    data = cmdb_get(base_url, "/api/route53/")
    return list(data.get("results") or [])


def match_alb_in_cmdb(albs: list[dict], lb_hostname: str) -> dict[str, Any] | None:
    target = lb_hostname.rstrip(".").lower()
    for alb in albs:
        dns = (alb.get("dns_name") or "").rstrip(".").lower()
        if dns == target:
            return alb
    return None


def route53_fallback_domain(
    records: list[dict], domain: str
) -> tuple[str, list[DnsHop]]:
    """Walk CMDB Route53 records when live DNS did not yield an ELB hostname."""
    domain = domain.rstrip(".").lower()
    by_name = {(r.get("name") or "").rstrip(".").lower(): r for r in records}
    extra_chain: list[DnsHop] = []
    current = domain
    seen: set[str] = set()
    for _ in range(10):
        if current in seen:
            break
        seen.add(current)
        rec = by_name.get(current)
        if not rec:
            break
        route_to = (rec.get("route_to") or "").rstrip(".").lower()
        rtype = rec.get("type") or "?"
        extra_chain.append(DnsHop(current, f"CMDB-{rtype}", route_to))
        if is_lb_hostname(route_to):
            return route_to, extra_chain
        if re.match(r"^\d", route_to):
            break
        current = route_to
    return "", extra_chain


def ec2_index(ec2_rows: list[dict]) -> dict[str, dict]:
    return {(r.get("instance_id") or ""): r for r in ec2_rows if r.get("instance_id")}


def find_ec2_by_ip(ec2_rows: list[dict], ip: str) -> dict | None:
    for row in ec2_rows:
        if row.get("private_ip") == ip:
            return row
    return None


def short_tg_name(arn: str) -> str:
    return arn.split("/")[-1] if arn else "unknown"


def resolve_backends_via_aws(
    alb_arn: str,
    region: str,
    ec2_by_id: dict[str, dict],
    warnings: list[str],
) -> list[BackendTarget]:
    backends: list[BackendTarget] = []
    elbv2 = boto3.client("elbv2", region_name=region)
    ec2 = boto3.client("ec2", region_name=region)

    try:
        listeners = elbv2.describe_listeners(LoadBalancerArn=alb_arn).get("Listeners") or []
    except (ClientError, BotoCoreError) as exc:
        warnings.append(f"AWS describe-listeners failed: {exc}")
        return backends

    tg_arns: set[str] = set()
    for listener in listeners:
        for action in listener.get("DefaultActions") or []:
            if action.get("TargetGroupArn"):
                tg_arns.add(action["TargetGroupArn"])
        try:
            rules = elbv2.describe_rules(ListenerArn=listener["ListenerArn"]).get("Rules") or []
        except (ClientError, BotoCoreError):
            continue
        for rule in rules:
            for action in rule.get("Actions") or []:
                if action.get("TargetGroupArn"):
                    tg_arns.add(action["TargetGroupArn"])

    instance_ids: set[str] = set()
    for tg_arn in sorted(tg_arns):
        tg_name = short_tg_name(tg_arn)
        try:
            health = elbv2.describe_target_health(TargetGroupArn=tg_arn).get(
                "TargetHealthDescriptions"
            ) or []
        except (ClientError, BotoCoreError) as exc:
            warnings.append(f"Target health failed for {tg_name}: {exc}")
            continue
        for desc in health:
            target = desc.get("Target") or {}
            iid = target.get("Id") or ""
            if not iid.startswith("i-"):
                continue
            instance_ids.add(iid)
            state = (desc.get("TargetHealth") or {}).get("State") or "unknown"
            cmdb_row = ec2_by_id.get(iid) or {}
            backends.append(
                BackendTarget(
                    target_group=tg_name,
                    instance_id=iid,
                    private_ip=cmdb_row.get("private_ip") or "",
                    state=state,
                    name_tag=cmdb_row.get("name_tag") or "",
                    patch_class=cmdb_row.get("patch_class") or "",
                    source="cmdb+aws" if cmdb_row else "aws",
                )
            )

    missing_ips = [b for b in backends if not b.private_ip]
    if missing_ips:
        try:
            resp = ec2.describe_instances(
                InstanceIds=[b.instance_id for b in missing_ips]
            )
            ip_map: dict[str, str] = {}
            name_map: dict[str, str] = {}
            for res in resp.get("Reservations") or []:
                for inst in res.get("Instances") or []:
                    iid = inst.get("InstanceId") or ""
                    ip_map[iid] = inst.get("PrivateIpAddress") or ""
                    for tag in inst.get("Tags") or []:
                        if tag.get("Key") == "Name":
                            name_map[iid] = tag.get("Value") or ""
            for b in backends:
                if not b.private_ip:
                    b.private_ip = ip_map.get(b.instance_id, "")
                if not b.name_tag:
                    b.name_tag = name_map.get(b.instance_id, "")
        except (ClientError, BotoCoreError) as exc:
            warnings.append(f"EC2 describe-instances failed: {exc}")

    return backends


def trace_domain(
    domain: str,
    cmdb_url: str,
    source: str = "auto",
    region_override: str | None = None,
) -> TraceResult:
    result = TraceResult(domain=domain, cmdb_url=cmdb_url.rstrip("/"))
    use_cmdb = source in ("auto", "cmdb")

    try:
        chain, lb_hostname, lb_ips = resolve_dns_chain(domain)
        result.dns_chain = chain
        result.lb_hostname = lb_hostname
        result.lb_ips = lb_ips
    except RuntimeError as exc:
        result.warnings.append(str(exc))

    albs: list[dict] = []
    ec2_rows: list[dict] = []
    if use_cmdb:
        try:
            albs = fetch_cmdb_albs(cmdb_url)
            ec2_rows = fetch_cmdb_ec2(cmdb_url)
        except requests.RequestException as exc:
            result.cmdb_available = False
            result.warnings.append(f"CMDB unreachable: {exc}")
            if source == "cmdb":
                return result

    if use_cmdb and result.cmdb_available and not result.lb_hostname:
        try:
            r53 = fetch_cmdb_route53(cmdb_url)
            lb_from_r53, r53_chain = route53_fallback_domain(r53, domain)
            result.dns_chain.extend(r53_chain)
            if lb_from_r53:
                result.lb_hostname = lb_from_r53
                result.warnings.append(
                    "LB hostname from CMDB Route53 (live DNS did not expose ELB CNAME)"
                )
        except requests.RequestException as exc:
            result.warnings.append(f"CMDB Route53 lookup failed: {exc}")

    if result.lb_hostname and not result.lb_ips:
        try:
            _, ips = parse_nslookup_output(
                result.lb_hostname, run_nslookup(result.lb_hostname)
            )
            result.lb_ips = ips
        except RuntimeError:
            pass

    if use_cmdb and result.cmdb_available and result.lb_hostname:
        result.alb_match = match_alb_in_cmdb(albs, result.lb_hostname)

    if not result.lb_hostname and result.dns_chain:
        last = result.dns_chain[-1]
        if last.record_type == "A":
            result.warnings.append(
                "Domain resolves to IP(s) without ELB CNAME — may be CDN/edge. "
                "Check CMDB Route53 for internal AWS path."
            )
            if use_cmdb and result.cmdb_available and ec2_rows:
                for ip in last.value.split(","):
                    ip = ip.strip()
                    row = find_ec2_by_ip(ec2_rows, ip)
                    if row:
                        result.backends.append(
                            BackendTarget(
                                target_group="(direct A record)",
                                instance_id=row.get("instance_id") or "",
                                private_ip=row.get("private_ip") or ip,
                                state=row.get("state") or "",
                                name_tag=row.get("name_tag") or "",
                                patch_class=row.get("patch_class") or "",
                                source="cmdb",
                            )
                        )

    if result.alb_match:
        region = region_override or result.alb_match.get("region") or ""
        alb_arn = result.alb_match.get("arn") or ""
        if region and alb_arn and source != "cmdb":
            ec2_by_id = ec2_index(ec2_rows)
            result.backends = resolve_backends_via_aws(
                alb_arn, region, ec2_by_id, result.warnings
            )
        elif source != "cmdb" and not region:
            result.warnings.append("CMDB ALB match missing region; pass --region")

    elif result.lb_hostname and source == "aws":
        result.warnings.append(
            "AWS-only mode without CMDB ALB ARN — install CMDB access or use --source auto"
        )

    return result


def print_trace(result: TraceResult) -> None:
    print(f"=== Trace: {result.domain} ===")
    print(f"CMDB: {result.cmdb_url}")
    print(f"  UI: {result.cmdb_url}/albs-all-accounts")
    print(f"      {result.cmdb_url}/instances-all-accounts")
    print()

    print("DNS:")
    if result.dns_chain:
        for hop in result.dns_chain:
            print(f"  {hop.name}  {hop.record_type} → {hop.value}")
    else:
        print("  (no DNS chain resolved)")
    if result.lb_hostname:
        ips = ", ".join(result.lb_ips) if result.lb_ips else "(none)"
        print(f"  {result.lb_hostname}  A → {ips}  (LB front-end)")
    print()

    if result.alb_match:
        alb = result.alb_match
        domains = alb.get("route53_records") or []
        print("CMDB ALB match:")
        print(f"  name:     {alb.get('name') or '?'}")
        print(f"  dns_name: {alb.get('dns_name') or '?'}")
        print(
            f"  region:   {alb.get('region') or '?'}  "
            f"account: {alb.get('account_id') or '?'}"
        )
        if domains:
            print(f"  domains:  {', '.join(domains)}")
        print()
    elif result.lb_hostname:
        print("CMDB ALB match: (none)")
        print()

    if result.backends:
        print("Backend instances:")
        for b in result.backends:
            extra = []
            if b.name_tag:
                extra.append(f"name={b.name_tag}")
            if b.patch_class:
                extra.append(f"patch_class={b.patch_class}")
            extra_s = "  " + "  ".join(extra) if extra else ""
            print(
                f"  {b.target_group}  {b.instance_id}  {b.private_ip or '?'}  "
                f"{b.state}{extra_s}  ({b.source})"
            )
    else:
        print("Backend instances: (none found)")

    if result.warnings:
        print()
        print("Notes:")
        for w in result.warnings:
            print(f"  - {w}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace domain to backend instance IPs")
    parser.add_argument("domain", help="Domain to trace")
    parser.add_argument(
        "--cmdb-url",
        default="https://cmdb.paytmpayments.com",
        help="CMDB base URL",
    )
    parser.add_argument(
        "--source",
        choices=("auto", "cmdb", "aws"),
        default="auto",
        help="auto=CMDB+AWS, cmdb=CMDB only, aws=skip CMDB",
    )
    parser.add_argument("--region", default="", help="AWS region override")
    args = parser.parse_args()

    domain = normalize_domain(args.domain)
    if not domain:
        print("Invalid domain", file=sys.stderr)
        sys.exit(1)

    result = trace_domain(
        domain,
        args.cmdb_url,
        source=args.source,
        region_override=args.region or None,
    )
    print_trace(result)

    if not result.dns_chain and not result.backends:
        sys.exit(1)


if __name__ == "__main__":
    main()
