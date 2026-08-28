# Reviewed visual proofs

These images record visual decisions that remain relevant to the current font
release. They complement automated checks; they do not replace them.

- [`sans-variable-named-instances.png`](sans-variable-named-instances.png)
  compares the rounded Sans variable font with the approved static instances.
  Regenerate it with `venv/bin/python scripts/proof_sans_variable.py` after a
  reviewed Sans variable-font change.
- [`sans-italic-variable-named-instances.png`](sans-italic-variable-named-instances.png)
  is the italic counterpart. Regenerate it with
  `venv/bin/python scripts/proof_sans_variable.py --italic`, which selects the
  italic VF and this output path on its own.
- [`issues/`](issues/README.md) contains the proof panels used to resolve or
  maintain specific Fontspector issues.

Do not replace a reviewed proof merely to make a changed build look current.
First run the relevant check, inspect the change, and record the design or QA
decision in an issue or pull request.
