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
      AWS CloudTrail Management events
- Covers:
      Actor / Time / Origin, Mechanism, Action
- Why collect it:
      Records AWS-native VM access activity such as SSM Session Manager or EC2 Instance Connect API calls, including which AWS identity initiated the access, when it occurred, where it originated, and which EC2 instance was targeted.
- Required setup:
      Enable CloudTrail management event logging.
- Notes / gaps:
      - CloudTrail is useful for AWS-native access paths, but ordinary direct SSH/RDP connections are not represented as IAM API activity in the same way.
      - CloudTrail does not show arbitrary commands or other activity performed inside the VM.

### Telemetry Source 2
- Telemetry source:
      AWS VPC Flow Logs
- Covers:
      Origin, Mechanism, Action
- Why collect it:
      - Records network-flow metadata within the AWS virtual private network (VPC), helping determine whether a VM received direct network connectiosn such as SSH or RDP.
      - It can provide source/destination IPs, ports, protocol, timing, traffic volume, and whether traffic was accepted or rejected.
- Required setup:
      Enable VPC Flow Logs for the in-scope VPC, subnet, or network interfaces.
- Notes / gaps:
      - VPC Flow Logs provide network-flow metadata rather than authentication details, commands, or application content.
      - A connection such as "external IP --> EC2:22" does not by itself show whether SSH authentication succeeded or what happened after login.
      - Flow records should therefore be correlated with host authentication / endpoint telemetry when deeper investigation is required.

### Telemetry Source 3
- Telemetry source: 
      AWS IAM + network-access configuration, supplemented by AWS Config history
- Covers:
      Mechanism / Permission
- Why collect it:
      - Determines why the VM access path was possible.
      - IAM configuration helps explain AWS-native access permissions such as SSM or EC2 Instance Connect, while network configuration such as Security Groups helps explain whether direct SSH/RDP traffic was permitted.
      - AWS Config history can help reconstruct the relevant access-control configuration that existed around incident time.
- Required setup:
      - Give the investigator read-only access to relevant IAM and network configuration.
      - Enables AWS Config recording for relevant resources when historical configuration reconstruction is needed.
- Notes / gaps:
      - The required configuration evidence depends on the access path: IAM permissions matter more for AWS-native access, while network controls matter more for direct SSH/RDP.
      - Historical state is only available if the relevant configuration was already being recorded.

### Telemetry Source 4
- Telemetry source:
      EC2 host login / authentication logs + Endpoint Telemetry
- Covers:
      Actor, Action / Follow-on
- Why collect it:
      - Enriches network and cloud-access evidence with activity observed inside the EC2 VM. 
      - It can help determine whether authentication succeeded, which host user was involved, and what processes, commands, file activity, credential access, or subsequent network activity occurred after access.
- Required setup:
      Collect OS login / authentication logs and endpoint telemetry from the in-scope EC2 instances, using the selected host logging or endpoint-security mechanism.
- Notes / gaps:
      - The exact visibility depends on which host telemtry is enabled.
      - CloudTrail and VPC Flow Logs alone cannot reconstruct arbitrary activity occurring inside the VM.
      - Host / endpoint telemetry can be correlated with VPC Flow Logs to turn connection metadata into richer investigation evidence.

---

## Scenario 06 - Cloud Data Collection and Exfiltration

### Telemetry Source 1
- Telemetry source:
      AWS CloudTrail management events
- Covers:
      Actor / Time / Origin, Mechanism, 
- Why collect it:
      Records AWS management / API activity related to the identity performing the collection or transer, including the originating identity/session, time, source, role-assumption activity, and related control-plane actions.
- Required setup:
      Enable CloudTrail management event logging.
- Notes / gaps:
      - CloudTrail management events do not provide complete visibility into S3 object-level reads/writes.
      - Organization-specific context such as an approved backup, migration, or analytics workflow is not available from CloudTrail alone.

### Telemetry Source 2
- Telemetry source:
      CloudTrail S3 data events
- Covers:
      Actor / Time / Origin, Action / Follow-on
- Why collect it:
      - Records S3 object-level data-plane activity such as reading, writing, or copying objects.
      - This allows the investigator to determine which identity accessed which data and whether object-level actions may represent collection or exfiltration.
      - For example, a "GetObject" request from an attacker-controlled client using compromised credentials can directly retrieve victim data to the attacker's system, while a "CopyObject" operation may represent exfiltration if the destination is an unauthorized or attacker-controlled bucket/account.  
- Required setup:
      Enable S3 data-event logging across all in-scope S3 buckets.
- Notes / gaps:
      - S3 object-level data-plane operations require CloudTrail data-event logging and are not fully captured by management-event logging alone.
      - A "GetObject" or "CopyObject" event does not by itself prove malicious exfiltration, the identity, source, destination, volume, timing, and expected business activity must also be considered.
      - The current collection policy enables coverage across all in-scope S3 buckets to preserve complete investigation visibility, while production deployments may scope data-event collection to control cost and volume.
      - The current scenario primarily assumes S3 API / cloud-native collection and transfer. A network-heavy path such as "S3 --> EC2 staging --> external destination" would require additional network and host telemetry such as VPC Flow Logs and EC2 host / endpoint telemetry.

### Telemetry Source 3
- Telemetry source: 
      AWS IAM / S3 access configuration + AWS Config configuration history
- Covers:
      Mechanism / Permission
- Why collect it:
      - Determines why the identity was allowed to access or transer the S3 data, including IAM permissions and relevant S3 access configuration.
      - AWS Config history can help reconstruct the access configuration that existed around the time of the suspicious activity. 
- Required setup:
      - Give the investigator read-only access to relevant IAM and S3 access configuration.
      - Enable AWS Config recording for relevant supported resources when historical configuration reconstruction is needed.
- Notes / gaps:
      - Currnet configuration may not represent the permissions that existed at incident time.
      - Historical configuration is only available if the relevant resources were already being recorded.
      - Configuration evidence can show whether access was technically permitted, but not whether the collection or transfer was organizationally approved.



---

## Scenario 07 - Cloud Firewall Manipulation

### Telemetry Source 1
- Telemetry source:
      AWS CloudTrail management events
- Covers:
      Actor / Time / Origin, Action
- Why collect it:
      Records AWS API activity used to create, modify, or remove cloud network-access controls, including which AWS identity initiated the change, when and where it originated, and the specific rule/configuration change requested through the API call (e.g., adding an ingress rule that allows TCP port 22 from '0.0.0.0/0'.)
- Required setup:
      Enable CloudTrail management event logging.
- Notes / gaps:
      - CloudTrail shows that a network-control change occurred, but does not by itself provide the complete network-control state before and after the change.
      - It therefore shows what modification was requested, while the actual resulting and historical configuration should be checked through the network-control configuration and AWS Config history.
      - It also does not show whether the newly permitted network path was actually used afterward.

### Telemetry Source 2
- Telemetry source:
      IAM + firewall / network access-control configuration + AWS Config history (e.g., Security Grous, NACLs, AWS Network Firewall where used)
- Covers:
      Mechanism / Permission, Action
- Why collect it:
      - IAM configuration explains why the AWS identity had permission to modify the firewall / network controls.
      - Firewall / network-access configuration shows what traffic was actually permitted or restricted.
      - AWS Config history helps reconstruct how those network-control settings changed before, during, and after the suspicious activity.
- Required setup:
      - Give the investigator read-only access to relevant IAM and network access-control configuration.
      - Enable AWS Config recording/history for the network resources in scope.
- Notes / gaps:
      - CloudTrail shows the requested change action, while this source shows he actual network-control state resulting from those changes.
      - Security Groups, NACLs, and AWS Network Firewall represent different AWS network-control mechanisms. 
      - Historical state is only available if the relevant configuration was already being recorded.
      - Configuration evidence shows what network access was permitted or restricted, but does not by itself show whether hat access path was actually used.

### Telemetry Source 3
- Telemetry source:
      AWS VPC Flow Logs
- Covers:
      Origin, Action / Follow-on
- Why collect it:
      - Records network-flow metadata after the firewall / network-control change, including soruce/destination IPs, ports, protocol, timing, traffic volume, and whether traffic was accepted or rejected.
      - This allows the investigator to check whether traffic that matches the newly opened rule actually occured. 
      - For example, if TCP port 22 was opened to '0.0.0.0/0', the investigator can check whether inbound traffic to that resource on port 22 apeared aterward. 
- Required setup:
      Enable VPC Flow Logs for the in-scope VPC, subnet, or network interfaces.
- Notes / gaps:
      - VPC Flow Logs can show whether traffic matching the newly permitted firewall rule occurred after the configuration change.
      - However, VPC Flow Logs do not show whether that traffic resulted in a successful login or waht activity occurred inside the target host.
      - Host login/authentication logs and host/endpoint telemetry are required to investigate successful access and post-connection activity.


---

## Scenario 08 - Resource Creation in an Unused Cloud Region

### Telemetry Source 1
- Telemetry source:
      AWS CloudTrail multi-region management events
- Covers:
      Actor / Time / Origin, Action
- Why collect it:
      - Detects AWS resource-creation / configuration API activity across all monitored AWS regions, including regions the organization normally does not use.
      - It identifies which AWS identity initiated the resource creation, when and where the request originated, which region was targeted, and what resource-creation / configuration action was requested. 
- Required setup:
      Enable always-on multi-region CloudTrail management event logging so that activity is collected even from regions normally unused by the organization.
- Notes / gaps:
      - Resource inventory / configuration history can also show that a resource appeared in a region and what state it had. 
      - CloudTrail's main additional value here is identifying the identity/session that initiated the creation and the corresponding API request.
      - CloudTrail records the creation/configuration event, but does not show the runtime behavior of the newly created workload.

### Telemetry Source 2
- Telemetry source:
      AWS IAM configuration + resouce / configuration inventory + AWS Config history 
- Covers:
      Mechanism / Permission, Context
- Why collect it:
      - IAM configuration explains why the AWS identity was permitted to create resources in that region.
      - Resource inventory and configuration show which resources currently exist in each region and how they are configured (e.g., resource type, region, attached IAM role, network configuration, and other relevant settings).
      - AWS Config history shows when those resources appeared and how their configurations changed over time, helping determine whether resources had historically existed in that region or whether the region was previously unused. 
- Required setup:
      - Give the investigator read-only access to relevant IAM and AWS resource configuration APIs.
      - Enable AWS Config recording/history across all monitored AWS regions, including regions normally unused by the organization, for the resource types that need historical configuration visibility.
      - Maintain historical region/resource usage so newly used (previously unused) regions can be identified.
- Notes / gaps:
      - Resource inventory reflects resources that actually exist after creation, while configuration history can show when those resources/configurations appeared or changed over time. 
      - Historical configuration evidence is only available where AWS Config supported the relevant resource type/region and recording was already enabled.
      CloudTrail may still provide the corresponding resource-creation / change API events even when AWS Config history is unavailable. 
      - Historical resource usage can indicate that a region was previously unused, but organization-specific reasons for intentionally entering a new region (e.g., approved expansion, disaster recorvery, or compliance requirements) may require an external organizational evidence source. 

### Telemetry Source 3
- Telemetry source:
      Workload / runtime telemetry for newly created resources
      (e.g., CloudWatch Log/Metrics, GuardDuty Runtime Monitoring, or other host/endpoint telemtry where applicable)
- Covers:
      Action / Follow-on
- Why collect it:
      - Determines what the newly created resource actually did after creation, including both resource-intensive and non-resource intensive behavior.
      - Depending on the resource type and available monitoring, this may include resource usage, OS/application activity, OS/application activity, process execution, file activity, commands, network connections, or other runtime security events.
- Required setup:
      - Preconfigure automatic runtime-monitoring / logging policies across all AWS regions, so that supported newly created workloads begin producing/streaming runtime telemetry at or near creation time, regardless of whether they are created in normally used or unused regions.
      - Use automatically managed GuardDuty Runtime Monitoring, logging agents, or other suitable collectors where supported.
- Notes / gaps:
      - CloudWatch Logs/Metrics, GuardDuty Runtime Monitoring, and host/endpoint telemetry are different mechanisms for collecting different forms of workload/runtime evidence. 
      -- The important requirement here is that the necessary runtime evidence begins collected automatically rather than only after the suspicious resource is discovered.
      - Runtime visibility depends on the resource type, region, and monitoring-service support.
      - If the preferred runtime-monitoring mechanism is unsupported, use another automatically deployable collector where possible. If no suitable mechanism is available, explicitly record a runtime-visibility gap.
      - Enabling runtime monitoring only after suspicious activity is detected may lose evidence from the resource's initial behavior.
      - Deeper runtime monitoring can add cost at scale, so production deployments may selectively scope expensive telemetry while preserving broad multi-region resource-creation visibility through CloudTrail.



