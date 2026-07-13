# Biometric data governance

Before collecting deployment data, obtain written purpose, lawful basis, informed consent where required, retention period, access roles, deletion process, incident response, and risk-owner approval. Use pseudonymous subject IDs; keep the re-identification mapping in a separate controlled system.

Never place employee names, raw captures, completed manifests, embeddings, provider assertions, or encryption keys in Git, tickets, chat, logs, or general file shares. Encrypt controlled datasets at rest and in transit, restrict access, record access, and delete them at the approved date. Reports should contain aggregate counts/slices only and must suppress very small slices that could re-identify people.

The API stores Fernet-encrypted templates plus model/calibration/key version and optional consent reference. Face revoke stops use; face delete overwrites the encrypted template before marking it deleted; re-enrollment requires a new secure capture. Operational policy must define who may invoke these actions, how key rotation is performed, and how backups honor deletion/retention.

Fairness/demographic analysis is permitted only with legally approved, consented data and sufficient sample sizes. Liveness spoof datasets require separate licensing and safe handling. Model accuracy, fairness, and spoof resistance must be reassessed after material model, preprocessing, camera, population, or environment changes.

Before selecting a liveness provider, document whether it stores raw frames/video, derived PAD signals, device metadata, or result assertions; processing regions/subprocessors; cross-border transfers; retention/deletion APIs; backup deletion; and incident obligations. Face-template deletion does not automatically delete provider-side capture data, so ESS must orchestrate both lifecycle processes where applicable.
