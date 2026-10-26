
# Deployment and Rollback Runbook

## Purpose
Investigate service degradation that begins during or shortly after an application deployment.

## Trigger Conditions
- API latency or error rates increase after a release.
- Health checks fail or application instances repeatedly restart.
- A new application version produces unexpected behavior.
- A configuration or dependency change coincides with an incident.

## Investigation Steps

### 1. Establish the timeline
Identify when the incident started, the affected service, and the currently deployed version.

### 2. Compare service metrics
Compare p50, p95, and p99 latency, error rates, traffic, and resource utilization before and after deployment.

### 3. Review release changes
Inspect release notes, code changes, configuration updates, database migrations, and dependency upgrades.

### 4. Inspect logs and traces
Look for new exceptions, slow downstream calls, failed requests, and changes in request execution paths.

### 5. Check deployment health
Review deployment status, instance health, readiness checks, restart events, and rollout progress.

### 6. Determine the scope
Establish whether the problem affects all instances or only instances running the new version.

## Rollback Decision
Consider rollback when evidence strongly suggests that a recent release caused customer-impacting degradation and an approved rollback path exists.

Before proceeding, verify whether database migrations, schema changes, or data-format changes could make rollback unsafe.

Follow the organization's change-management and incident-response procedures. Do not perform a rollback solely because two events occurred at the same time.

## Recovery Verification
After an approved rollback or mitigation:
- Confirm that application instances and readiness checks are healthy.
- Compare latency and error rates against the known healthy baseline.
- Test affected endpoints using approved health checks.
- Monitor for recurrence of the incident.

## Escalation
Record the release identifier, deployment timestamps, configuration changes, affected endpoints, relevant logs, trace IDs, mitigation steps, and recovery evidence.

Escalate to the service owner if the issue persists or rollback safety is uncertain.

## Evidence Limitations
This runbook does not specify organization-specific approval requirements, deployment commands, or rollback tooling. Consult the service's official release procedure before taking action.
