# Bootstrap Compatibility Boundary

Project-Foundry was introduced by pull request #1 before a validator existed on the trusted `main` branch. The first merge therefore cannot satisfy lifecycle rules that were created inside that same pull request.

The validator recognizes exactly one historical bootstrap boundary:

- base: `d197447598d7108c44e79fbaa57d71e529930052`
- first canonical Task snapshot: `fd039af9f1771922c185d3595afd975ad93dfd04`
- pull-request Head: `75282b08d27015543e7467dabb34395803ed1ed5`
- merge commit: `c44ced1d858bd0d1b6d690e47ae12355c79166ca`
- pull request: `#1`
- Task: `PF-001`
- initial status: `implementation_submitted`

The exception is accepted only when the exact Git topology, canonical files, hosted merge record, and successful pull-request CI evidence all match those identities. It does not authorize another Task, commit, pull request, repository, status, or merge.

All Tasks introduced after this bootstrap must first appear as `planned` with empty evidence. A violation is reported as `PFV-037`.
