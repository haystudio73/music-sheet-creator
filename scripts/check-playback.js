// Playwright run-code function. ONLY run against the isolated ui_fixture project.
// UI language must be English; dismiss the guide and open Playback regression first.
async page => {
  const assert = (ok, message) => { if (!ok) throw new Error(message); };
  assert(await page.getByRole('heading', { name: 'Playback regression', exact: true }).count() === 1, 'Open the isolated Playback regression fixture');
  const role = (kind, name) => page.getByRole(kind, { name, exact: true });
  const active = page.locator('.playback-active-note');
  const ready = () => page.locator('.notation-container:not(.is-loading) [data-playback-start]').first().waitFor({ state: 'attached' });
  const stop = async () => {
    await role('button', 'Stop score preview').click();
    await active.waitFor({ state: 'detached' });
    assert(Number(await role('slider', 'Score playback position').getAttribute('value')) === 0, 'Stop must reset position');
  };
  await role('tab', 'Score').click();
  await ready();
  await role('checkbox', 'Follow active notes').uncheck();
  await role('slider', 'Score preview volume').press('End');
  assert(await role('slider', 'Score preview volume').getAttribute('value') === '100', 'Visible volume remains capped at 100%');
  await page.evaluate(() => {
    const prototype = AudioContext.prototype;
    const createGain = prototype.createGain;
    window.__scoreGainNodes = [];
    prototype.createGain = function () {
      const node = createGain.call(this);
      window.__scoreGainNodes.push(node);
      return node;
    };
  });
  await role('checkbox', 'Metronome').check();
  await role('slider', 'Metronome volume').press('Home');
  assert(await role('slider', 'Metronome volume').getAttribute('value') === '0', 'Independent metronome mute');
  for (let replay = 0; replay < 2; replay++) {
    await role('button', 'Play score preview').click();
    await page.locator('.playback-active-note[data-playback-start="0"]').waitFor({ state: 'attached' });
    if (replay === 0) {
      const gain = await page.evaluate(() => window.__scoreGainNodes[0]?.gain.value);
      assert(Math.abs(gain - 0.8) < 0.001, '100% instrument volume must produce gain 0.8');
    }
    await stop();
  }
  // Native keyboard range input: 7% of the 64-second fixture = 4.48s,
  // inside the second written segment of the tied D4 (4..6 quarter beats).
  const seek = role('slider', 'Score playback position');
  await seek.press('Home');
  for (let i = 0; i < 7; i++) await seek.press('ArrowRight');
  await role('button', 'Play score preview').click();
  await page.locator('.playback-active-note[data-playback-start="4"][data-playback-end="6"]').waitFor({ state: 'attached' });
  await stop();
  await role('tab', 'Melody').click();
  await role('spinbutton', 'Pitch of note 1').fill('67');
  await role('tab', 'Score').click();
  await ready();
  assert(await role('button', 'Save').isEnabled(), 'Fixture must have unsaved changes');
  assert(!await role('button', 'MusicXML Continue editing in notation software').isEnabled(), 'Dirty score must block export');
  await role('button', 'Play score preview').click();
  await page.locator('.playback-active-note[data-playback-start="0"]').waitFor({ state: 'attached' });
  await stop();
  await page.getByRole('button', { name: /Undo edits|Hoàn tác chỉnh sửa/ }).click();
  await ready();
  return 'PASS: 0–100% boosted instrument volume, independent metronome mute, replay, seek into tied notes, unsaved-score highlight, export gate';
}
