---
name: api-design
description: "This skill should be used when the user asks to \"design an API\", \"add an endpoint\", \"version an API\", \"define a schema\", or mentions REST, GraphQL, payloads, or API contracts."
triggers:
- api
- rest
- endpoint
- contract
- schema
- graphql
---

# API Design

- Validate all inputs at the boundary; reject unknown fields.
- Use consistent naming, status codes, and error shapes across the surface.
- Make changes backward compatible; version or deprecate instead of breaking.
- Design for idempotency on retried writes.
- Document each endpoint with an example request and response.
