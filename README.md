# Snowflake + AWS CI/CD Demo (beginner version)

Mirrors a real company pipeline: **API → Lambda → S3 → SQS → Snowpipe → RAW → DIM/FACT (SCD2) → CORE view**, deployed by **GitHub Actions** using **sprint release branches** through **dev → qa → prod** with approval gates.

## What is a sprint? (beginner explanation)

A **sprint** is a fixed block of work time, here **14 days**. All changes finished in that sprint go into one labeled "box": a branch named `dev_release_<sprint end date>`, e.g. `dev_release_20261023`. The box then travels through the environments with the same date:

```
feature branches -> dev_release_20261023  -> dev     (deploys DEV)
                    qa_release_20261023   -> qa      (deploys QA, approval)
                    prod_release_20261023 -> main    (deploys PROD, approval)
```

The pipeline creates the boxes for you:
- **Every day at 01:00 UTC** it checks which sprint you are in and creates `dev_release_<sprint end>` if it doesn't exist.
- **After a good DEV deploy** it creates `qa_release_<same date>` (from `qa`).
- **After a good QA deploy** it creates `prod_release_<same date>` (from `main`).
- **Old release branches** (over 90 days) are deleted automatically.

A deploy happens **only** when a release branch is merged into `dev`, `qa` or `main` using a normal **merge commit** (the message contains the release branch name). Random pushes don't deploy.

## How it maps to your company pipeline

| Company (`main5.yaml`) | This demo |
|---|---|
| `auto-create-sprint-release` (hardcoded sprint list) | `release-management.yaml` (anchor date + 14 days) |
| `create-emergency-release` | same manual button |
| `cleanup-branches` | same, 90 days |
| `detect-changes` reads merge message | `detect-env` job |
| `approval-*` jobs (Environments) | Environments `dev`, `qa`, `prod` |
| `deploy` | `scripts/deploy.py` |
| `create-next-release` | same job, DEV to QA to PROD |
| UAT stage, diff-check, Teams alerts | Left out (add later) |

## Project layout

```
.github/workflows/release-management.yaml  sprint/emergency release branches, cleanup
.github/workflows/deploy-snowflake.yaml    deploys SQL + creates the next release branch
.github/workflows/deploy-lambda.yaml       deploys the Lambda
aws/lambda/lambda_function.py              API -> S3
scripts/deploy.py                          runs the SQL files
snowflake/setup/                           run ONCE by hand
snowflake/tables/                          schemas, raw, dim, fact, view
snowflake/snowpipes/                       file format, stage, pipe
snowflake/tasks/                           stream + SCD2 load task
```

---

## Step 1: Install tools (Ubuntu)

```bash
sudo apt update
sudo apt install -y git openssl unzip
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

## Step 2: Create the GitHub repo

1. GitHub → New repository → name `snowflake-elt-cicd`. Choose **Public** (approval gates are free only on public repos). Never commit keys or passwords.
2. On your laptop:

```bash
unzip snowflake-elt-cicd.zip && cd snowflake-elt-cicd
git init -b dev
git remote add origin https://github.com/<you>/snowflake-elt-cicd.git
```
Don't push yet. Finish steps 3–6 first.

## Step 3: AWS (S3 bucket + role for Snowflake)

Sign up at aws.amazon.com and **immediately** set a budget alert (Billing → Budgets → $5).

1. **S3 bucket:** S3 → Create bucket → name like `yourname-elt-demo-123` → keep "Block all public access" on. Note the name and region.
2. **IAM policy** `snowflake-s3-read` (IAM → Policies → JSON). Replace `BUCKET`:

```json
{"Version":"2012-10-17","Statement":[
 {"Effect":"Allow","Action":["s3:GetObject","s3:GetObjectVersion"],"Resource":"arn:aws:s3:::BUCKET/*"},
 {"Effect":"Allow","Action":["s3:ListBucket","s3:GetBucketLocation"],"Resource":"arn:aws:s3:::BUCKET"}]}
```
3. **IAM role** `snowflake-s3-role`: Create role → Trusted entity "AWS account" → This account → attach `snowflake-s3-read`. Copy the role's ARN and your 12-digit AWS account ID.

## Step 4: Snowflake

1. Sign up for the free 30-day trial (Standard edition, AWS, same region as your bucket if possible).
2. **Make a key pair** on your laptop:

```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
cat rsa_key.pub
```
3. Open `snowflake/setup/00_one_time_setup.sql`, replace `<ACCOUNT_ID>`, `<YOUR_BUCKET>`, `<PUBLIC_KEY>` (public key = the text between the BEGIN/END lines, joined into one line). Paste it into a Snowflake worksheet and run all.
   - If `TYPE = SERVICE` errors, delete that line.
4. From the `DESC INTEGRATION S3_INT` output copy `STORAGE_AWS_IAM_USER_ARN` and `STORAGE_AWS_EXTERNAL_ID`.
5. Back in AWS → role `snowflake-s3-role` → Trust relationships → Edit → paste:

```json
{"Version":"2012-10-17","Statement":[{"Effect":"Allow",
 "Principal":{"AWS":"<STORAGE_AWS_IAM_USER_ARN>"},
 "Action":"sts:AssumeRole",
 "Condition":{"StringEquals":{"sts:ExternalId":"<STORAGE_AWS_EXTERNAL_ID>"}}}]}
```
6. Find your **account identifier**: Snowflake bottom-left account menu → copy account identifier (looks like `ORGNAME-ACCOUNTNAME`).

## Step 5: AWS Lambda

1. Lambda → Create function → name **`weather-ingest`**, runtime Python 3.12.
2. Code tab: paste `aws/lambda/lambda_function.py` → Deploy.
3. Configuration → General: timeout **30 sec**. Environment variables: `BUCKET` = your bucket, `ENV` = `dev`.
4. Configuration → Permissions → click the role → Add permissions → Create inline policy:

```json
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"s3:PutObject","Resource":"arn:aws:s3:::BUCKET/*"}]}
```
5. **User for GitHub:** IAM → Users → create `github-deployer` → inline policy:

```json
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"lambda:UpdateFunctionCode","Resource":"arn:aws:lambda:*:*:function:weather-ingest"}]}
```
Then Security credentials → Create access key (CLI use). Save both values.

## Step 6: GitHub secrets and environments

Repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret | Value |
|---|---|
| `SNOWFLAKE_ACCOUNT` | account identifier, e.g. `ORGNAME-ACCOUNTNAME` |
| `SNOWFLAKE_USER` | `GH_DEPLOY_USER` |
| `SNOWFLAKE_PRIVATE_KEY` | full contents of `rsa_key.p8` (including BEGIN/END lines) |
| `S3_BUCKET` | your bucket name |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | from `github-deployer` |
| `AWS_REGION` | e.g. `us-east-1` |

Repo → Settings → Environments → create **`dev`**, **`qa`**, **`prod`**. In `qa` and `prod` tick **Required reviewers** and add yourself. (This is your approval gate, like `QA-approval` in the company pipeline.)

## Step 7: First deployment (DEV)

Set your sprint calendar first: open `.github/workflows/release-management.yaml` and change `SPRINT_ANCHOR_END` to any real sprint **end** date (YYYYMMDD), e.g. the coming Friday. Every 14 days from it is a sprint end.

```bash
git add . && git commit -m "Initial pipeline"
git push -u origin dev
```
Keep `dev` as the repo's **default branch** (Settings -> Branches), because scheduled workflows only run from the default branch.

Now GitHub -> **Actions** -> "Snowflake CI/CD" -> **Run workflow** -> branch `dev` -> Run. (A plain push doesn't deploy, because its message has no release name. This manual button is only for the very first deploy.) Click the `deploy` job to watch each SQL file run. The Lambda workflow runs by itself.

Then create the other two branches:
```bash
git branch qa && git branch main
git push origin qa main
```
Their runs will show the `deploy` job as **skipped**. That's correct.

In Snowflake check: `SHOW TABLES IN DATABASE DEMO_ELT_DEV;`

## Step 8: Connect S3 to Snowpipe (SQS)

1. In Snowflake run:
```sql
SHOW PIPES IN DATABASE DEMO_ELT_DEV;
```
Copy the `notification_channel` value (an `arn:aws:sqs:...` string).
2. AWS → S3 → your bucket → Properties → Event notifications → Create:
   - Event types: **All object create events**
   - Destination: **SQS queue** → Enter ARN → paste the value.
   (All pipes in your Snowflake account share this one queue, so you only do this once.)

## Step 9: Test the whole flow

1. AWS Lambda → `weather-ingest` → Test (any empty event) → Invoke. A file appears in `s3://<bucket>/dev/weather/...`.
2. Wait ~1–2 minutes, then in Snowflake:

```sql
USE DATABASE DEMO_ELT_DEV;
SELECT SYSTEM$PIPE_STATUS('RAW.WEATHER_PIPE');   -- pipe is running
SELECT * FROM RAW.WEATHER_RAW;                   -- raw JSON landed
SELECT * FROM CORE.DIM_CITY;                     -- SCD2 dimension
SELECT * FROM CORE.FACT_WEATHER;
SELECT * FROM CORE.V_WEATHER;                    -- core layer
```
3. Test SCD2: update a city's latitude in the raw data (or edit the Lambda's `CITIES`), invoke again, and query `DIM_CITY`. The old row gets `IS_CURRENT = FALSE` and a new row appears.

## Step 10: Run one full sprint release (DEV -> QA -> PROD)

Use the GitHub website for the Pull Requests (PRs). When merging, always click **"Create a merge commit"** (not squash, not rebase), because the pipeline reads the merge message.

**A. Get the sprint box**
Actions -> "Release Management" -> Run workflow -> `create-sprint-release`. (It also happens automatically each night.) Look in Branches for `dev_release_<date>`. Call that date `D`.

**B. Make a change (your "feature")**
```bash
git fetch origin
git checkout -b feature_add_country origin/dev_release_D
echo "ALTER TABLE CORE.DIM_CITY ADD COLUMN IF NOT EXISTS COUNTRY STRING;" > snowflake/tables/05_alter_dim_city.sql
git add . && git commit -m "Add country column"
git push -u origin feature_add_country
```
Open a PR: **base** `dev_release_D` <- **compare** `feature_add_country`. Merge it. Nothing deploys yet. Many people can merge their features into the same box.

**C. Release the box to DEV**
PR: base `dev` <- compare `dev_release_D`. Merge with a merge commit. The pipeline deploys to `DEMO_ELT_DEV`, then creates `qa_release_D`. Check Branches.

**D. QA**
1. PR: base `qa_release_D` <- compare `dev_release_D`. Merge. (Brings the DEV changes into the QA box.)
2. PR: base `qa` <- compare `qa_release_D`. Merge with a merge commit.
3. Actions pauses at **Review deployments** -> Approve. It deploys to `DEMO_ELT_QA` and creates `prod_release_D`.

**E. PROD**
1. PR: base `prod_release_D` <- compare `qa_release_D`. Merge.
2. PR: base `main` <- compare `prod_release_D`. Merge with a merge commit.
3. Approve. It deploys to `DEMO_ELT_PROD`. No next box after PROD.

Take screenshots of the Actions graph and the branch list for your resume.

**Emergency fix:** Actions -> Release Management -> `create-emergency-release` creates `dev_release_<today>` so an urgent change can go out without waiting for the sprint end. Then follow B to E with that date.

> QA and PROD read from `s3://<bucket>/qa/weather/` and `/prod/weather/`. To test them end to end, set the Lambda env var `ENV` to `qa` and invoke.

## Making changes (the daily workflow)

1. `git checkout -b feature_xyz origin/dev_release_<current sprint end>`
2. Edit or add `.sql` files in `snowflake/tables|snowpipes|tasks`. Push and PR into the release box.
3. At sprint end, release the box through dev, qa and prod as in Step 10.

Rules for SQL files: every deploy re-runs **all** files, so keep them re-runnable (`CREATE ... IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`). Separate multiple statements with a line `-- GO`. To change an existing table, add a new file such as `tables/05_alter_dim_city.sql`.

## Step 11: Save credits and money

```sql
ALTER TASK DEMO_ELT_DEV.CORE.LOAD_WEATHER_TASK SUSPEND;   -- repeat for QA / PROD
```
Keep the warehouse XSMALL, don't schedule Lambda more often than hourly, and delete everything when done (S3 bucket, Lambda, IAM user, Snowflake databases). Check your AWS and Snowflake billing pages.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Failed to load private key` | Secret must include the BEGIN/END lines of `rsa_key.p8` |
| `JWT token is invalid` | Public key in Snowflake doesn't match the private key, or account identifier is wrong |
| Stage/pipe error about S3 access | Trust policy values wrong (re-run `DESC INTEGRATION S3_INT`) |
| File in S3 but no rows | S3 event notification missing, or wrong SQS ARN |
| Deploy never starts on qa/prod | It's waiting for your approval in the Actions tab |
| Merged a PR but `deploy` was skipped | You used squash/rebase merge, or merged the wrong branch. The merge message must contain e.g. `dev_release_20261023`. Use "Create a merge commit" |
| No `dev_release_*` branch appeared | Run Release Management manually. Scheduled runs need the default branch to be `dev` and may pause after 60 days of repo inactivity |
| `qa_release_*` not created after DEV deploy | Branch `qa` must exist (Step 7), and the DEV deploy must have succeeded |
| `Insufficient privileges` | Re-run the grants in the setup SQL |

## Resume bullets

- Built a CI/CD pipeline with GitHub Actions that deploys versioned SQL (tables, Snowpipes, streams, tasks) to Snowflake across DEV/QA/PROD with manual approval gates.
- Implemented a sprint-based release-branch model: automated release branch creation, promotion DEV to QA to PROD, emergency releases and scheduled branch cleanup.
- Automated API ingestion with AWS Lambda into S3 and Snowpipe auto-ingest via S3 → SQS notifications.
- Implemented SCD Type 2 dimensions and fact loading with Snowflake streams and tasks; key-pair authentication and secrets managed in GitHub.
