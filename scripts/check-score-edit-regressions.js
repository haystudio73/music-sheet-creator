// Playwright CLI run-code. Run only against scripts/ui_edit_regression_fixture.py data.
async page => {
  const assert = (ok, message) => { if (!ok) throw new Error(message); };
  const waitForScore = async () => {
    await page.locator('.notation-container:not(.is-loading) .studio-interactive-note').first().waitFor();
  };

  await page.addInitScript(() => localStorage.removeItem('studio_check_export_history_v1'));
  await page.goto('http://127.0.0.1:8766/?project=ui-no-lyrics');
  const guide = page.getByRole('dialog', { name: 'Hướng dẫn sử dụng' });
  if (await guide.isVisible())
    await guide.getByRole('button', { name: 'Đóng', exact: true }).click();
  await page.getByRole('heading', { name: 'No lyric project', exact: true }).waitFor();
  await waitForScore();
  assert(await page.locator('.studio-interactive-lyric').count() === 0, 'Fixture must have no lyrics');

  const firstNote = page.locator('.studio-interactive-note').first();
  await firstNote.evaluate(element => element.scrollIntoView({ block: 'center', inline: 'nearest' }));
  await firstNote.click();
  const editor = page.locator('.in-place-note-editor');
  await editor.waitFor();
  const [noteBox, editorBox, scoreBox] = await Promise.all([
    firstNote.boundingBox(), editor.boundingBox(), page.locator('.notation-container').boundingBox()
  ]);
  assert(noteBox && editorBox && scoreBox, 'Selected note, score and quick editor must have measurable positions');
  assert(editorBox.y >= noteBox.y + noteBox.height + 6, 'Quick editor must appear directly below the selected note');
  assert(editorBox.y - (noteBox.y + noteBox.height) <= 14, 'Quick editor must stay close to its selected note');
  assert(editorBox.x >= scoreBox.x - 1 && editorBox.x + editorBox.width <= scoreBox.x + scoreBox.width + 1,
    'Quick editor must stay within the score column');
  await editor.getByText(/Nốt hợp lệ · ô nhịp 1, phách 1/).waitFor();
  await editor.getByTitle('Tròn (4)').click();
  await editor.getByRole('alert').filter({ hasText: 'vượt sang nốt kế tiếp' }).waitFor();
  assert((await editor.getByTitle('Đen (1)').getAttribute('class'))?.includes('active'), 'Invalid duration must be rejected');
  const pitch = editor.locator('.in-place-pitch-select');
  const beforeSavePitch = await pitch.inputValue();
  await editor.locator('.in-place-pitch-group button').nth(1).click();
  assert(await pitch.inputValue() !== beforeSavePitch, 'Pitch edit before save');
  await page.getByRole('button', { name: 'Lưu', exact: true }).click();
  await page.getByRole('status').filter({ hasText: 'Đã lưu phiên bản' }).waitFor();
  await waitForScore();

  await page.locator('.studio-interactive-note').first().click();
  await editor.waitFor();
  const savedPitch = await pitch.inputValue();
  await editor.locator('.in-place-pitch-group button').nth(1).click();
  await page.keyboard.press('Control+z');
  await page.waitForFunction(value => document.querySelector('.in-place-pitch-select')?.value === value, savedPitch);

  await editor.locator('.in-place-pitch-group button').nth(1).click();
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: /Lyric project/ }).click();
  await page.getByRole('heading', { name: 'Lyric project', exact: true }).waitFor();
  await waitForScore();

  await page.locator('.studio-interactive-lyric').first().click();
  await editor.waitFor();
  await page.locator('.project-heading').click();
  await editor.waitFor({ state: 'hidden' });

  await page.getByRole('button', { name: 'Xác nhận đã kiểm tra', exact: true }).click();
  await page.getByRole('status').filter({ hasText: 'Đã đánh dấu bản nhạc' }).waitFor();
  let stored = await page.evaluate(() => JSON.parse(localStorage.getItem('studio_check_export_history_v1') || '[]'));
  assert(stored.length === 1 && stored[0].kind === 'review', 'Review result must be recorded');

  const abc = page.getByRole('button', { name: /score\.abc/ });
  for (let index = 0; index < 10; index++) {
    const [download] = await Promise.all([page.waitForEvent('download'), abc.click()]);
    await download.cancel();
    await abc.waitFor({ state: 'visible' });
    await page.waitForFunction(() => ![...document.querySelectorAll('button')].find(button => button.textContent?.includes('score.abc'))?.disabled);
  }
  stored = await page.evaluate(() => JSON.parse(localStorage.getItem('studio_check_export_history_v1') || '[]'));
  assert(stored.length === 10, 'Activity history must be capped at 10');
  const allowed = new Set(['id', 'kind', 'projectId', 'projectTitle', 'audioName', 'audioDuration', 'revision', 'createdAt', 'format', 'outputFilename']);
  assert(stored.every(item => Object.keys(item).every(key => allowed.has(key))), 'History must contain metadata only');
  assert(stored.every(item => item.kind === 'review' || item.kind === 'export'), 'Only review/export results are allowed');

  await page.getByRole('tab', { name: /Giai điệu/ }).click();
  const title = page.getByLabel('Tên bản nhạc');
  for (let index = 0; index < 100; index++)
    await title.fill(`Undo ${index}`);
  await page.getByRole('tab', { name: /Giai điệu/ }).focus();
  for (let index = 0; index < 99; index++)
    await page.keyboard.press('Control+z');
  await page.waitForFunction(() => document.querySelector('input[value="Undo 0"]'));
  assert(await page.getByRole('button', { name: /Hoàn tác chỉnh sửa/ }).isDisabled(), 'Undo history must contain exactly the latest 99 changes');

  console.log('PASS: no-lyric edit, note validation, edit-after-save, Ctrl+Z/99 cap, save-before-switch, one-click close, Local Storage history');
}
