"""Operator-only secret bootstrap for an explicitly selected Kubernetes cluster."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ["kubeconfig", "context", "tls-cert", "tls-key"]:
        parser.add_argument("--" + flag, required=True)
    parser.add_argument("--database-url-file", help="File containing the PostgreSQL runtime URI; needed on first bootstrap")
    args = parser.parse_args()
    kube = ["kubectl", "--kubeconfig", args.kubeconfig, "--context", args.context, "-n", "baatchit"]

    def exists(name):
        result = subprocess.run(kube + ["get", "secret", name, "--ignore-not-found", "-o", "name"],
                                check=True, text=True, capture_output=True)
        return bool(result.stdout.strip())

    def apply(name, values, kind="Opaque"):
        body = {"apiVersion":"v1", "kind":"Secret", "type":kind,
                "metadata":{"name":name, "namespace":"baatchit"}, "stringData":values}
        # Secret values never appear in process arguments or tool output.
        subprocess.run(kube + ["apply", "-f", "-"], input=json.dumps(body), text=True,
                       check=True, capture_output=True)

    cert = Path(args.tls_cert).read_text(encoding="utf-8")
    key = Path(args.tls_key).read_text(encoding="utf-8")
    if "BEGIN CERTIFICATE" not in cert or "PRIVATE KEY" not in key:
        raise ValueError("Supply PEM certificate chain and private key")
    database_url = None
    if not exists("database-url"):
        if not args.database_url_file:
            raise ValueError("Provision PostgreSQL and supply --database-url-file before the first account-capable release")
        database_url = Path(args.database_url_file).read_text(encoding="utf-8").strip()
        if not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("The database file must contain a postgresql+psycopg URI")
    have_url, have_acl = exists("redis-url"), exists("redis-auth")
    if have_url != have_acl:
        raise ValueError("Incomplete Redis Secret pair; restore it before continuing")
    if not have_url:
        password = secrets.token_hex(32)
        digest = hashlib.sha256(password.encode()).hexdigest()
        apply("redis-auth", {"users.acl":"user default off\nuser app on #" + digest
                            + " &global_chat_channel +ping +publish +subscribe +unsubscribe\n"})
        apply("redis-url", {"url":"redis://app:" + password + "@redis:6379/0"})
    apply("gateway-tls", {"tls.crt":cert, "tls.key":key}, "kubernetes.io/tls")
    if database_url:
        apply("database-url", {"url": database_url})
    print("Secrets provisioned. Existing Redis/database credentials preserved. Restart gateway after TLS rotation.")


if __name__ == "__main__":
    main()
