# GMD publication durability and incident handling

This addendum supplements `prompts/automation-transaction.md`; it does not replace any publication, safety, schema, research, or Quality requirement. It neither changes the 09:00 / 10:30 schedules nor adds a publisher.

## Preserve work before any GitHub publication write

After constructing the canonical five-file bundle, save the actual bytes in the permitted working environment. Run:

```
python scripts/publication_checkpoint.py pack --root CANDIDATE_ROOT --date YYYY-MM-DD --base-main-sha VERIFIED_MAIN_SHA --out /mnt/data/gmd-checkpoints
```

The SHA must come from the current GitHub read, not memory. The command only packages the five allowed publication files and a hash manifest. It has no network, credential, branch, commit, PR, or publishing capability. Its basic structural diagnostics are NOT a full Quality-parity pass. Run all existing Quality commands separately.

Save the completed checkpoint to the user's permitted private Library using the available Files interface, or attach the completed file through an available supported attachment mechanism. Verify the returned destination and success status. `/mnt/data` alone is temporary storage. Do not claim persistent recovery is available until saving is confirmed. Do not put account diagnostics in this public repository. Preserve partial work with an explicit partial/invalid label; a saved invalid bundle is not eligible for submission.

Before rebuilding a missing remote candidate, inspect the permitted Library for a matching checkpoint, verify its exact hashes, and recheck current main, factual cutoff, permission/safety status, and complete Quality parity. Do not change a real research timestamp merely to resubmit. A checkpoint that received an explicit safety denial must not be automatically resubmitted or rerouted; retain it for supported review and diagnostics.

## Distinguish failures and preserve evidence

An explicit safety block is not a network timeout or a GitHub Quality failure. On denial, stop external publishing writes; do not change accounts, transports, encoding, content, or use cloud/browser execution to defeat the denial. Read back the intended branch/PR/main to determine whether anything changed. Preserve the original error privately, with UTC and SGT times, action, attempted target, bundle hash, provider head, and any real request/diagnostic ID. Use `not shown` when an ID is absent. Never invent a support ticket or internal root cause.

Authorization errors require provider/account review. Only confirmed transient connection errors may receive the existing single ordinary retry after provider readback; never treat an ambiguous error as transient. `publication_checkpoint.py classify` is a local diagnostic helper, not an automatic retry runner.

A blocked or unknown result cannot become `SUBMITTED_FOR_VALIDATION`. That status still requires reading back the exact PR title/base/head/SHA. A saved ZIP, a green older health check, or HTTP 200 is not publication evidence. Keep valid current main unchanged; do not disable or reschedule either existing task.

## Fault-injection acceptance

`python scripts/test_publication_checkpoint.py` tests exact bytes, original cutoff preservation, idempotency, partial recovery, corrupt JSON/ZIP handling, path allowlisting, and terminal safety-block classification. Successful local tests establish these properties only, not removal of a platform safety block or success of a future unattended run.
