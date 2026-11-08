# Workflow: Plugin / Tool Onboarding

**Adapted from:** os-factory/har plugin factory and 0xenzyme adapter contracts.

1. Research official provider documentation and supported host capabilities.
2. Define adapter contract: inputs, outputs, auth boundary, allowed operations, timeout, error model and evidence.
3. Add a disabled-by-default registry entry.
4. Add a health check and deterministic fixture tests.
5. Validate in a real supported environment without exposing secrets.
6. Enable only after Owner approval and a successful end-to-end test.
7. Record provenance, license, host limitations and rollback procedure.
