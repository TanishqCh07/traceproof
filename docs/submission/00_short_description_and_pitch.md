# Short description (lablab "Short Description" field)

TraceProof proves your code matches its spec. IBM Bob audits the repo against the requirements document, catches what green CI misses, fixes the gaps test-first, and blocks regressions in CI.

# Project title

TraceProof: Proof, not trust

# One-sentence problem statement

Proving that code does what its specification says is manual, slow and unreliable, and passing tests are mistaken for proof.

# 30-second spoken pitch (for the video intro or if a judge asks)

"In banking, payments or medical software, every release has to prove that each rule in the spec is implemented and tested. Today that proof is a spreadsheet someone fills in by hand, and teams assume green tests mean compliant. They don't. Our demo app passes all 11 tests, yet it logs full card numbers and allows twice the legal transaction limit. TraceProof uses IBM Bob to check the code against the spec line by line, record evidence that can't be faked, fix every gap test-first, and block any pull request that breaks a rule again."

# Plain-English glossary (use these words in the video)

- **Specification (spec):** the approved document listing numbered rules the software must follow (e.g. PF-005: refunds only within 30 days).
- **RTM (Requirements Traceability Matrix):** a table proving each rule → the code that implements it → the test that proves it.
- **Drift:** the code does something close to the rule, but not the rule (60 days instead of 30).
- **Violation:** the code does something the rule forbids (logging card numbers).
- **Coverage:** the percentage of rules that are both implemented correctly and proven by a passing test.
