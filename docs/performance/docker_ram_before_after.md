# Docker RAM Before/After Comparison

## Scope

This production-style local Docker comparison measures the parent of the RAM optimization commit against the optimization commit itself. Both images used the same otherwise-idle Docker Desktop engine, limits, read-only YuNet/ArcFace mount, environment fingerprint, test-image hash, fresh database state, request sequence, and 20 ms Docker-style working-set sampling method. The containers ran separately on the same port.

## Environment

- Operating system: Microsoft Windows 11 Home Single Language, build 26200; Docker Desktop Linux containers
- Docker: Desktop 4.81.0, Engine/CLI 29.6.1
- Container allocation: 2 CPUs and 2 GiB memory; one Uvicorn worker
- Model provider: YuNet detector and ArcFace R100 ONNX recognizer on `CPUExecutionProvider`
- BEFORE commit: `c5e4019334b41d868a04a5de11d6d07809381d07`
- AFTER commit: `cc93386f1906b98f01418d6a6780f5b308086e0e`
- BEFORE image: `sha256:6e4bd46cbb4e527a6c31d1e9d407a35d6fb109a711dcfac71bb0495dc7188dc5`
- AFTER image: `sha256:4719aaac21095676fb389f8ff2322292e47b4bc99d1aa3fb2965d0e6e38a5267`
- Identical configuration fingerprint: `55bbdcacd4d7…505d072a`
- Identical test-image hash: `7de7ed51a159…7bb72c07`

Differences and percentages below are AFTER minus BEFORE. Memory peaks use `memory.current - inactive_file`, matching Docker CLI's Linux working-set presentation; current ready/idle values use Docker stats directly.

## Results table

| Metric | Before | After | Difference | Percent |
|---|---:|---:|---:|---:|
| Image size | 345.271 MiB | 345.274 MiB | +0.003 MiB | +0.00% |
| Startup to ready | 17.09 s | 16.07 s | -1.02 s | -5.98% |
| Ready memory | 661.1 MiB | 696.7 MiB | +35.6 MiB | +5.38% |
| 30-second idle memory | 661.3 MiB | 696.6 MiB | +35.3 MiB | +5.34% |
| Verification peak | 693.3 MiB | 726.2 MiB | +32.9 MiB | +4.75% |
| Registration peak | 692.8 MiB | 726.6 MiB | +33.8 MiB | +4.88% |
| Five sequential peak | 695.9 MiB | 727.3 MiB | +31.4 MiB | +4.52% |
| Two concurrent peak | 705.6 MiB | 738.7 MiB | +33.1 MiB | +4.70% |
| Final idle memory | 703.8 MiB | 737.8 MiB | +34.0 MiB | +4.83% |
| Verification latency | 2663.4 ms | 655.9 ms | -2007.6 ms | -75.38% |
| Registration latency | 4902.1 ms | 1044.6 ms | -3857.5 ms | -78.69% |
| Two concurrent latency | 5491.2 ms | 1613.2 ms | -3878.0 ms | -70.62% |

The maximum observed working set, including startup, was 707.8 MiB BEFORE and 779.8 MiB AFTER, an increase of 72.0 MiB (10.17%). Five sequential verifications completed in 14.30 s BEFORE and 3.13 s AFTER.

## Behavioral validation

- Both builds succeeded, became Docker-healthy, and returned HTTP 200 from `/healthz` and `/readyz`.
- Both reported YuNet and ArcFace R100 ONNX with no model-loading errors.
- Both ran as the expected non-root `app` user (UID 999).
- Registration returned HTTP 201 with `registered`; every verification returned HTTP 200 with `match`.
- No raw image/Base64 payload or embedding array appeared in container logs, and the external API contract was unchanged.
- Five sequential requests did not show continuous growth: their peaks stayed near the first verification peak in each container.
- BEFORE final memory was 42.5 MiB (6.43%) above its pre-workload idle value. AFTER final memory was 41.2 MiB (5.91%) above idle. Neither returned within 5% of its earlier idle level during the 30-second cooldown; both remained close to their two-concurrent peaks.
- AFTER remained stable after the concurrent workload, but at a higher plateau. No model/session recreation was evident from flat repeated-request peaks or logs; constructor counts were not instrumented inside these immutable images.

## Conclusion

This run does **not** prove a Docker RAM reduction. AFTER improved readiness and request latency substantially, including concurrent throughput, but used 5.3% more idle memory, 4.5–4.9% more workload-peak memory, and 10.2% more maximum observed startup-inclusive memory. The increased post-concurrency plateau is consistent with allowing two model jobs to execute concurrently rather than serializing all inference.

## Limitation

This is one controlled production-style local Docker comparison, not a large production load benchmark. It used one real-model-compatible image and one request sequence with Docker otherwise idle. A small identical in-container sampler was included in both memory totals. Docker CPU peak estimates at 20 ms exceeded the enforced two-CPU ceiling because of short-window counter quantization, so unreliable peak CPU values are intentionally not reported.
