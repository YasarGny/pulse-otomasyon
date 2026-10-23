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
    {...data,chapters:[{start:0,title:''}]}, {...data,chapters:[{start:5,title:'a'},{start:6,title:'b'}]}])
    assert.equal(validate(invalid,asset),null);
});
