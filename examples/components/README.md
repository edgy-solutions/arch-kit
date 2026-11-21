# Components example (Sorrel)

A standalone project with `files.components` and a `components:` map. Every name in it is invented. The export
snapshot is added when render_html wires the Components page in; until then `expected/components.html` is the
output of `components.render` and `components.nav`, checked by `test_example_components.py`.
Three components carry `connections`: one link with a written protection, one with a known gap (reported on stderr
and shown with a gap badge) and one with no `protected_by`, which renders "not written".
