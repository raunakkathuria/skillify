---
name: Performance Optimization
description: Identify and resolve performance bottlenecks
category: quality
tags: [performance, optimization, caching, database, profiling, monitoring]
version: "1.0"
author: platform-team
---

# Performance Optimization

Systematic approach to identifying and fixing performance issues.

## Diagnosis

1. Profile application (CPU, memory, I/O)
2. Identify hot paths and bottlenecks
3. Check database query performance (slow query log)
4. Review caching strategy
5. Analyze network latency

## Common Optimizations

- Add database indexes for frequent queries
- Implement caching (Redis, Memcached)
- Use connection pooling
- Optimize N+1 query patterns
- Compress API responses
- Use CDN for static assets

## Monitoring

- Set up APM (Application Performance Monitoring)
- Define SLOs and alert thresholds
- Track p50, p95, p99 latency
- Monitor resource utilization trends
