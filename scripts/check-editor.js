// Playwright CLI run-code. Run only on the isolated ui-fixture editor page.
async page => {
  const assert = (ok, message) => { if (!ok) throw new Error(message); };
  assert(page.url().includes('project=ui-fixture'), 'Use the isolated UI fixture');
  const data = async () => page.evaluate(async () => {
    const xml = await document.querySelector('iframe').contentWindow.exportProjectXml();
    const doc = new DOMParser().parseFromString(xml, 'application/xml');
    return { xml, pitch: doc.querySelector('pitch step')?.textContent, notes: doc.querySelectorAll('note pitch').length,
      measures: doc.querySelectorAll('measure').length, lyrics: [...doc.querySelectorAll('lyric text')].map(n => n.textContent) };
  });
  await page.getByRole('button', { name: 'Save to project', exact: true }).waitFor();
  const before = await data();
  assert(before.notes === 60 && before.measures === 16 && before.lyrics.includes('Nắng'), 'Import must preserve written notes, tied segments, bars and lyrics');
  const next = before.pitch === 'D' ? 'e' : 'd';
  await page.frameLocator('#notation-editor').locator('g.vf-stavenote').first().click();
  await page.keyboard.press(next);
  await page.getByRole('button', { name: 'Save to project', exact: true }).click();
  await page.getByRole('status').filter({ hasText: 'Saved to project' }).waitFor();
  assert((await data()).pitch === next.toUpperCase(), 'Keyboard pitch edit must affect MusicXML');
  await page.reload();
  await page.waitForFunction(() => !document.querySelector('#save').disabled);
  assert((await data()).pitch === next.toUpperCase(), 'Saved pitch must survive reopening');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download MusicXML', exact: true }).click();
  const file = await download;
  assert(file.suggestedFilename().endsWith('.musicxml'), 'Download filename');
  await file.saveAs('output/playwright/editor-roundtrip.musicxml');
  await page.getByRole('link', { name: 'Back to project', exact: false }).click();
  await page.getByRole('heading', { name: 'Playback regression', exact: true }).waitFor();
  assert(await page.getByRole('button', { name: 'Open Editor', exact: true }).isEnabled(), 'Reviewed source remains available');
  const sections = page.locator('.collapsible-section');
  assert(await sections.count() === 8, 'All workspace and inspector boxes have toggles');
  for (let i = 0; i < await sections.count(); i++) {
    const section = sections.nth(i), toggle = section.locator('.collapse-toggle');
    const controlled = await toggle.getAttribute('aria-controls');
    await toggle.click();
    assert(await toggle.getAttribute('aria-expanded') === 'false', 'Collapsed ARIA state');
    assert(await page.locator(`[id="${controlled}"]`).isHidden(), 'Body hidden');
    await toggle.click();
    assert(await toggle.getAttribute('aria-expanded') === 'true', 'Expanded ARIA state');
  }
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  assert(await page.getByRole('combobox', { name: 'Processing device', exact: true }).inputValue() === 'cpu', 'CPU choice survives navigation');
  assert(await page.getByRole('combobox', { name: 'Lyrics font', exact: true }).inputValue() === 'Birthstone', 'Font choice survives navigation');
  await page.getByRole('button', { name: 'Close', exact: true }).click();
  await page.locator('.notation-container:not(.is-loading) .studio-lyric').first().waitFor();
  const fonts = await page.locator('.notation-container').evaluate(el => [...el.querySelectorAll('text')].map(e => ({ lyric: !!e.closest('.studio-lyric'), font: getComputedStyle(e).fontFamily })));
  assert(fonts.some(f => f.lyric && f.font.includes('Birthstone')), 'Selected font applied to lyrics');
  assert(fonts.every(f => f.lyric || !f.font.includes('Birthstone')), 'Other notation fonts unchanged');
  await page.screenshot({ path: 'output/playwright/editor-workflow-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForFunction(() => document.querySelector('.sidebar').getBoundingClientRect().right <= 1);
  await page.screenshot({ path: 'output/playwright/editor-workflow-mobile.png', fullPage: true });
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'No mobile page overflow');
  console.log('PASS: import, pitch edit, save/reopen, download, all 8 collapses, settings persistence, lyrics-only font, mobile layout');
}
