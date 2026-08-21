<!-- Thanks for contributing to ADHED. Fill in what's relevant. -->

## Summary

<!-- One or two sentences on what this PR does and why. -->

## Changes

<!-- Bulleted list of user-visible changes. Link to issues if any. -->

-

## The five questions

<!-- From the ai-dev-framework. Answer honestly; any "no" without an
     explanation is grounds to stop, however good the work looks.
     Not every question applies to every PR — say so when one
     doesn't, don't just tick the box. -->

- [ ] **Was the threshold written down before the result was known?**
      The pass criteria predate the run that produced the numbers.
- [ ] **Did the test fail first?** The branch history shows the new
      test red on the unfixed code — a test that has only ever been
      green may be testing nothing.
- [ ] **Can the reviewer run it themselves?** Every claimed finding
      ships with one command that reproduces it.
- [ ] **Who checked this, and were they independent?** Review came
      from someone (or something) other than the author, judged the
      evidence without the author's conclusion attached — and you
      read the reviewer's output, not its exit code.
- [ ] **Could this have come out the other way?** Some reachable
      result would have falsified the claim. A gate that cannot fail
      is decoration.

## Test plan

<!-- How you verified this works. -->

- [ ] `pytest tests/` passes
- [ ] `ruff check src/ tests/` passes
- [ ] `ruff format --check src/ tests/` passes
- [ ] New behaviour has tests
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`
- [ ] Documentation updated if the API changed

## Out of scope

<!-- Anything this PR deliberately does NOT do. Helps reviewers
     avoid asking "what about X?" -->
