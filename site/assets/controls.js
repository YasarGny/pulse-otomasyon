/* Owner pause controls; portable daily archives are independent of live controls. */
(() => {
  'use strict';
  if (window.PULSE_ARCHIVE || location.protocol === 'file:') return;
  const base = new URL('../', document.currentScript.src);
  const api = window.PulseControls = {
    state: {schema_version: 1, enabled: true, automation_enabled: true, podcasts: {teknoloji: true, oyun: true}},
    ready: null, refreshView,
  };
  let busy = false;
  function refreshView() {
    const held = api.state.automation_enabled === false;
    const stamp = document.querySelector('.nav-issue');
    if (stamp && held && window.PULSE_RELEASE) {
      if (!('originalIssue' in stamp.dataset)) stamp.dataset.originalIssue = stamp.textContent;
      stamp.textContent = 'Son yayın · ' + window.PULSE_RELEASE.manifest.publish_date.split('-').reverse().join('.');
    } else if (stamp && 'originalIssue' in stamp.dataset) {
      stamp.textContent = stamp.dataset.originalIssue;
      delete stamp.dataset.originalIssue;
    }
    for (const heading of document.querySelectorAll('#listening-title')) {
      if (held && /^Bugünün podcast/.test(heading.textContent)) {
        heading.dataset.originalHeading = heading.textContent;
        heading.textContent = 'Podcast’ler';
      } else if (!held && heading.dataset.originalHeading) {
        heading.textContent = heading.dataset.originalHeading;
        delete heading.dataset.originalHeading;
      }
    }
    for (const [section, enabled] of Object.entries(api.state.podcasts)) {
      for (const node of document.querySelectorAll(`[data-audio-section="${section}"][data-audio-kind="podcast"],.program-card[aria-labelledby="program-${section}"],.story-clip-slot[data-section="${section}"]`)) {
        node.hidden = !enabled;
      }
    }
  }
  async function update() {
    if (busy) return;
    busy = true;
    try {
      const response = await fetch(new URL('data/controls.json?check=' + Date.now(), base), {cache: 'no-store', signal: AbortSignal.timeout(10000)});
      if (response.status === 404) return; // Backwards-compatible pre-control builds.
      if (!response.ok) return;
      const next = await response.json();
      if (next.schema_version !== 1 || typeof next.enabled !== 'boolean' ||
          (next.automation_enabled !== undefined && typeof next.automation_enabled !== 'boolean') ||
          !['teknoloji', 'oyun'].every(s => typeof next.podcasts?.[s] === 'boolean')) return;
      const changed = JSON.stringify(next) !== JSON.stringify(api.state);
      api.state = next;
      refreshView();
      if (changed) window.dispatchEvent(new Event('pulse:controls'));
      if (!next.enabled && document.body.dataset.pulsePaused !== 'true') {
        window.dispatchEvent(new Event('pulse:locked'));
        document.querySelectorAll('audio').forEach(a => a.pause());
        // Drop the live page and its navigation/audio session, retaining no stale UI.
        document.body.replaceChildren();
        document.body.className = 'pulse-owner-pause';
        document.documentElement.classList.remove('pulse-loading', 'pulse-locked');
        document.body.dataset.pulsePaused = 'true';
        const main = document.createElement('main');
        main.className = 'owner-pause-card';
        main.innerHTML = '<div class="brand">PULSE<span class="brand-dot">.</span></div><h1>Yayınlara kısa bir ara verdik.</h1><p>Yeniden buluşmak üzere.</p>';
        document.body.append(main);
      } else if (next.enabled && document.body.dataset.pulsePaused === 'true') {
        const page = await fetch(location.href, {cache:'no-store', signal:AbortSignal.timeout(10000)});
        if (page.ok && !(await page.text()).includes('data-pulse-paused="true"')) location.reload();
      }
    } catch (_) {
      // A network outage must not undo a previously observed owner pause.
    } finally { busy = false; }
  }
  api.ready = update();
  setInterval(update, 30000);
  window.addEventListener('pageshow', update);
  window.addEventListener('online', update);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) update(); });
})();
