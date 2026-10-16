const { test } = require("node:test");
const assert = require("node:assert/strict");
const r = require("../site/assets/publication.js");
const m = {
  schema_version: 1,
  status: "ready",
  publish_date: "2026-10-16",
  release_id: "2026-10-16-0123456789abcdef",
  not_before: "2026-10-16T07:30:00+03:00",
  game_start: "2026-10-16",
  validation: "full-mp3-decode+sha256+content-v1",
  editions: Object.fromEntries(
    r.sections.map((s) => [
      s,
      { file: s + ".json", sha256: "a".repeat(64), issue: 1 },
    ]),
  ),
};
test("07:29:59 remains closed even with a ready manifest", () =>
  assert.equal(r.isReady(m, new Date("2026-10-16T07:29:59+03:00")), false));
test("07:30 opens only a complete manifest", () =>
  assert.equal(r.isReady(m, new Date("2026-10-16T07:30:00+03:00")), true));
test("07:30 alone does not open a preparing issue", () =>
  assert.equal(
    r.isReady(
      { ...m, status: "preparing" },
      new Date("2026-10-16T07:30:00+03:00"),
    ),
    false,
  ));
test("missing game prevents publication", () =>
  assert.equal(
    r.isReady(
      { ...m, editions: { teknoloji: m.editions.teknoloji } },
      new Date("2026-10-16T08:00:00+03:00"),
    ),
    false,
  ));
test("next day 05:59:59 remains readable", () =>
  assert.equal(r.isReady(m, new Date("2026-10-17T05:59:59+03:00")), true));
test("next day 06:00 closes yesterday", () =>
  assert.equal(r.isReady(m, new Date("2026-10-17T06:00:00+03:00")), false));
test("next day 07:30 cannot resurrect yesterday", () =>
  assert.equal(r.isReady(m, new Date("2026-10-17T07:30:00+03:00")), false));
test("Istanbul date at UTC boundary", () =>
  assert.equal(r.expectedDate(new Date("2026-10-17T02:59:59Z")), "2026-10-16"));
test("server Date and Age are authoritative", () =>
  assert.equal(
    r
      .httpTime(
        new Headers({ date: "Fri, 16 Oct 2026 04:30:00 GMT", age: "10" }),
      )
      .toISOString(),
    "2026-10-16T04:30:10.000Z",
  ));
test("missing server time fails closed", () =>
  assert.throws(() => r.httpTime(new Headers())));
test("bad cache age fails closed", () =>
  assert.throws(() =>
    r.httpTime(
      new Headers({ date: "Fri, 16 Oct 2026 04:30:00 GMT", age: "bad" }),
    ),
  ));
test("unsafe relative assets fail", () =>
  ["../x", "/x", "https://example.com", "a/../b", "a\\b"].forEach((p) =>
    assert.equal(r.safeRelative(p), false),
  ));
test("unsafe source schemes fail", () =>
  [
    "javascript:alert(1)",
    "data:text/html,x",
    "http://example.com",
    "https://user:pass@example.com",
  ].forEach((p) => assert.equal(r.safeHttps(p), false)));
test("arbitrary ready flags fail attestation", () =>
  assert.equal(
    r.isReady(
      { ...m, validation: null },
      new Date("2026-10-16T08:00:00+03:00"),
    ),
    false,
  ));

test("expanded issues accept broad selections and require a real long podcast", () => {
  for (const [section, count, duration] of [["teknoloji", 20, 900], ["oyun", 18, 720]]) {
    const d = {
      section, publish_date: m.publish_date, ready: true, issue: 1,
      publication_profile: "expanded-v1",
      stories: Array.from({length: count}, (_,i) => ({id: String(i), title:"Başlık", summary:"Özet", why:"Önemi", category:"Gündem", source_name:"Kaynak", source_url:"https://example.com/"+i})),
      summary: {file: section+"/summary.mp3", duration:30, bytes:25000,sha256:"a".repeat(64),episode:1},
      podcast: {file: section+"/podcast.mp3",duration,bytes:25000,sha256:"b".repeat(64),episode:1}
    };
    assert(r.editionValid(d,section,m));
    assert(!r.editionValid({...d,podcast:{...d.podcast,duration:120}},section,m));
    assert(!r.editionValid({...d,stories:d.stories.slice(0,3)},section,m));
  }
});
