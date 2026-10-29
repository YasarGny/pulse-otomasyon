const test = require('node:test');
const assert = require('node:assert/strict');
const {validate, activeIndex} = require('../site/assets/listening.js');
const asset = {sha256:'a'.repeat(64),duration:90};
const data = {schema_version:1,reviewed:true,audio_sha256:asset.sha256,
  chapters:[{start:0,title:'Açılış'},{start:12.4,title:'Çip üretimi'},{start:40,title:'Uzay'}]};
test('chapter boundaries follow actual seconds, including reverse seeking',()=>{
  assert.equal(validate(data,asset),data);
  for(const [time,index] of [[0,0],[12.3,0],[12.4,1],[41,2],[5,0]])
    assert.equal(activeIndex(data.chapters,time),index);
});
test('mismatched audio, bad times and unreviewed chapters are omitted',()=>{
  for(const invalid of [{...data,reviewed:false},{...data,audio_sha256:'b'.repeat(64)},
    {...data,chapters:[{start:90,title:'bad'}]}, {...data,chapters:[{start:NaN,title:'bad'}]},
    {...data,chapters:[{start:0,title:''}]}, {...data,chapters:[{start:5,title:'a'},{start:5,title:'b'}]}])
    assert.equal(validate(invalid,asset),null);
});
test('browser matches the server contract and preserves a four-second opening',()=>{
  const fixture = require('./chapter-contract.json');
  for (const item of fixture.cases) {
    const effective = {...fixture.asset,...item.asset};
    const value = {schema_version:1,reviewed:true,audio_sha256:effective.sha256,chapters:item.chapters};
    assert.equal(Boolean(validate(value,effective)),item.valid,item.name);
  }
  const chapters = [{start:0,title:'Açılış'},{start:4,title:'İlk konu'}];
  assert.equal(activeIndex(chapters,3.99),0);
  assert.equal(activeIndex(chapters,4),1);
  assert.equal(activeIndex(chapters,0),0);
});
