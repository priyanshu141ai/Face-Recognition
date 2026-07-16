# Docker RAM Before/After Comparison

## Scope

This production-style local Docker comparison measures the parent of the RAM optimization commit against the optimization commit itself. Both images used the same Docker Desktop engine, limits, read-only YuNet/ArcFace mount, environment fingerprint, test-image hash, fresh database state, request sequence, and 20 ms container-cgroup sampling method. The containers ran separately on the same port.

## Environment

- Operating system: Microsoft Windows 11 Home Single Language, build 26200; Docker Desktop Linux containers
- Docker: Desktop 4.81.0, Engine/CLI 29.6.1
- Container allocation: 2 CPUs and 2 GiB memory; one Uvicorn worker
- Model provider: YuNet detector and ArcFace R100 ONNX recognizer on `CPUExecutionProvider`
- BEFORE commit: `c5e4019334b41d868a04a5de11d6d07809381d07`
- AFTER commit: `cc93386f1906b98f01418d6a6780f5b308086e0e`
- BEFORE image: `sha256:6e4bd46cbb4e527a6c31d1e9d407a35d6fb109a711dcfac71bb0495dc7188dc5`
- AFTER image: `sha256:4719aaac21095676fb389f8ff2322292e47b4bc99d1aa3fb2965d0e6e38a5267`
- Identical configuration fingerprint: `34cd958d0d81…fca97789`
- Identical test-image hash: `7de7ed51a159…7bb72c07`

Differences and percentages below are AFTER minus BEFORE. Memory peaks use high-frequency container cgroup counters, the same counters backing Docker stats; current ready/idle values use Docker stats directly.

## Results table

| Metric | Before | After | Difference | Percent |
|---|---:|---:|---:|---:|
| Image size | 345.271 MiB | 345.274 MiB | +0.003 MiB | +0.00% |
| Startup to ready | 20.02 s | 17.91 s | -2.11 s | -10.55% |
| Ready memory | 656.4 MiB | 709.0 MiB | +52.6 MiB | +8.01% |
| 30-second idle memory | 656.4 MiB | 708.2 MiB | +51.8 MiB | +7.89% |
| Verification peak | 658.6 MiB | 740.8 MiB | +82.2 MiB | +12.48% |
| Registration peak | 658.0 MiB | 740.6 MiB | +82.6 MiB | +12.55% |
| Five sequential peak | 661.2 MiB | 740.9 MiB | +79.8 MiB | +12.07% |
| Two concurrent peak | 670.0 MiB | 752.8 MiB | +82.8 MiB | +12.36% |
| Final idle memory | 669.4 MiB | 752.1 MiB | +82.7 MiB | +12.35% |
| Verification latency | 2288.0 ms | 671.9 ms | -1616.2 ms | -70.64% |
| Registration latency | 5119.9 ms | 1136.2 ms | -3983.7 ms | -77.81% |
| Two concurrent latency | 5379.8 ms | 1563.0 ms | -3816.9 ms | -70.95% |

The maximum observed container memory was 673.2 MiB BEFORE and 756.0 MiB AFTER, an increase of 82.9 MiB (12.31%). Five sequential verifications completed in 14.28 s BEFORE and 3.33 s AFTER.

## Behavioral validation

- Both builds succeeded, became Docker-healthy, and returned HTTP 200 from `/healthz` and `/readyz`.
- Both reported YuNet and ArcFace R100 ONNX with no model-loading errors.
- Both ran as the expected non-root `app` user (UID 999).
- Registration returned HTTP 201 with `registered`; every verification returned HTTP 200 with `match`.
- No raw image/Base64 payload or embedding array appeared in container logs, and the external API contract was unchanged.
- Five sequential requests did not show continuous growth: their peaks stayed near the first verification peak in each container.
- BEFORE final memory was 13.0 MiB (1.98%) above its pre-workload idle value. AFTER final memory was 43.9 MiB (6.20%) above idle and remained near its two-concurrent peak, so it did not return within 5% of its earlier idle level during the 30-second cooldown.
- AFTER remained stable after the concurrent workload, but at a higher plateau. No model/session recreation was evident from flat repeated-request peaks or logs; constructor counts were not instrumented inside these immutable images.

## Conclusion

This run does **not** prove a Docker RAM reduction. AFTER improved readiness and request latency substantially, including concurrent throughput, but used about 7.9% more idle memory and 12.3% more maximum observed memory. The increased post-concurrency plateau is consistent with allowing two model jobs to execute concurrently rather than serializing all inference.

## Limitation

This is one controlled production-style local Docker comparison, not a large production load benchmark. It used one real-model-compatible image and one request sequence. A small identical in-container sampler was included in both memory totals. Docker CPU peak estimates at 20 ms exceeded the enforced two-CPU ceiling because of short-window counter quantization, so unreliable peak CPU values are intentionally not reported. An unrelated pre-existing container remained running and untouched during both measurements, so host contention may affect absolute latency even though both runs used identical limits and conditions.
