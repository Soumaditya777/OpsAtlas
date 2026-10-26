
# Database Troubleshooting Runbook

## Purpose
Investigate application incidents that may involve database latency, connectivity, or resource contention.

## Symptoms
- API latency increases while application CPU usage remains normal.
- Database query latency rises or throughput decreases.
- Applications report connection timeouts or connection-pool acquisition timeouts.
- Error rates increase for endpoints that depend on database queries.

## Investigation Steps

### 1. Check database health
Review database availability, connection counts, resource utilization, and recent alerts. Compare current metrics with a known healthy period.

### 2. Inspect connection pools
Check active, idle, waiting, and timed-out connections where those metrics are available. Pool exhaustion may cause application requests to wait even when CPU usage is low.

### 3. Analyze query performance
Review slow-query logs, query execution times, and query plans where available. Investigate long-running transactions and lock contention.

### 4. Trace dependencies
Use distributed traces to determine whether request time is spent acquiring a database connection, executing a query, or waiting on another service.

### 5. Review recent changes
Check application releases, database migrations, configuration changes, traffic spikes, and changes to query patterns.

## Mitigation
- Follow approved procedures for investigating or terminating harmful queries.
- Address lock contention using database-specific operational procedures.
- Consider rollback if a recent change is strongly associated with the incident and rollback is safe.
- Do not increase connection-pool size blindly. Excessive connections can overload the database.

## Escalation
Record the incident time window, affected services and endpoints, database metrics, connection-pool metrics, representative trace IDs, relevant query identifiers, and recent changes.

Escalate to the database or service owner if the cause remains unclear or the incident persists.

## Evidence Limitations
This generic runbook does not define universal connection-pool sizes, query timeout values, or database-specific commands. Consult the relevant service configuration and official database documentation.
