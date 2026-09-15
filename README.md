# Agentic SOC

Agentic SOC is a cloud-security investigation project built around real AWS telemetry, Elastic Security alerts, and an LLM-based investigator.

The current implementation uses AWS CloudTrail, S3, SQS, Elastic Agent, Elasticsearch, and Elastic Security. The investigation layer is being built with LangGraph and LangChain.

## Architecture

```text
AWS activity
    ↓
CloudTrail
    ↓
S3
    ↓
SQS
    ↓
Elastic Agent
    ↓
Elasticsearch
    ↓
Elastic Security alert
    ↓
FastAPI webhook
    ↓
LangGraph investigator
```

## Current Status

Scenario 01 implements credential persistence through an additional IAM access key.

```text
temporary role session
    ↓
CreateAccessKey
    ↓
new IAM credential
    ↓
ListUsers using the new credential
```

Implemented and verified:

- AWS infrastructure with Terraform
- repeatable Scenario 01 execution with boto3
- CloudTrail → S3 → SQS pipeline
- Elastic Agent ingestion
- Elasticsearch / Discover verification
- Elastic Security detection and real alert generation
- programmatic detection-rule configuration
- programmatic CloudTrail and alert queries
- FastAPI webhook receiver with token authentication

In progress:

- external Elastic → webhook delivery
- LangGraph investigation workflow
- evidence collection and structured verdict generation

## Repository Structure

```text
infra/terraform/     AWS infrastructure
scripts/scenarios/   repeatable security scenarios
scripts/elastic/     Elastic configuration automation
src/agentic_soc/     Agentic SOC application code
docs/                design and implementation notes
```

## Investigation Model

The investigator is designed to answer:

```text
Who   — who performed the activity?
When  — when did it occur?
Where — where did it originate?
How   — how did access change?
What  — what happened afterward?
Why   — is there evidence of a legitimate explanation?
```

The final goal is an evidence-backed verdict with a timeline, supporting evidence, and explicit uncertainty.

## Security

Secrets, API keys, Terraform state, and runtime scenario state are excluded from version control.