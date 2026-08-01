---
name: Test Strategy
description: Comprehensive testing strategy for applications
category: quality
tags: [testing, unit-tests, integration, e2e, coverage, quality, tdd]
version: "1.0"
author: qa-team
---

# Test Strategy

A layered approach to software testing.

## Testing Pyramid

1. **Unit Tests** (70%) — Test individual functions/methods in isolation
2. **Integration Tests** (20%) — Test component interactions
3. **E2E Tests** (10%) — Test full user workflows

## Guidelines

- Write tests before fixing bugs (regression prevention)
- Aim for meaningful coverage, not 100%
- Mock external dependencies in unit tests
- Use real databases in integration tests
- Keep tests fast and deterministic

## Tools

- Unit: pytest, jest, go test
- Integration: testcontainers, docker-compose
- E2E: playwright, cypress
- Coverage: coverage.py, istanbul
