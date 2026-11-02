feature branches -> dev_release_20261023  -> dev     (deploys DEV)
                    qa_release_20261023   -> qa      (deploys QA, approval)
                    prod_release_20261023 -> main    (deploys PROD, approval)

This pipeline creates:
Every day at 01:00 UTC it checks which sprint you are in and creates `dev_release_<sprint end>` if it doesn't exist.
After a good DEV deploy it creates `qa_release_<same date>` (from `qa`).
After a good QA deploy it creates `prod_release_<same date>` (from `main`).
Old release branches** (over 90 days) are deleted automatically.

A deploy happens only when a release branch is merged into `dev`, `qa` or `main` using a normal merge commit (the message contains the release branch name). Random pushes don't deploy.

Project layout
.github/workflows/release-management.yaml  sprint/emergency release branches, cleanup
.github/workflows/deploy-snowflake.yaml    deploys SQL + creates the next release branch
.github/workflows/deploy-lambda.yaml       deploys the Lambda
aws/lambda/lambda_function.py              API -> S3
scripts/deploy.py                          runs the SQL files
snowflake/setup/                           run ONCE by hand
snowflake/tables/                          schemas, raw, dim, fact, view
snowflake/snowpipes/                       file format, stage, pipe
snowflake/tasks/                           stream + SCD2 load task
