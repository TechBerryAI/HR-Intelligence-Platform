# HRMS Tests

Component tests are colocated with their owners:

| Component | Location |
|-----------|----------|
| AI Runtime | `ai/runtime/tests/` |
| AI Providers | `ai/providers/ollama/tests/` |
| Capabilities | `ai/capabilities/*/tests/` |
| Dataset extraction | `ai/dataset/extraction/tests/` |
| Dataset proposals | `ai/dataset/proposals/tests/` |
| Dataset factory inspector | `ai/dataset/factory/inspector/tests/` |
| TOON | `ai/toon/v1/tests/` |
| Database preflight | `scripts/database/test_db_connection.py` |

Run AI tests from `ai/`:

```bash
cd ai && pytest
```
