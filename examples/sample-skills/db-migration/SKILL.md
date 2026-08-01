---
name: Database Migration
description: Safe database schema migration process with rollback support
category: infrastructure
tags: [database, migration, schema, sql, rollback, deployment]
version: "2.0"
author: dba-team
---

# Database Migration

Step-by-step guide for safe database schema migrations.

## Pre-flight Checks

1. Backup the current database state
2. Review migration SQL for correctness
3. Test migration on staging environment
4. Estimate downtime (if any)
5. Prepare rollback script

## Execution

1. Put application in maintenance mode (if needed)
2. Run migration script
3. Verify schema changes
4. Run integration tests against new schema
5. Remove maintenance mode

## Rollback Plan

If migration fails:
1. Execute rollback script
2. Verify original schema is restored
3. Notify team of failure
4. Investigate root cause
