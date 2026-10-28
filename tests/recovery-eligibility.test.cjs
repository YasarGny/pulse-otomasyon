const test = require('node:test');
const assert = require('node:assert/strict');
const {recoverableFailure} = require('../scripts/recovery-eligibility.cjs');
const audio = {name:'Research, edit, synthesize and validate both publications',conclusion:'success'};
const chapters = {name:'Required final-audio chapter analysis (never regenerates voices)',conclusion:'failure'};
test('only completed audio or failed publication can reserve the recovery queue', () => {
  assert.equal(recoverableFailure([{name:'generate',conclusion:'failure',steps:[audio,chapters]}]),true);
  assert.equal(recoverableFailure([{name:'publish',conclusion:'failure'}]),true);
  for (const jobs of [null, [], [{name:'gate',conclusion:'failure'}],
    [{name:'generate',conclusion:'failure',steps:[{...audio,conclusion:'failure'},chapters]}],
    [{name:'generate',conclusion:'cancelled',steps:[audio,chapters]}],
    [{name:'generate',conclusion:'failure',steps:[audio]}]]) {
    assert.equal(recoverableFailure(jobs),false);
  }
});
