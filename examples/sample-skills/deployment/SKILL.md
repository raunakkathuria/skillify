---
name: CI/CD Deployment
description: Continuous integration and deployment pipeline setup
category: infrastructure
tags: [deployment, ci-cd, pipeline, automation, docker, kubernetes, rollback]
version: "3.0"
author: devops-team
---

# CI/CD Deployment

Setting up and managing deployment pipelines.

## Pipeline Stages

1. **Build** — Compile code, install dependencies
2. **Test** — Run unit and integration tests
3. **Security Scan** — SAST/DAST analysis
4. **Package** — Build Docker image, push to registry
5. **Deploy Staging** — Deploy to staging environment
6. **Smoke Tests** — Verify basic functionality
7. **Deploy Production** — Blue/green or canary deployment

## Rollback Strategy

- Keep last 3 versions available for instant rollback
- Automate rollback on health check failures
- Use feature flags for gradual rollouts

## Tools

- GitHub Actions, GitLab CI, Jenkins
- Docker, Kubernetes, Helm
- ArgoCD for GitOps
