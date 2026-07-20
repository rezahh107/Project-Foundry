# Trusted Provenance

Project Foundry separates ordinary repository validation from hosted-evidence authority.

## Authoritative producer

The authoritative hosted-evidence verifier is the external composite action:

```text
repository: rezahh107/Post-Merge-Auditor
path: attestors/project_foundry_v1
commit: c17da77665a7ab4416e5084f93cc03c1d3532cba
```

The action is loaded by exact commit SHA. It is outside the evaluated Project Foundry pull request and does not checkout or execute target-repository code.

## Canonical CI identity

The active policy accepts only:

```text
repository: rezahh107/Project-Foundry
workflow_id: 315675709
workflow_path: .github/workflows/foundation-validation.yml
workflow_sha256: a6973556b2f03a75fea2feecd11cc322a466c9840a7db3aea5704261971a39e1
```

A matching display name is not authority. The attestor resolves the exact workflow ID and path, fetches the workflow bytes at the evaluated Head SHA, and rejects any byte change not activated through a later attestor policy.

For pull-request runs it also binds the exact run attempt, repository, PR number, Head SHA, Head ref and base ref. For pushes it requires the exact successful `main` run. A two-parent push must correspond to exactly one hosted merged pull request whose base SHA is parent 1 and whose PR Head is parent 2.

## Execution boundary

`.github/workflows/trusted-provenance.yml` is loaded from the default branch through `workflow_run`. The evaluated PR cannot replace the workflow used to judge its own Foundation run. The trusted workflow has read-only permissions and does not checkout the target repository.

`scripts/collect_hosted_provenance.py` remains a compatibility input for internal historical validation. Its runner-temporary JSON is not the external trust root and must not be used as the sole basis for Merge or completion approval.

## Activation and upgrades

Trust-policy updates are deliberately delayed:

1. change and validate the attestor in `Post-Merge-Auditor`;
2. merge that change and obtain an immutable commit SHA;
3. update the exact pin in the deterministic trusted workflow;
4. validate and merge the pin update;
5. only subsequent runs use the new policy.

No branch, tag or mutable action reference is an approved producer identity.

## Required checks

Owner policy must treat both checks as required before Merge:

- `Validate exact triggering head`
- `Verify immutable hosted provenance`

Repository settings are a protected owner action. The checked-in contracts can detect drift and duplicate workflow identities, but they cannot by themselves configure GitHub branch protection.
