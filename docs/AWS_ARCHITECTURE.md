# AWS Architecture

This document covers two concerns:

1. **Pipeline Execution** — the runtime flow that generates reports and emails subscribers on a weekly cron.
2. **CI/CD Infrastructure** — the build and image-management process that maintains the Docker images consumed by the pipeline.

---

## 1. Pipeline Execution

```mermaid
flowchart LR
    %% Trigger layer
    EB["EventBridge Scheduler<br/>weekly cron"]
    DL["Dispatcher Lambda<br/>fan-out per city"]

    %% Compute layer
    subgraph VPC["Amazon Virtual Private Cloud"]
        ECS["Elastic Container Service Fargate<br/>1 task per city"]
    end
    EXT["External APIs<br/>LLM / scraping"]

    %% Messaging layer
    SQS["Simple Queue Service<br/>report-ready queue"]
    WQ["Simple Queue Service<br/>worker-jobs queue"]
    DLQ[("Simple Queue Service<br/>Email DLQ")]
    PDLQ[("Simple Queue Service<br/>Pipeline DLQ")]
    WDLQ[("Simple Queue Service<br/>Worker DLQ")]

    %% Delivery layer
    EML["Email Lambda"]
    MAILGUN["Mailgun<br/>external email API"]
    USERS["User Inboxes"]

    %% Post-processing layer
    WK["Worker Lambda<br/>post-process report"]

    %% Data layer
    DB[("Supabase")]

    %% Main flow
    EB --> DL
    DL --> ECS
    ECS <-.->|"Internet Gateway Access"| EXT
    ECS -->|"write report<br/>+ bullets"| DB
    ECS -->|"enqueue<br/>{city, report_id}"| SQS
    SQS --> EML
    EML -->|"read report<br/>write send_log"| DB
    EML -->|"HTTPS API"| MAILGUN
    MAILGUN --> USERS

    %% Worker post-processing flow
    ECS -->|"enqueue<br/>{region, report_id}"| WQ
    WQ --> WK
    WK -->|"read report<br/>mark processed_at"| DB

    %% Side flows
    DL -.->|read cities| DB
    SQS -.->|after N retries| DLQ
    ECS -.->|"on failure<br/>{city, failures, report_id}"| PDLQ
    WQ -.->|after N retries| WDLQ

    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef ext fill:#4A90E2,stroke:#1F3A5F,stroke-width:2px,color:#fff
    classDef db fill:#1F6B47,stroke:#0D3322,stroke-width:2px,color:#fff
    classDef queue fill:#CC2264,stroke:#5C0F2E,stroke-width:2px,color:#fff
    classDef user fill:#7B68EE,stroke:#3F2E8C,stroke-width:2px,color:#fff

    class EB,DL,ECS,EML,WK aws
    class EXT,MAILGUN ext
    class DB db
    class SQS,WQ,DLQ,PDLQ,WDLQ queue
    class USERS user
    style VPC fill:#1F3A5F,stroke:#0D1F33,stroke-width:2px,color:#fff

    linkStyle 2 stroke-width:3px,stroke:#fff
```

### Flow Summary

1. **EventBridge** triggers the **Dispatcher Lambda** on a weekly cron.
2. **Dispatcher Lambda** reads the active cities from **Supabase** and fans out one **Elastic Container Service Fargate** task per city.
3. Each **Fargate task** calls external APIs (LLM, scraping) to generate report content, writes the report and its bullets to **Supabase**, then enqueues a message to the **report-ready queue** (`{city, report_id}`) for the Email Lambda and a message to the **worker-jobs queue** (`{region, report_id}`) for the Worker Lambda, and exits. If any topic or either SQS enqueue fails, the task sends failure metadata to the **Pipeline Dead Letter Queue** before exiting 1.
4. **Simple Queue Service** holds the message. AWS-managed pollers invoke the **Email Lambda** with batches of messages. Lambda reserved concurrency caps parallel executions to protect Mailgun rate limits.
5. **Email Lambda** reads the report and bullets from Supabase, queries subscribers for the city, renders the email, sends via **Mailgun** (HTTPS API; API key read from SSM), and writes to `send_log` for idempotency.
6. Failed Email Lambda messages are retried automatically by Simple Queue Service. After N failures, they land in the **Email Dead Letter Queue** for investigation. Pipeline-side failures land in the separate **Pipeline Dead Letter Queue** directly from the Fargate task.
7. In parallel with email delivery, **Simple Queue Service** invokes the **Worker Lambda** with each `{region, report_id}` message. The Worker Lambda reads the report from Supabase, verifies it belongs to the given region, and stamps `reports.processed_at`. It returns SQS partial-batch responses, so a message that fails validation or the write is retried and, after N attempts, lands in the **Worker Dead Letter Queue**. Supabase credentials are read from SSM at cold start.

---

## 2. CI/CD Infrastructure

```mermaid
flowchart LR
    DEV["Developer<br/>git push"]
    CI["CI/CD<br/>build + tag image"]

    subgraph ECR["Elastic Container Registry"]
        R1["next-voters-&lt;env&gt;-agent"]
        R2["next-voters-&lt;env&gt;-dispatcher"]
        R3["next-voters-&lt;env&gt;-email"]
        R4["next-voters-&lt;env&gt;-worker"]
    end

    ECS_T["Elastic Container Service<br/>Fargate task"]
    DL_T["Dispatcher Lambda"]
    EML_T["Email Lambda"]
    WK_T["Worker Lambda"]

    DEV --> CI
    CI -->|push image| R1
    CI -->|push image| R2
    CI -->|push image| R3
    CI -->|push image| R4

    R1 -.->|image pull on task start| ECS_T
    R2 -.->|image pull on deploy| DL_T
    R3 -.->|image pull on deploy| EML_T
    R4 -.->|image pull on deploy| WK_T

    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef repo fill:#232F3E,stroke:#FF9900,stroke-width:2px,color:#fff
    classDef ci fill:#7B68EE,stroke:#3F2E8C,stroke-width:2px,color:#fff
    classDef dev fill:#4A90E2,stroke:#1F3A5F,stroke-width:2px,color:#fff

    class ECS_T,DL_T,EML_T,WK_T aws
    class R1,R2,R3,R4 repo
    class CI ci
    class DEV dev
    style ECR fill:#1F3A5F,stroke:#FF9900,stroke-width:2px,color:#fff
```

### Repositories

| Repository | Consumer | Purpose |
|---|---|---|
| `next-voters-<env>-agent` | Elastic Container Service Fargate | LangGraph agent that scrapes external sources, calls LLMs, and generates report bullets |
| `next-voters-<env>-dispatcher` | Dispatcher Lambda | Reads active cities from Supabase and fans out Fargate tasks |
| `next-voters-<env>-email` | Email Lambda | Renders email templates and sends via Mailgun |
| `next-voters-<env>-worker` | Worker Lambda | Consumes `{region, report_id}` from the worker-jobs queue and post-processes the saved report (marks `reports.processed_at`) |

### Deployment Flow

1. Code is pushed to the application repository.
2. CI builds a Docker image and pushes it to the corresponding Elastic Container Registry repository, tagged with the commit SHA.
3. Lambda functions are updated to point to the new image tag. Lambda caches the image until the next deploy.
4. Fargate task definitions reference the desired image tag and pull the image when a new task starts.
