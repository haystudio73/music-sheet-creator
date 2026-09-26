// Playwright CLI run-code. Only use the isolated scripts.ui_pdf_fixture data.
async page => {
  const assert = (ok, message) => { if (!ok) throw new Error(message); };
  const button = name => page.getByRole('button', { name, exact: true });
  assert(await page.getByRole('heading', { name: 'Khúc thử nghiệm – Nắng bên đồi', exact: true }).count() === 1, 'Open the PDF QA fixture');
  const pdf = button('PDF A4 printout directly from your browser');
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  // An unavailable legacy MuseScore flag must have no effect on PDF export.
  await page.route('**/api/health', async route => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...await response.json(), musescore: false } });
  });
  await page.reload();
  await pdf.waitFor();
  if (await button('Confirm reviewed').count()) {
    assert(!await pdf.isEnabled(), 'Unreviewed score blocks PDF');
    await button('Confirm reviewed').click();
  }
  await page.getByRole('button', { name: 'Score reviewed', exact: true }).waitFor();
  assert(await pdf.isEnabled(), 'PDF is available without MuseScore');
  await page.route('**/fonts/notosans.ttf', route => route.fulfill({ status: 503, body: 'QA font unavailable' }));
  await pdf.click();
  await page.getByText('Could not load the PDF font. Reload the page and try again.', { exact: true }).waitFor();
  assert(await page.locator('[data-pdf-render]').count() === 0, 'Font failure leaves no renderer');
  await page.unroute('**/fonts/notosans.ttf');
  const savePdf = async name => {
    const download = page.waitForEvent('download', { timeout: 60000 });
    await pdf.click();
    const file = await download;
    assert(file.suggestedFilename().endsWith('.pdf'), 'Correct PDF filename');
    await file.saveAs(`output/playwright/${name}.pdf`);
    assert(await page.locator('[data-pdf-render]').count() === 0, 'Temporary score renderer cleaned up');
  };
  await savePdf('pdf-export-full');
  await page.getByRole('combobox', { name: 'Export range', exact: true }).selectOption('range');
  await page.getByRole('spinbutton', { name: 'From bar', exact: true }).fill('3');
  await page.getByRole('spinbutton', { name: 'To bar', exact: true }).fill('4');
  await page.getByRole('checkbox', { name: 'Include chord symbols', exact: true }).uncheck();
  await page.getByRole('checkbox', { name: 'Include lyrics (if available)', exact: true }).uncheck();
  await savePdf('pdf-export-range');
  await page.getByRole('tab', { name: 'Melody', exact: true }).click();
  await page.getByRole('spinbutton', { name: 'Pitch of note 1', exact: true }).fill('67');
  assert(!await pdf.isEnabled(), 'Unsaved edit blocks PDF');
  await page.getByRole('button', { name: /Undo edits|Hoàn tác chỉnh sửa/ }).click();
  await page.getByRole('tab', { name: 'Score', exact: true }).click();
  await button('Switch to dark theme').click();
  await page.setViewportSize({ width: 390, height: 844 });
  await savePdf('pdf-export-mobile-dark');
  await page.screenshot({ path: 'output/playwright/pdf-export-mobile-dark.png' });
  await button('Switch to light theme').click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  assert(!errors.length, `Browser errors: ${errors.join('; ')}`);
  return 'PASS: no MuseScore, review/dirty gates, font failure and retry, full/range exports, mobile/dark, cleanup, no JS errors';
}
