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
test("production pause retains only the pinned verified release across later mornings",()=>{
  const control={enabled:true,automation_enabled:false,retained_release_id:m.release_id};
  for(const at of ['2026-10-17T06:00:00+03:00','2026-10-20T12:00:00+03:00'])
    assert.equal(r.isReady(m,new Date(at),control),true);
  const later=new Date('2026-10-20T12:00:00+03:00');
  for(const control of [{enabled:true,automation_enabled:true,retained_release_id:m.release_id},
    {enabled:true,automation_enabled:false},
    {enabled:true,automation_enabled:false,retained_release_id:'another-release'}])
    assert.equal(r.isReady(m,later,control),false);
  for(const bad of [{...m,status:'preparing'},{...m,validation:'unverified'},{...m,editions:{teknoloji:m.editions.teknoloji}}])
    assert.equal(r.isReady(bad,later,control),false);
  assert.equal(r.isReady(m,new Date('2026-10-16T07:29:59+03:00'),control),false);
  assert.equal(r.isReady(m,new Date('2026-10-16T12:00:00+03:00'),
    {...control,retained_release_id:'another-release'}),false);
});
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
    assert(!r.editionValid({...d,stories:d.stories.slice(0,section === "teknoloji" ? 11 : 9)},section,m));
  }
});

test("shared policy accepts quiet days equally but rejects empty news and invalid ranking", () => {
  const future = {...m, publish_date:"2026-10-22",
    editions:Object.fromEntries(r.sections.map(s=>[s,{...m.editions[s],issue:7}]))};
  for (const section of r.sections) {
    const d={section,publish_date:future.publish_date,ready:true,issue:7,publication_profile:"daily-v2",
      stories:[{id:"one",title:"Başlık",summary:"Özet",why:"Önemi",category:"Gündem",source_name:"Kaynak",source_url:"https://example.com/news",
        editorial_priority:{impact:3,development:3,timeliness:3,evidence:3,reason:"Kaynağa dayanan somut gelişme açıklaması."}}],
      summary:{file:section+"/summary.mp3",duration:30,bytes:25000,sha256:"a".repeat(64),episode:7},
      podcast:{file:section+"/podcast.mp3",duration:600,bytes:25000,sha256:"b".repeat(64),episode:7}};
    assert(r.editionValid(d,section,future));
    assert(r.editionValid({...d,summary:{...d.summary,duration:15}},section,future));
    assert(!r.editionValid({...d,summary:{...d.summary,duration:1}},section,future));
    assert(!r.editionValid({...d,stories:[]},section,future));
    assert(!r.editionValid({...d,stories:[{...d.stories[0],editorial_priority:null}]},section,future));
    assert(!r.editionValid({...d,podcast:{...d.podcast,duration:1}},section,future));
    assert(r.editionValid({...d,podcast_enabled:false,podcast:null},section,future));
    assert(!r.editionValid({...d,podcast:null},section,future));
    assert(!r.editionValid({...d,podcast_enabled:false},section,future));
    assert(!r.editionValid({...d,podcast_enabled:'false',podcast:null},section,future));
  }
});
