/* Project identity comes from the link, never from Smoosic's global autosave. */
(async () => {
  const params = new URLSearchParams(location.search);
  const project = params.get('project');
  const revision = Number(params.get('revision'));
  const status = document.getElementById('status');
  const frame = document.getElementById('notation-editor');
  const save = document.getElementById('save');
  const download = document.getElementById('download');
  const back = document.getElementById('back');
  let vi = false;
  try { vi = JSON.parse(localStorage.getItem('studio_settings_v2') || '{}').language !== 'en'; } catch { vi = true; }
  const words = {
    back: 'Quay lại dự án', save: 'Lưu vào dự án', download: 'Tải MusicXML',
    audio: 'Nghe thử trong Editor dùng mẫu piano local cho mọi nhạc cụ.',
    help: 'Chọn nốt: A–G đặt cao độ, =/− chuyển cao độ, dấu phẩy/chấm đổi trường độ. Dùng menu Smoosic để sửa ô nhịp, lời và bố cục, rồi Lưu vào dự án.',
    storage: 'Bản sửa Editor được lưu thành phiên bản MusicXML riêng trong dự án. Bản phiên âm và các tệp xuất của nó vẫn ở phiên bản nguồn đã kiểm tra.',
  };
  document.documentElement.lang = vi ? 'vi' : 'en';
  if (vi) document.querySelectorAll('[data-copy]').forEach(el => { el.textContent = words[el.dataset.copy]; });
  const message = (en, vn) => vi ? vn : en;
  const report = (text, error = false) => { status.textContent = text; status.className = error ? 'error' : ''; status.setAttribute('role', error ? 'alert' : 'status'); };
  let savedXml = '', version = 0, ready = false, saving = false, dirty = false;
  let checking = false;
  const frameReady = new Promise((resolve, reject) => {
    if (frame.contentWindow?.loadProjectXml) return resolve();
    frame.addEventListener('load', () => frame.contentWindow?.loadProjectXml ? resolve() : reject(new Error('Could not load Smoosic')), { once: true });
    setTimeout(() => reject(new Error('Smoosic loading timed out. Reload this page.')), 30000);
  });
  // Attach a rejection handler immediately while the API is loading.
  frameReady.catch(() => {});
  async function api(path, options = {}) {
    const response = await fetch(`/api${path}`, { credentials: 'same-origin', ...options });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    return data;
  }
  const endpoint = `/projects/${encodeURIComponent(project)}/editor`;
  const exportXml = () => frame.contentWindow.exportProjectXml();
  window.addEventListener('beforeunload', event => { if (dirty || saving) { event.preventDefault(); event.returnValue = ''; } });
  back.addEventListener('click', async event => {
    if (!ready) return;
    event.preventDefault();
    try {
      dirty = (await exportXml()) !== savedXml;
      if (saving || (dirty && !confirm(message('Leave without saving your editor changes?', 'Rời Editor mà không lưu thay đổi?')))) return;
      dirty = false;
      location.href = back.href;
    } catch (error) { report(error.message, true); }
  });
  try {
    if (!project || !Number.isInteger(revision) || revision < 1) throw new Error(message('Open Editor from a checked project.', 'Mở Editor từ một dự án đã kiểm tra.'));
    back.href = `/?project=${encodeURIComponent(project)}`;
    report(message('Loading current project…', 'Đang mở dự án hiện tại…'));
    await api('/health');
    const [documentData, info] = await Promise.all([api(`${endpoint}?revision=${revision}`), api(`/projects/${encodeURIComponent(project)}`)]);
    document.getElementById('title').textContent = `${info.title} · MusicXML Editor`;
    await frameReady;
    await frame.contentWindow.loadProjectXml(documentData.musicxml);
    savedXml = await exportXml(); // Normalize the baseline through the same serializer.
    version = documentData.version;
    ready = true; save.disabled = false; download.disabled = false;
    report(message(`Source revision ${revision} · Editor version ${version}`, `Nguồn ${revision} · Phiên bản Editor ${version}`));
    // Mark immediately on an edit interaction; polling also observes menu/undo changes.
    frame.contentDocument.addEventListener('input', () => { dirty = true; });
    frame.contentDocument.addEventListener('keydown', event => { if (!['Shift', 'Control', 'Alt', 'Meta', 'Escape', 'Tab'].includes(event.key)) dirty = true; });
    frame.contentDocument.addEventListener('click', () => { dirty = true; });
    setInterval(async () => {
      if (checking || saving) return;
      checking = true;
      try { dirty = (await exportXml()) !== savedXml; }
      catch { /* Save/download will show errors without losing edits. */ }
      finally { checking = false; }
    }, 1500);
  } catch (error) { report(error.message, true); }
  save.addEventListener('click', async () => {
    if (!ready || saving) return;
    saving = true; save.disabled = true;
    try {
      const musicxml = await exportXml();
      const result = await api(endpoint, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expected_revision: revision, expected_version: version, musicxml }) });
      version = result.version; savedXml = musicxml; dirty = (await exportXml()) !== savedXml;
      report(message(`Saved to project · Editor version ${version}`, `Đã lưu vào dự án · Phiên bản Editor ${version}`));
    } catch (error) { report(error.message, true); }
    finally { saving = false; save.disabled = false; }
  });
  download.addEventListener('click', async () => {
    try {
      const xml = await exportXml();
      const url = URL.createObjectURL(new Blob([xml], { type: 'application/vnd.recordare.musicxml+xml' }));
      const link = document.createElement('a'); link.href = url; link.download = `score-r${revision}-editor.musicxml`;
      document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { report(error.message, true); }
  });
})();
