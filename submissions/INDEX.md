# Submissions

One directory per entered result, as `CONTRIBUTING.md` describes. Each holds the
manifest the runs used, the unedited run logs, a `RUN.md` naming the machine and
the commands, and any certificates.

| submission | tracks | corpus | budgets | reproduced from a rebuild | merged |
|---|---|---|---|---|---|
| none yet | | | | | |

The reference engines are not submissions: they are measured here and their
numbers live in `results/reference/REFERENCE.md`, with the studies in `studies/`
and the held-out rounds in `rounds/`. Their manifests are in `manifests/`, and
`engines/` rebuilds them from public sources.

**"Reproduced from a rebuild"** means the maintainer rebuilt the engine from the
manifest's `build` recipe, checked its `bench` node count, re-ran the node-budget
comparison, and got the same claims, verifications and discordant pairs. Clock
results are not re-run for equality: they belong to the machine that produced
them, which `RUN.md` records.
