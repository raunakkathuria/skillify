---
name: REST API Design
description: Design RESTful APIs following best practices and conventions
category: architecture
tags: [api, rest, http, design, endpoints, versioning, documentation]
version: "1.5"
author: api-guild
---

# REST API Design

Guidelines for designing clean, consistent REST APIs.

## URL Structure

- Use nouns, not verbs: `/users` not `/getUsers`
- Use plural nouns: `/users` not `/user`
- Nest resources logically: `/users/{id}/orders`
- Keep URLs shallow (max 3 levels deep)

## HTTP Methods

- GET: Retrieve resources (idempotent)
- POST: Create new resources
- PUT: Replace entire resource
- PATCH: Partial update
- DELETE: Remove resource

## Versioning

- Use URL versioning: `/v1/users`
- Or header versioning: `Accept: application/vnd.api+json; version=1`

## Error Responses

Always return structured error objects with code, message, and details.
