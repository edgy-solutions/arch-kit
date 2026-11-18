# Changelog

## 0.1.0

The first release. Each step of Phase 1 in a sentence:

- **Step 1:** the tools moved out of the first project unchanged, and read the content paths from the project's declaration.
- **Step 2:** no project names in the kit; names, keys and file names are declared, and a test fails on a name that leaks back in.
- **Step 3:** a loader seam, so each project reads its own files into a neutral record the kit checks against a JSON Schema; labels, phases, statuses and view kinds are declared.
- **Step 4:** relabelling and the leak scan run on the rendered HTML, and a leak writes no file.
- **Step 5:** each portal declares its hosting and its audience, and a public audience requires the relabel and barred lists.
- **Step 6a:** the decision-index check moved into the kit, with its names declared in `decisions.index`.
- **Step 6b:** the `arch-kit` command, a declared term dictionary, an optional declared data exchange, and the minimal example project with its self-test.
- **Step 6c:** a composite GitHub Action that runs the whole chain, uploads the export when the portal declares `ci-artifact`, and a `portal` subcommand that prints the declaration.
- **Step 6d:** `check_views --record FILE` checks a project's own capability record in place of the default, and the phases view names that record in plain words when the render uses one.
