// check_export_browser_decisions.mjs - the assertions of check_export_browser.mjs for `portal.mode: decisions`.
//
// Imported by check_export_browser.mjs when the facts file says mode "decisions". It receives the page and the
// helpers of that script and runs its checks on state only: computed display, geometry, counts and hrefs.

export async function runDecisions({ page, check, go, display, shot, facts }) {
  const IDS = facts.page_ids;
  const ALL = ["front", ...IDS];
  const sel = (id) => `[id="${id}"]`;
  const shown = () =>
    page.evaluate(() => [...document.querySelectorAll(".page")].filter((e) => getComputedStyle(e).display !== "none").map((e) => e.id));
  const frame = () => page.evaluate(() => new Promise((r) => requestAnimationFrame(() => r())));
  const alone = async (id) => {
    const s = await shown();
    return s.length === 1 && s[0] === id;
  };

  // 1. load
  const loaded = await shown();
  check(loaded.length === 1 && loaded[0] === "front", "load: exactly one page is displayed, the front page", loaded.join(","));
  await shot("front.png");

  // 2. page count
  const ids = await page.evaluate(() => [...document.querySelectorAll("section.page")].map((e) => e.id));
  check(ids.length === 1 + IDS.length, `page count: ${1 + IDS.length} section.page elements`, String(ids.length));
  check(ids[0] === "front" && JSON.stringify(ids.slice(1)) === JSON.stringify(IDS), "page ids: the front page, then the declared ids in order",
    ids.slice(0, 8).join(","));

  // 3. navigation
  const notAlone = [];
  for (const id of IDS) {
    await go("#" + id);
    if (!(await alone(id)) || (await display("#front")) !== "none") notAlone.push(id);
  }
  check(notAlone.length === 0, `navigation: each of ${IDS.length} pages opens alone`, notAlone.slice(0, 5).join(","));

  // 4. front-page link
  const noLink = [];
  for (const id of IDS) {
    const has = await page.evaluate((i) => !!document.getElementById(i).querySelector('a[href="#front"]'), id);
    if (!has) noLink.push(id);
  }
  check(noLink.length === 0, "front link: every page holds a link to the front page", noLink.slice(0, 5).join(","));
  const clicked = [];
  for (const id of [IDS[0], IDS[IDS.length - 1]]) {
    await go("#" + id);
    await page.click(`${sel(id)} a[href="#front"]`);
    await frame();
    if (!(await alone("front"))) clicked.push(id);
  }
  check(clicked.length === 0, "front link: clicking it on the first and last page shows the front page alone", clicked.join(","));

  // 5. back
  await go("#front");
  await go("#" + IDS[0]);
  if (IDS.length > 1) await go("#" + IDS[1]);
  const trail = IDS.length > 1 ? [IDS[0], "front"] : ["front"];
  const backs = [];
  for (const want of trail) {
    await page.goBack();
    await frame();
    backs.push((await alone(want)) ? "ok" : `not ${want}`);
  }
  check(backs.every((b) => b === "ok"), `back: ${trail.length} steps back return through ${trail.join(", ")}`, backs.join(","));

  // 6. internal links
  const dangling = await page.evaluate(() =>
    [...document.querySelectorAll('a[href^="#"]')].map((a) => a.getAttribute("href")).filter((h) => !document.getElementById(h.slice(1))));
  check(dangling.length === 0, "internal links: every #href names an id that exists", `${dangling.length}: ${dangling.slice(0, 5).join(" ")}`);

  // 7. search
  await go("#front");
  await page.click("#q");
  await page.keyboard.type("qzxqzxqzx");
  let n = await page.evaluate(() => document.querySelectorAll("#results li").length);
  check(n === 0, "search: a nonsense term gives 0 results", String(n));
  await page.keyboard.press("Escape");
  check((await page.evaluate(() => document.getElementById("q").value)) === "", "search: Esc clears the box");
  await page.keyboard.type(facts.search.phrase);
  n = await page.evaluate(() => document.querySelectorAll("#results li").length);
  check(n >= 1, "search: the declared phrase gives results", String(n));
  const hit = await page.evaluate((id) => !!document.querySelector(`#results a[href="#${id}"]`), facts.search.finds);
  check(hit, "search: a result links the declared decision page");
  if (hit) {
    await page.click(`#results a[href="#${facts.search.finds}"]`);
    await frame();
    check(await alone(facts.search.finds), "search: the link opens that page alone");
  }
  await page.keyboard.press("Escape");

  // 8. width
  const fit = async (width, height) => {
    await page.setViewport({ width, height });
    const bad = [];
    for (const id of ALL) {
      await go("#" + id);
      const r = await page.evaluate(() => {
        const tables = [...document.querySelectorAll("table")].filter((t) => t.offsetParent !== null && t.parentElement);
        const over = tables.filter((t) => t.scrollWidth > t.parentElement.clientWidth + 1);
        const stuck = over.filter((t) => {
          const s = t.closest(".scroll");
          return !s || getComputedStyle(s).overflowX !== "auto";
        });
        return [document.documentElement.scrollWidth, document.documentElement.clientWidth, stuck.length];
      });
      if (r[0] > r[1] || r[2] > 0) bad.push(`${id} ${r.join("/")}`);
    }
    check(bad.length === 0, `width ${width}: ${ALL.length} pages do not scroll sideways and wide tables scroll inside .scroll`, bad.slice(0, 5).join(", "));
  };
  await fit(390, 800);
  await go("#front");
  await shot("phone-front.png");
  await fit(1280, 900);

  // 9. print
  await go("#front");
  await page.emulateMediaType("print");
  const printed = (await shown()).length;
  check(printed === 1 + IDS.length, `print: all ${1 + IDS.length} pages are displayed`, String(printed));
  check((await display(".bar")) === "none", "print: the bar is hidden");
  check((await display("#results")) === "none", "print: the search panel is hidden");
  const pdf = Buffer.from(await page.pdf({ format: "A4", printBackground: true, preferCSSPageSize: true }));
  const count = (pdf.toString("latin1").match(/\/Type\s*\/Page(?![A-Za-z])/g) || []).length;
  check(count >= facts.min_pages, `print: the PDF has at least ${facts.min_pages} pages`, String(count));
  const boxes = [...pdf.toString("latin1").matchAll(/\/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)/g)].map((m) => [Number(m[1]), Number(m[2])]);
  check(boxes.length >= facts.min_pages && boxes.every(([w, h]) => w > h), "print: the PDF's pages are landscape", `${boxes.length} boxes, first ${boxes[0]}`);
  await page.emulateMediaType("screen");

  // 10. screenshot of a decision page
  if (facts.decision_pages > 0) {
    await go("#" + IDS[0]);
    await shot(`decision-${IDS[0]}.png`);
  }
}
