---
name: browser-operations
description: Perform bounded website navigation and browser interactions through an actually exposed browser or computer-use tool.
triggers: browse a website, sign in, navigate UI, fill a form, download, inspect web app
risk: medium; high for account changes, purchases, submissions or destructive actions
required_tools: browser/computer-use connector; authenticated session when needed
---

# Browser Operations Skill

## Purpose
Use browser tools for website tasks; do not pretend web search is interactive browser control.

## Prerequisites
Identify target site, goal, expected state, account boundary and whether authentication is required. Confirm an actual browser tool is exposed.

## Permissions
Public navigation and read-only inspection are allowed. Submissions, account changes, purchases, messages, destructive actions and sensitive data transfer require explicit Owner approval.

## Procedure
1. Verify the browser tool and session state.
2. Navigate to the exact target; confirm domain and page identity.
3. Record the current page state before acting.
4. Execute one bounded action at a time; verify visible result after each.
5. Never bypass MFA, CAPTCHA, access controls or site restrictions.
6. Avoid copying secrets into page fields unless explicitly authorized and safely handled.
7. Capture final URL, state, timestamp and relevant artifact.
8. Stop on unexpected redirects, login challenges, ambiguous controls or irreversible actions.

## Evidence
Record tool/session ID, URL, action, observed result and screenshot/artifact reference where available.

## Failure handling
If no browser connector is exposed, report BLOCKED and name the missing integration. Do not substitute a search result and call it browser execution.

## Completion criteria
The intended page state is visibly verified and no unapproved consequential action occurred.
