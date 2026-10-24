# Contract-change proposal: `get_commitment_summary` response shape

Status: PROPOSED by Agent 04 for integrator approval (not applied to `CONTRACTS.md`; that file is not A4's).
Affects: A5 (producer), A4 (consumer, already enforcing this), A6 (indirectly, via `proposal_confirmed`).

## Why
`CONTRACTS.md` names `get_commitment_summary(session_id, plan_id, version)` but not its payload. A4 must decide
"confirmed" from it without trusting ambiguous data, so both sides need one frozen shape.

## Request
`get_commitment_summary(session_id: str, plan_id: str, version: int) -> Mapping`

## Response (all fields JSON scalars; no member identities, reasons or constraint values)

| Field | Type | Required | Meaning |
|---|---|---|---|
| `session_id` | string | yes | echo of the request |
| `plan_id` | string | yes | echo; A4 treats a mismatch as `PROPOSAL_STALE` |
| `version` | integer | yes | echo; A4 treats a mismatch as `PROPOSAL_STALE` |
| `required_count` | integer >= 1 | yes | members who must accept; A4 requires it to equal the current roster size |
| `accepted_count` | integer >= 0 (not boolean) | yes | members whose latest valid state for THIS version is `accepted` |
| `declined_count` | integer >= 0 | optional (default 0) | any value > 0 blocks confirmation |
| `withdrawn_count` | integer >= 0 | optional (default 0) | any value > 0 blocks confirmation |
| `confirmed` | boolean | optional | if present it must be `true`; `false` blocks confirmation |

`tentative`, `conditional`, `interested` and `pending` members are simply not counted in `accepted_count`.

## A4's decision rule (implemented in `NegotiationCoordinator.confirm_if_approved`)

| Condition | Result |
|---|---|
| `plan_id`/`version` differ from the published proposal | `stale` / `PROPOSAL_STALE` |
| `required_count != roster size` or `accepted_count != required_count` | `incomplete` / `APPROVAL_INCOMPLETE` |
| `declined_count > 0`, `withdrawn_count > 0`, or `confirmed == false` | `incomplete` / `APPROVAL_INCOMPLETE` |
| gateway raises | `incomplete` / `PROVIDER_UNAVAILABLE` |
| otherwise | `confirmed`; A4 emits `proposal_confirmed` then `session_completed` |

## Related obligations (also proposed)
1. `CommitmentGateway.invalidate_version(session_id, old_version, new_floor)`: after this call every approval for a version
   `< new_floor` must report `accepted_count == 0`. The published winner may be numbered above `new_floor`.
2. A5 must treat an approval as valid only if its version equals `get_public_snapshot(session_id)["version"]`.
3. A5 records approvals; A4 never writes them.
4. New optional `AgentEvent` payload fields and `reason_category` values used by A4 are listed in `README.md`
   ("Assumptions / contract-change requests").

## Conformance
`tests/negotiation/test_neg_commitment_contract.py` encodes the table above against `MockCommitmentGateway`.
A5 can import `check_commitment_summary` from that file (or copy the table) to test its real gateway.
