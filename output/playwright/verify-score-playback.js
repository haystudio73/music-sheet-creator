async page => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    if (window.__audioContexts) return;
    const Native = window.AudioContext;
    window.__audioContexts = [];
    window.AudioContext = class extends Native {
      constructor(options) { super(options); this.testGains = []; this.testVoices = []; window.__audioContexts.push(this); }
      createGain() { const gain = super.createGain(); this.testGains.push(gain); return gain; }
      createBufferSource() { const voice = super.createBufferSource(); const stop = voice.stop.bind(voice); voice.testStopped = false; voice.stop = (...args) => { if (!args.length) voice.testStopped = true; return stop(...args); }; this.testVoices.push(voice); return voice; }
    };
  });
  await page.reload();
  const play = page.getByRole('button', { name: 'Phát giai điệu dựng lại', exact: true });
  const stop = page.getByRole('button', { name: 'Dừng giai điệu dựng lại', exact: true });
  const seek = page.getByRole('slider', { name: 'Vị trí phát giai điệu dựng lại', exact: true });
  const volume = page.getByRole('slider', { name: 'Âm lượng giai điệu dựng lại', exact: true });
  await play.waitFor();
  await page.locator('.notation-container svg').first().waitFor();
  await page.getByRole('checkbox', { name: 'Tự cuộn theo nốt' }).uncheck();
  await seek.fill('15');
  if (Number(await seek.inputValue()) !== 15) throw Error('Stopped seek failed');
  await play.click();
  await page.waitForFunction(() => window.__audioContexts.some(c => c.testVoices.length));
  await page.waitForTimeout(150);
  if (Number(await seek.inputValue()) < 15) throw Error('Play ignored selected position');
  await volume.fill('0');
  await page.waitForTimeout(150);
  const muted = await page.evaluate(() => window.__audioContexts.at(-1).testGains[0].gain.value);
  if (muted > 0.0001) throw Error(`Mute failed: ${muted}`);
  await volume.fill('45');
  await page.waitForTimeout(150);
  const gain = await page.evaluate(() => window.__audioContexts.at(-1).testGains[0].gain.value);
  if (Math.abs(gain - 0.072) > 0.001) throw Error(`Live volume failed: ${gain}`);
  await seek.fill('65');
  await page.waitForTimeout(90);
  if (Math.abs(Number(await seek.inputValue()) - 65) > 1) throw Error('Forward seek failed');
  await seek.fill('2');
  await page.waitForTimeout(90);
  if (Math.abs(Number(await seek.inputValue()) - 2) > 1) throw Error('Backward seek failed');
  const contexts = await page.evaluate(() => ({ count: window.__audioContexts.length, cancelled: window.__audioContexts.at(-1).testVoices.filter(v => v.testStopped).length }));
  if (contexts.count !== 1 || !contexts.cancelled) throw Error('Seek must cancel old voices and reuse context');
  await page.waitForFunction(() => document.querySelector('.playback-active-note'));
  await page.waitForFunction(() => { const n = document.querySelector('.playback-active-note .vf-notehead path'); return n && getComputedStyle(n).fill === 'rgb(0, 102, 255)'; });
  await stop.click();
  await page.waitForFunction(() => !document.querySelector('.playback-active-note'));
  if (Number(await seek.inputValue()) !== 0) throw Error('Stop did not reset');
  await seek.focus(); await seek.press('End');
  const duration = Number(await seek.getAttribute('max'));
  if (Math.abs(Number(await seek.inputValue()) - duration) > 0.00001) throw Error('Keyboard seeking failed');
  await play.click(); await page.waitForTimeout(150);
  if (Number(await seek.inputValue()) > 1) throw Error('Replay at end did not restart');
  await seek.fill(String(Number((duration - 0.1).toFixed(3))));
  await play.waitFor();
  await page.waitForFunction(() => !document.querySelector('.playback-active-note'));
  await seek.fill('2'); await play.click(); await page.waitForTimeout(100);
  await page.getByRole('combobox', {name:'Nhạc cụ nghe thử'}).selectOption('flute');
  await play.waitFor();
  await page.waitForFunction(() => !document.querySelector('.playback-active-note'));
  await page.setViewportSize({width:1440,height:1000});
  await seek.fill('2'); await play.click();
  await page.waitForFunction(() => document.querySelector('.playback-active-note'));
  await page.screenshot({path:'output/playwright/score-playback-desktop.png'});
  await stop.click();
  await page.setViewportSize({width:390,height:844});
  await page.locator('.score-player').scrollIntoViewIfNeeded();
  const bounds = await page.locator('.score-player').boundingBox();
  if (bounds.x < 0 || bounds.x + bounds.width > 391) throw Error('Player overflows mobile viewport');
  await page.screenshot({path:'output/playwright/score-playback-mobile.png'});
  await page.setViewportSize({width:1440,height:1000});
  if (errors.length) throw Error(errors.join('\n'));
  return {passed: ['seek before play', 'live mute and volume', 'seek forward/backward', 'voice cancellation/context reuse', 'blue active notes', 'stop reset', 'keyboard seek', 'replay from end', 'natural completion', 'instrument reset', 'mobile layout'], gain, muted, contexts, errors};
}
