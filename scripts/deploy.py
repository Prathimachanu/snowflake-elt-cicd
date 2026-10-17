"""Runs every .sql file in snowflake/{tables,snowpipes,tasks} against one environment.
Files run in folder order, then alphabetical order. Statements inside a file are
separated by a line containing:  -- GO
"""
import glob
import os
import re
import sys

import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

FOLDER_ORDER = ["tables", "snowpipes", "tasks"]

env = os.environ["TARGET_ENV"].lower()          # dev / qa / prod
bucket = os.environ["S3_BUCKET"]
database = f"DEMO_ELT_{env.upper()}"

# --- load the private key (PEM text stored in a GitHub secret) ---
key = serialization.load_pem_private_key(
    os.environ["SNOWFLAKE_PRIVATE_KEY"].strip().encode("utf-8"),
    password=None,
    backend=default_backend(),
)
pkb = key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

print(f"Connecting to Snowflake, deploying to {database} ...")
conn = snowflake.connector.connect(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    private_key=pkb,
    role="DEPLOY_ROLE",
    warehouse="DEMO_WH",
    database=database,
)
cur = conn.cursor()


def statements(text):
    for part in re.split(r"^\s*--\s*GO\s*$", text, flags=re.I | re.M):
        only_code = "\n".join(
            l for l in part.splitlines() if not l.strip().startswith("--")
        ).strip()
        if only_code:
            yield part.strip()


ok = 0
for folder in FOLDER_ORDER:
    for path in sorted(glob.glob(f"snowflake/{folder}/*.sql")):
        text = open(path, encoding="utf-8").read()
        text = text.replace("{{ENV}}", env).replace("{{S3_BUCKET}}", bucket)
        print(f"\n>>> {path}")
        for i, stmt in enumerate(statements(text), 1):
            try:
                cur.execute(stmt)
                print(f"    statement {i}: OK")
            except Exception as e:
                print(f"    statement {i}: FAILED -> {e}")
                conn.close()
                sys.exit(1)
        ok += 1

conn.close()
print(f"\nDONE. {ok} files deployed to {database}.")
