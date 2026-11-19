# Prose pages example (Woad)

A standalone project with `files.pages`. Every name in it is invented. It declares components, a roadmap, flows and one
alignment record, and its three pages cite them. `pages/a-offline.md` sorts before `pages/b-return.md` by name but
carries `order: 2`, and the other `order: 1`, so the walkthroughs render in `order`, not file, order. The export snapshot is added when
render_html wires the pages in; until then `expected/pages.html` is the output of `pages.render` and `pages.nav`,
checked by `test_example_pages.py`. `registers.roadmap` names a note that does not exist, which is allowed.
