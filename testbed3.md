Call a positive integer \(m\) **universal** if for every integer \(n\),
\[
n^2 \equiv 1 \pmod{m} \iff \gcd(n, m) = 1 .
\]

This problem has three dependent phases. Each phase must produce its own
evidence before the next one starts.

1. **Survey.** Determine computationally which \(m\) in the range \(1 \le m \le
   200\) are universal. The search program and its output are part of the
   deliverable and must be reproducible.

2. **Characterization.** State and prove the exact characterization of the
   universal \(m\) that phase 1 suggests. The proof must be complete in both
   directions, and it must stand on its own — a finite search is not a proof of
   a statement about all \(m\).

3. **Formalization.** Produce a Lean 4 source that compiles against Mathlib
   with no `sorry`, no `axiom`, and no unproved hypothesis, containing both:
   - a theorem that 24 is universal, and
   - a theorem that 48 is not universal.

Report the largest universal \(m\) and why no larger one exists.
