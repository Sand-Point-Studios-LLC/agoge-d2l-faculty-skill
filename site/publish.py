#!/usr/bin/env python3
"""Publish the site to Cloudflare Pages on a public custom domain.

    python3 site/publish.py            # DRY RUN: prints what it would do, changes nothing
    python3 site/publish.py --apply    # creates the Pages project, deploys, attaches the domain, adds DNS

Set CF_API_TOKEN (Pages edit + DNS edit), CF_ACCOUNT_ID and CF_ZONE_ID, and edit PROJECT and HOST below.
The DNS record must be proxied (orange cloud). Needs node (npx wrangler) for the upload.
Run `python3 build_kit.py` and `python3 site/build_site.py` first.
"""
import argparse, json, os, subprocess, sys, urllib.request
from pathlib import Path

ACCOUNT = os.environ["CF_ACCOUNT_ID"]
ZONE = os.environ["CF_ZONE_ID"]
PROJECT = "agoge-d2l"
HOST = "agoge-d2l.sandpointstudios.ltd"
API = "https://api.cloudflare.com/client/v4"
here = Path(__file__).resolve().parent


def call(method, path, body=None, apply=False):
    if not apply and method != "GET":
        print("  [dry run] %s %s\n    %s" % (method, path, json.dumps(body)[:400] if body else ""))
        return {"success": True, "result": {}}
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": "Bearer " + os.environ["CF_API_TOKEN"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        res = {"success": False, "errors": [e.read().decode()[:300]]}
    if method != "GET" and not res.get("success"):
        sys.exit("STOPPED: %s %s failed: %s" % (method, path, res.get("errors")))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--upload-only", action="store_true", help="redeploy the files only")
    a = ap.parse_args()
    if "CF_API_TOKEN" not in os.environ:
        sys.exit("CF_API_TOKEN is not set")
    dist = here / "dist"
    if not (dist / "index.html").is_file():
        sys.exit("build first: python3 build_kit.py && python3 site/build_site.py")
    print("MODE:", "APPLY" if a.apply else "DRY RUN (nothing will change)")
    deploy = ["npx", "wrangler", "pages", "deploy", str(dist), "--project-name", PROJECT, "--branch", "main", "--commit-dirty=true"]
    if not a.upload_only:
        print("\n1. Pages project '%s'" % PROJECT)
        if call("GET", "/accounts/%s/pages/projects/%s" % (ACCOUNT, PROJECT), apply=True).get("success"):
            print("  exists already")
        else:
            call("POST", "/accounts/%s/pages/projects" % ACCOUNT, {"name": PROJECT, "production_branch": "main"}, a.apply)
    print("\n2. Upload %d files from %s" % (sum(1 for _ in dist.rglob("*") if _.is_file()), dist))
    if a.apply:
        subprocess.run(deploy, check=True, env={**os.environ, "CLOUDFLARE_ACCOUNT_ID": ACCOUNT})
    else:
        print("  [dry run]", " ".join(deploy))
    if a.upload_only:
        return
    print("\n3. Custom domain %s" % HOST)
    call("POST", "/accounts/%s/pages/projects/%s/domains" % (ACCOUNT, PROJECT), {"name": HOST}, a.apply)
    print("\n4. DNS: proxied CNAME %s -> %s.pages.dev" % (HOST.split(".")[0], PROJECT))
    call("POST", "/zones/%s/dns_records" % ZONE,
         {"type": "CNAME", "name": HOST.split(".")[0], "content": "%s.pages.dev" % PROJECT, "proxied": True, "ttl": 1}, a.apply)
    print("\nVerify: curl -sI https://%s/ | head -3   # expect 200" % HOST)


if __name__ == "__main__":
    main()
