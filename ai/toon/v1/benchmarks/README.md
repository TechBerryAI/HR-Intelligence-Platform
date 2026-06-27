# TOON v1 Benchmarks

Conformance benchmarks for TOON wire format and projection mappings.

## Status

Placeholder — benchmark suite to be added. Benchmark data will live alongside category definitions here and in `dataset/lake/benchmark/`.

## Planned coverage

| Category | Validates |
|----------|-----------|
| Round-trip | `toon_dumps(toon_loads_flex(x))` preserves semantics |
| Projection | Normalized schema → TOON via `mappings/*.yaml` |
| Validation | Wire format rules in `validation/validation.yaml` |

## Related documentation

- [TOON package](../../README.md)
- [Benchmark strategy](../../../docs/BENCHMARK_STRATEGY.md)
- [Data lake benchmark stage](../../../dataset/lake/benchmark/README.md)
