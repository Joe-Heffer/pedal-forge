## Summary

<!-- What changes, and why. Link the issue or design note it follows. -->

## Notes and values

* [ ] `docs/design-notes.md` is updated before any code that depends on the change
* [ ] Each new constant, threshold or default says whether it is documented, reported, inferred or chosen, with a link for anything sourced
* [ ] Any change to an evaluation item's expected answer has a reason in its `reasoning` field

## Checks

* [ ] `make check` passes (every pre-commit hook, as CI runs it)
* [ ] `make test` passes
* [ ] `make eval` runs, and any new numbers are described as reported or measured
* [ ] No generated files are committed (`build/` and `out/` stay out of git)
* [ ] Prose is British English, and no manufacturer or product names appear outside `docs/`

## Listening

<!-- For anything that changes sound, list what a person should check by ear
and on their own hardware, and name the value to adjust. Delete this section
if the change does not affect sound. -->
