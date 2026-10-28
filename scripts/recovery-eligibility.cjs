// Decide from trusted Actions execution metadata before joining the publish lock.
function recoverableFailure(jobs) {
  if (!Array.isArray(jobs)) return false;
  return jobs.some(job => job.conclusion === 'failure' && (
    job.name === 'publish' || (job.name === 'generate' &&
      Array.isArray(job.steps) &&
      job.steps.some(step => step.name === 'Research, edit, synthesize and validate both publications' && step.conclusion === 'success') &&
      job.steps.some(step => step.name === 'Required final-audio chapter analysis (never regenerates voices)' && step.conclusion === 'failure'))));
}
module.exports = { recoverableFailure };
