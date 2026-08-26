# Telemetry Evidence Matrix

One block per telemetry source.
One or more telemetry-sources for each scenario.

For **Covers**, use one or more of:
- Actor / Time / Origin
- Mechanism / Permission
- Action / Follow-on
- Context

---

## Scenario 01 - Credential Persistence / Additional Cloud Credentials

### Telemetry Source 1
- Telemetry source: 
      AWS CloudTrail management events
- Covers: 
      Actor/Time/Origin, Mechanism/Permission, Action/Follow-on
- Why collect it: 
      Records who created the new access key and subsequent AWS management/API activity 
- Required setup:
      Enable Cloudtrail management event logging option.
- Notes / gaps:
      Does not provide organization-specific context such as whether the key creation was approved for onboarding or known automation.

---

## Scenario 02 - Temporary Privilege Escalation / Role Abuse

### Telemetry Source 1
- Telemetry source: 
      AWS CloudTrail management events
- Covers: 
      Actor,Time,Origin, Mechanism, Action/Follow-on
- Why collect it: 
      Records the AssumeRole activity, including the originating identity/session, time, source, target role, and subsequent AWS management/API activity performed using the elevated role session.  
- Required setup:
      Enable CloudTrail management event logging option.
- Notes / gaps:
      - CloudTrail shows that the role assumption occured and what AWS API activity followed, but does not by itself explain whether the underlying IAM permission/trust configuraton made the privilege path legitimate or overly permissive. 
      - Organization-specific context such as an approved deployment or maintenance window is also not contained in CloudTrail.

### Telemetry Source 2
- Telemetry source: 
      AWS IAM role / policy configuration + AWS Config configuration history
- Covers:
      Mechanism / Permission
- Why collect it:
      To understand why the source identity was able to assume the higher-privileged role and whether that privilege path was expected or overly permissive.
      AWS Config history can be used to check what the relevant IAM configuration looked like around the time of the suspicious role assumption.
- Required setup:
      Give the investigator a dedicated read-only AWS role that can retrieve IAM roles and policy configurations through AWS APIs.
      Enable AWS Config recording for the relevant IAM resources and retain configuration history.
- Notes / gaps:
      - This is configuration queried when needed rather than a continuous event log. 
      - Historical configuration is only available if the relevant IAM resources were already being recorded by AWS Config at the time.

---

## Scenario 03 - Unauthorized Serverless Execution

### Telemetry Source 1
- Telemetry source: 
      AWS CloudTrail management events
- Covers: 
      Actor / Time / Origin, Action / Follow-on
- Why collect it:
      In this project, AWS Lambda is the serverless execution service used for this scenario.
      CloudTrail records AWS API actions used to create or modify the Lambda function,
      incuding which AWS identity performed them, when they occured, and where they originated.
      It can also show follow-on AWS API actions performed after the function is created or modified.
- Required setup: 
      Enable CloudTrail management event logging option.
- Notes / gaps: 
      CloudTrail records AWS API activity, not aribitrary computation occuring inside the Lambda code itself. Some resource-level actions may require additional data-event logging.

### Telemetry Source 2
- Telemetry source: 
      AWS Lambda configuration + IAM execution-role configuration + AWS Config configuration history 
- Covers:
      Mechanism / Permission
- Why collect it:
      - Because Lambda is the serverless execution mechanism used in this scenario, its configuration shows how the serverless function was set up to run.
      - The IAM execution-role configuration shows what AWS resources/actions the function is permitted to access when it executes.
      - AWS Config history can help reconstruct the Lambda/IAM configuration that existed around the time of the suspicious activity instead of relying on the current state.
- Required setup:
      Give the investigator read-only AWS API access to retrieve Lambda configuration and the IAM role/policies used by the function.
      Enable AWS Config recording for the relevant Lambda and IAM resources where supported.
- Notes / gaps:
      - The Lamda configuration is set by the user, administrator, or deployment system. AWS separately manages the underlying servers and scaling.
      - This is configuration queried on demand rather than a continuous event log.
      - Historical configuration is only available if the relevant resources were already being recorded by AWS Config at the time. 

### Telemetry Source 3
- Telemetry source:
      AWS EventBridge / Lambda trigger configuration
- Covers:
      Mechanism / Permission, Action / Follow-on
- Why collect it:
      Lambda can execute not only through direct invocation but also in response to schedules or events. 
      EventBridge is an AWS service that provides such scheduled / event-driven triggers, so this config helps determine whether repeated or event-triggered serverless executon was configured.
- Required setup:
      Give the investigator read-only AWS API access to read EventBridge rule and Lambda trigger configuration. Where supported, enable AWS Config recording for relevant trigger/rule resources if historical configuration reconstruction is needed.
- Notes / gaps:
      - This is configuration evience rather than continuous telemetry.
      - CloudTrail can separately show who created or modified the trigger configuration.
      - Historical trigger configuration may only be available if the relevant resource was being recorded by AWS Config.
      - The configuration itself does not establish whether the automation was organizatioanlly approved.

---

## Scenario 04 - Suspicious Cloud Resource Discovery

### Telemetry Source 1
- Telemetry source:
      AWS CloudTrail management events + relevant S3 data events
- Covers:
      Actor / Time / Origin, Mechanism, Action / Follow-on 
- Why collect it:
      - Records which AWS identity performed resource-discovery API calls, when and from where they were issued, and which resources/services were enumerated.
      - It can also show subsequent AWS API activity by the same identity, such as accessing resources after discovery.
- Required setup:
      - Enable CloudTrail management event logging.
      - Enable S3 data event-logging for all S3 buckets in the scoped AWS lab account. 

- Notes / gaps:
      - CloudTrail is the strongest for AWS API-based discovery.
      - Organization-specific context such as whether the activity belonged to an approved inventory or troubleshooting job is not available from CloudTrail alone.
      - S3 object-level operations are not fully captured by CloudTrail management events alone and require S3 data-event logging. 
      - Current collection policy is to enable coverage across all in-scope S3 buckets to preserve complete investigation visibility, while production deployments may scope data-event collection to control cost and volume.

### Telemetry Source 2
- Telemetry source:
      AWS IAM role / policy configuration + AWS Config configuration history
- Covers:
      Mechanism / Permission
- Why collect it:
      - Shows why the identity was permitted to perform broad resource discovery and whether the permission path was expected or overly permissive.
      - AWS Config history can help reconstruct the relevant configuration around the time of the discovery activity rather than relying only on current state.
- Required setup:
      - Give the investigator read-only access to relevant IAM role / policy configuration.
      - Enable AWS Config recording for the relevant IAM resources where supported.
- Notes / gaps:
      Current IAM configuration is queried on demand.
      Historical configuration is only available if AWS Config was already recording the relevant resources at the time.

---

## Scenario 05 - Unauthorized Direct Cloud VM Access

### Telemetry Source 1
- Telemetry source:
- Covers:
- Why collect it:
- Required setup:
- Notes / gaps:

### Telemetry Source 2
- Telemetry source:
- Covers:
- Why collect it:
- Required setup:
- Notes / gaps:

### Telemetry Source 3
- Telemetry source:
- Covers:
- Why collect it:
- Required setup:
- Notes / gaps:

VPC Flow Logs?


---

## Scenario 06 - Cloud Data Collection and Exfiltration

### Telemetry Source 1
- Telemetry source:
- Covers:
- Why collect it:
- Required setup:
- Notes / gaps:

### Telemetry Source 2
- Telemetry source:
- Covers:
- Why collect it:
- Required setup:
- Notes / gaps:

### Telemetry Source 3
- Telemetry source:
- Covers:
- Why collect it:
- Required setup:
- Notes / gaps:


S3 ?  data events via clout trail ? 


---

## Scenario 07 - Cloud Firewall Manipulation

### Telemetry Source 1
- Telemetry source:
- Covers:
- Why collect it:
- Required setup:
- Notes / gaps:

### Telemetry Source 2
- Telemetry source:
- Covers:
- Why collect it:
- Required setup:
- Notes / gaps:

### Telemetry Source 3
- Telemetry source:
- Covers:
- Why collect it:
- Required setup:
- Notes / gaps:


VPC Flow Logs?

---

## Scenario 08 - Resource Creation in an Unused Cloud Region

### Telemetry Source 1
- Telemetry source:
- Covers:
- Why collect it:
- Required setup:
- Notes / gaps:

### Telemetry Source 2
- Telemetry source:
- Covers:
- Why collect it:
- Required setup:
- Notes / gaps:

### Telemetry Source 3
- Telemetry source:
- Covers:
- Why collect it:
- Required setup:
- Notes / gaps:



CloudWatch Logs / application or host logs → workload/runtime behavior.?

GuardDuty? -- to confirm if it is under-monitored? 

