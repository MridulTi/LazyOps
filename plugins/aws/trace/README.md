# AWS Domain Trace

Trace a domain to its load balancer and backend EC2 instance IPs.

## Usage

```bash
lazyops aws trace seller.example.com
lazyops aws trace seller.example.com --cmdb-url https://cmdb.paytmpayments.com
lazyops aws trace seller.example.com --source aws --region ap-south-1
```

Equivalent: `lazyops run aws/trace <domain> [--cmdb-url ...] [--source auto|cmdb|aws] [--region ...]`

## How it works

1. **nslookup** the domain and follow CNAMEs to an ELB hostname
2. **nslookup** the ELB hostname for front-end IPs
3. **CMDB** `/api/alb/` — match `dns_name` (same data as `/albs-all-accounts`)
4. **CMDB** `/api/ec2/` — enrich instances (same data as `/instances-all-accounts`)
5. **AWS ELBv2** `describe-target-health` — resolve actual backend targets

## Requirements

- VPN access to CMDB (no API token)
- AWS credentials with `elasticloadbalancing:Describe*` and `ec2:DescribeInstances`
- Python deps: `requests`, `boto3` (installed in LazyOps venv)

## CMDB configuration

Default URL: `https://cmdb.paytmpayments.com`

Override via:

- `--cmdb-url`
- `LAZYOPS_CMDB_URL` env
- `~/.lazyops/config.yaml`:

```yaml
cmdb:
  url: https://cmdb.paytmpayments.com
```

## Publishing

Copy this folder to `lazyops-plugins` at `plugins/aws/trace/` for remote catalog distribution.

Local development uses bundled `LazyOps/plugins/aws/trace/` automatically.
