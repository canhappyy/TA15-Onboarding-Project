# TA15 Onboarding Project

Industry Experience Studio (FIT5120)

## Tech Stack

### Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- pnpm

### Backend

- AWS Lambda (Python 3.13)

### Infrastructure

- Terraform
- AWS API Gateway
- AWS IAM

### Database (Upcoming)

- PostgreSQL (Amazon RDS)

---

# Project Structure

```text
project-root/
├── apps/
│   └── web/                # Next.js frontend
│
├── services/
│   └── api/                # Python Lambda functions
│
├── packages/
│   └── database/           # SQL schema and migrations
│
├── infra/
│   └── aws/                # Terraform
│
└── docs/
```

---

# Prerequisites

Install the following tools before starting.

| Tool       | Version |
| ---------- | ------- |
| Node.js    | 22.x    |
| pnpm       | Latest  |
| Python     | 3.13    |
| Terraform  | >= 1.9  |
| AWS CLI v2 | Latest  |
| Git        | Latest  |

Verify installation

```bash
node -v
pnpm -v
python3 --version
terraform version
aws --version
```

---

# Node.js Setup

Use Node.js 22.

```bash
nvm use 22
```

If Node.js 22 is not installed:

```bash
nvm install 22
nvm use 22
```

If `nvm` is not installed, follow this [guide](https://www.freecodecamp.org/news/node-version-manager-nvm-install-guide/)

---

# pnpm Setup

Enable Corepack.

```bash
corepack enable
```

Install workspace dependencies.

```bash
pnpm install
```

---

# Run Frontend

From the project root:

```bash
pnpm dev
```

Open

```
http://localhost:3000
```

---

# AWS Setup

## 0. Create AWS Account

1. Go to this [AWS Console link](https://aws.amazon.com/console/)
2. Click **Create account** on the top right
3. Use student email to register for Root user email
4. Once register successfully, set up an Alias
   1. Go to the **IAM Dashboard** in the AWS console.
   2. Find **Account Alias** under the AWS Account box (on the right of screen).
   3. Click **Create** (or **Edit** if changing).
   4. Type a unique, lowercase name for your account.
   5. Click **Save changes**.

## 1. Create IAM User

On IAM dashboard, click **IAM Users** on the left side and create user
**Note:** leave **Provide user access to the AWS Management Console - optional** uncheck

Next, select **Attach policies directly** and search permission policy below

```
AdministratorAccess
```

Generate an Access Key for CLI usage. (Save csv file)

---

## 2. Configure AWS CLI

```bash
aws configure --profile ta15-dev
```

Example

```
AWS Access Key ID: <from csv file>
AWS Secret Access Key: <from csv file>
Region: ap-southeast-4
Output: json
```

---

## 3. Export Profile

macOS/Linux

```bash
export AWS_PROFILE=ta15-dev
```

Windows PowerShell

```powershell
$env:AWS_PROFILE="ta15-dev"
```

---

## 4. Verify Credentials

```bash
aws sts get-caller-identity
```

Expected output

```json
{
  "Account": "...",
  "Arn": "...",
  "UserId": "..."
}
```

---

# Terraform Setup

If `Terraform` is not installed, follow this [guide](https://developer.hashicorp.com/terraform/install)

Move into the Terraform directory.

```bash
cd infra/aws
```

Copy the example variables.

```bash
cp terraform.tfvars.example terraform.tfvars
```

Initialize Terraform.

```bash
terraform init
```

Validate configuration.

```bash
terraform validate
```

Preview resources.

```bash
terraform plan
```

Deploy infrastructure.

```bash
terraform apply
```
Note: Enter `yes` if prompted

---

# Verify Deployment

Retrieve the Health API endpoint.

```bash
terraform output -raw health_endpoint
```

Example

```
https://xxxxx.execute-api.ap-southeast-4.amazonaws.com/health
```

Test it.

```bash
curl $(terraform output -raw health_endpoint)
```

Expected response

```json
{
  "status": "ok"
}
```

---

# Environment Variables

Frontend

Create

```
apps/web/.env.local
```

Example

```env
NEXT_PUBLIC_API_BASE_URL=https://<api-gateway-url>
```

---

# Git Ignore

The following files must **never** be committed.

```
node_modules/
.next/

.env*
!.env.example

.terraform/
terraform.tfstate
terraform.tfstate.*

terraform.tfvars

.terraform-build/

.venv/
```

---

# Useful Commands

Run frontend

```bash
pnpm dev
```

Terraform plan

```bash
terraform plan
```

Terraform apply

```bash
terraform apply
```

Destroy infrastructure

```bash
terraform destroy
```

Terraform formatting

```bash
terraform fmt -recursive
```

---

# Current Progress

- ✅ pnpm workspace
- ✅ Next.js setup
- ✅ Python Lambda skeleton
- ✅ Terraform boilerplate
- ✅ API Gateway
- ✅ Health Lambda
- ✅ Health endpoint

---

# Next Milestones

- Route search API
- Nearby refuge API
- PostgreSQL (Amazon RDS)
- Open Data API integration
- Frontend integration
