import typer

from registry.cmdb import get_cmdb_url
from registry.runner import run_target

aws_app = typer.Typer(help="AWS operational shortcuts")


def register(app: typer.Typer):
    app.add_typer(aws_app, name="aws")


@aws_app.command("trace", help="Trace a domain to ALB and backend EC2 instance IPs")
def aws_trace(
    domain: str = typer.Argument(..., help="Domain to trace, e.g. seller.paytmpayments.com"),
    cmdb_url: str | None = typer.Option(
        None,
        "--cmdb-url",
        help="CMDB base URL (default: config or https://cmdb.paytmpayments.com)",
    ),
    source: str = typer.Option(
        "auto",
        "--source",
        help="Data source: auto (CMDB + AWS), cmdb (CMDB only where possible), aws (skip CMDB)",
    ),
    region: str | None = typer.Option(
        None,
        "--region",
        help="AWS region override for ELBv2/EC2 calls",
    ),
    cmdb_api_prefix: str | None = typer.Option(
        None,
        "--cmdb-api-prefix",
        help="CMDB API path prefix (default: /node/api; env: CMDB_API_PREFIX)",
    ),
):
    """Resolve domain → load balancer → backend instances via DNS, CMDB, and AWS."""
    resolved_cmdb = get_cmdb_url(cmdb_url)
    args = [domain, "--cmdb-url", resolved_cmdb, "--source", source]
    if region:
        args.extend(["--region", region])
    if cmdb_api_prefix:
        args.extend(["--cmdb-api-prefix", cmdb_api_prefix])
    run_target("aws", "trace", args)
