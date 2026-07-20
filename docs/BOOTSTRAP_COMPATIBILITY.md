# Bootstrap Compatibility Boundaries

Project Foundry was introduced by pull request #1 before a validator existed on the trusted `main` branch. Pull request #2 then repaired the bootstrap validator itself while the Foundation Task still intentionally remained at `implementation_submitted`.

The validator recognizes exactly two immutable historical boundaries. Neither is a reusable lifecycle rule.

## Repository genesis — pull request #1

- base: `d197447598d7108c44e79fbaa57d71e529930052`
- first canonical Task snapshot: `fd039af9f1771922c185d3595afd975ad93dfd04`
- pull-request Head: `75282b08d27015543e7467dabb34395803ed1ed5`
- merge commit: `c44ced1d858bd0d1b6d690e47ae12355c79166ca`
- pull request: `#1`
- Task: `PF-001`
- initial status: `implementation_submitted`

## Validator-bootstrap repair — pull request #2

- base: `c44ced1d858bd0d1b6d690e47ae12355c79166ca`
- pull-request Head: `0d997d0429c2e3099e9ec5a09c83eea69f14a6ab`
- merge commit: `cac31e13815a7c52d436fcf34f65dbe997980a37`
- pull request: `#2`
- canonical Task: `PF-001`
- preserved status: `implementation_submitted`

Each exception is accepted only when its exact Git topology, canonical-file preservation, hosted merge record and successful exact-Head pull-request CI evidence match. The second boundary suppresses only the two known integration false positives caused by merging the validator repair before trusted lifecycle reconciliation.

These exceptions do not authorize another Task, commit, pull request, repository, status or merge. All Tasks introduced after repository genesis must first appear as `planned` with empty evidence. A violation is reported as `PFV-037`.
