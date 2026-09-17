Thanks for entering a result. `CONTRIBUTING.md` has the whole process; this is
its checklist. Delete what does not apply (a fix to the harness needs only the
last two lines).

**The submission**

- [ ] One new directory, `submissions/<engine>-<version>/`, and nothing else
      changed outside it.
- [ ] `manifest.json` as the runs used it, with `sha256`, every mate-search
      option set explicitly, and `tuned_on` naming every corpus the engine was
      developed on.
- [ ] `bench` and `build` in the manifest, so the engine can be rebuilt and the
      rebuild accepted. If it cannot be rebuilt, say so here.
- [ ] Every run log, unedited, from `bench/submit.py`.
- [ ] `RUN.md`: machine, cores, OS, searches at once, MateProver version, and the
      exact commands.
- [ ] Certificates, if the engine supplies them.

**The runs**

- [ ] Against the reference manifests in `manifests/`, at their own settings.
- [ ] On a corpus with a checksum in `corpora/CHECKSUMS.json`.
- [ ] A node budget within one family, or `--movetime` across families, on an
      idle machine.
- [ ] No claim refuted. If one was, leave it in the log and say so here.

**Anything else**

- [ ] `python bench/test_submit.py`, `test_certify.py` and `test_hook.py` pass if
      you changed the harness.
- [ ] `python bench/lint_measurement.py <script>` passes for any measurement
      script you changed.
