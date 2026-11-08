---
name: database-migrations
description: "This skill should be used when the user asks to \"write a migration\", \"change the schema\", \"backfill data\", \"add an index\", or mentions SQL, database changes, or reversible migrations."
triggers:
- migration
- schema change
- sql
- backfill
- index
---

# Database Migrations

- Keep every migration reversible; include the down path.
- Never drop or rename a column in the same release that stops writing to it; expand, migrate, then contract.
- Backfill in batches; never hold a long transaction on a live table.
- Add indexes concurrently where the engine supports it.
- Test the migration against a realistic dataset, not an empty one.
