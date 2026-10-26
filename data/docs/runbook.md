
# API Latency Troubleshooting

## Initial investigation

Compare p50, p95, and p99 latency against the last healthy period. Identify affected endpoints and when the problem started.

## Dependency checks

Normal CPU usage does not rule out database connection pool exhaustion, network delays, lock contention, thread pool starvation, or slow downstream services.

Inspect distributed traces and dependency-specific latency before restarting services.

## Recent deployments

If latency increased after deployment, compare the current version and configuration with the last known-good release. Review changed queries, connection pool settings, errors, and downstream timeouts.

## Escalation

Capture timestamps, affected endpoints, representative trace IDs, recent changes, and relevant metrics before escalating to the service owner.
