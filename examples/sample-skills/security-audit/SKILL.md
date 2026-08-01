---
name: Security Audit
description: Security review checklist for applications and infrastructure
category: security
tags: [security, audit, vulnerabilities, owasp, authentication, encryption]
version: "2.0"
author: security-team
---

# Security Audit

Comprehensive security review for applications.

## OWASP Top 10 Check

1. Injection (SQL, NoSQL, OS command)
2. Broken Authentication
3. Sensitive Data Exposure
4. XML External Entities (XXE)
5. Broken Access Control
6. Security Misconfiguration
7. Cross-Site Scripting (XSS)
8. Insecure Deserialization
9. Using Components with Known Vulnerabilities
10. Insufficient Logging & Monitoring

## Authentication Review

- Multi-factor authentication available?
- Password policy enforced?
- Session management secure?
- Token rotation implemented?

## Data Protection

- Encryption at rest and in transit
- PII handling compliant with regulations
- Secrets management (no hardcoded credentials)
