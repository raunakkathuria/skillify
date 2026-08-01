---
name: Code Review
description: Systematic code review process for pull requests
category: quality
tags: [code-review, pull-request, quality, best-practices, patterns]
version: "1.0"
author: team-lead
---

# Code Review

A structured approach to reviewing code changes in pull requests.

## Steps

1. Check for correctness — does the code do what it claims?
2. Review error handling and edge cases
3. Assess readability and naming conventions
4. Look for performance implications
5. Verify test coverage for new logic
6. Check for security vulnerabilities
7. Ensure documentation is updated

## Checklist

- [ ] No hardcoded secrets or credentials
- [ ] Error messages are helpful
- [ ] Functions are reasonably sized
- [ ] Tests cover happy path and error cases
