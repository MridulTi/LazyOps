# AWS domain trace (`lazyops aws trace`)

## Decision

`lazyops aws trace <domain>` is a thin CLI alias that delegates to the `aws/trace` workflow plugin. The workflow resolves **domain → load balancer → backend EC2 instance IPs** using:

1. Live DNS (`nslookup`, CNAME walk)
2. CMDB Node API (`/node/api/alb` or `/node/api/albs`, `/node/api/instances`, optional `/node/api/route53`)
3. AWS ELBv2 target health for the final hop to running instances

**Status:** implemented (confirmed). CMDB auth is VPN-only, no API token (confirmed by maintainer).

## Why DNS first

Ops debugging starts with “what does this domain resolve to?” — not with a Route53 API query. Live DNS can differ from CMDB-synced Route53 (CDN/Akamai in front, stale sync, internal vs external resolvers).

**Alternative considered:** Route53-first via AWS API or CMDB Route53 only.

**Rejected because:** misses CDN edge paths and live resolver behavior; engineers already run `nslookup` manually before opening CMDB.

## Why CMDB + AWS (hybrid)

CMDB (`ppsl_cmdb`) syncs Route53 records, ALBs, and EC2 into separate tables/APIs. Production exposes Node endpoints such as `GET https://cmdb.paytmpayments.com/node/api/instances` (confirmed). ALB and Route53 paths follow the same prefix: `/node/api/albs`, `/node/api/route53`. The web UI pages `albs-all-accounts` and `instances-all-accounts` show the same inventory.

CMDB **does not** store target-group → instance membership (inferred from CMDB models: `ALB`, `EC2`, `Route53Record` with no TG model).

**Alternative considered:** CMDB-only trace.

**Rejected because:** cannot reliably list backend instance IPs behind an ALB without `elasticloadbalancing:DescribeTargetHealth`.

**Alternative considered:** Match ALB by resolved IP.

**Rejected because:** ALB front-end IPs are shared and ephemeral; hostname match on `dns_name` is stable.

## Why thin CLI

Per [`.copilot/README.md`](../.copilot/README.md) and [ARCHITECTURE.md](../ARCHITECTURE.md): the CLI routes commands; workflow scripts hold operational logic. `commands/aws.py` only normalizes flags and calls `registry.runner.run_target("aws", "trace", ...)`.

**Alternative considered:** embed trace logic in `commands/aws.py`.

**Rejected because:** duplicates the workflow engine and breaks the remote plugin catalog model.

## Configuration

CMDB URL resolution order (confirmed design):

1. `--cmdb-url`
2. `LAZYOPS_CMDB_URL`
3. `~/.lazyops/config.yaml` → `cmdb.url`
4. Default `https://cmdb.paytmpayments.com`

Bundled plugins under `plugins/aws/trace/` are used when present (local dev); otherwise the plugin is fetched from the configured lazyops-plugins git source.

## Consequences

- **On VPN:** full trace with CMDB enrichment and CMDB UI links in output.
- **Off VPN:** CMDB fetch fails; use `--source aws` with credentials, or expect partial output.
- **CDN-only domains:** DNS shows edge IP without ELB CNAME; script warns and may use CMDB Route53 fallback for internal AWS path.

## Related files

- [`commands/aws.py`](../commands/aws.py) — CLI alias
- [`plugins/aws/trace/script.py`](../plugins/aws/trace/script.py) — trace implementation
- [`registry/cmdb.py`](../registry/cmdb.py) — CMDB URL resolution
- [`registry/runner.py`](../registry/runner.py) — shared workflow execution
