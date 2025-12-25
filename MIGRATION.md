# Migration Notes

- Existing demos can opt into the modular stack by instantiating `VectorMemory` with `backend_name="local"` for deterministic tests.
- Replace legacy substring memory calls with `VectorMemory.search`, which now returns scored `SearchHit` objects.
- Tool imports must move into the `cuga.modular.tools.*` namespace to satisfy dynamic import guardrails.
- Coordinators should be updated to the round-robin `CoordinatorAgent` to preserve fairness guarantees.
