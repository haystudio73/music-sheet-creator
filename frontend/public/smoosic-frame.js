/* Dedicated frame isolates Smoosic's CSS, globals and keyboard handlers. */
let application;
// Reuse the studio's bundled piano bank instead of Smoosic's online soundfonts.
const pianoSamples = [];
Smo.SuiSampleMedia.samplePromise = async (audio, progress) => {
  const response = await fetch('/instruments/acoustic_grand_piano.json');
  if (!response.ok) throw new Error('Local piano samples are missing');
  const bank = await response.json();
  const natural = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  const entries = Object.entries(bank);
  for (const [name, data] of entries) {
    const match = /^([A-G])([#b]?)(-?\d+)$/.exec(name);
    if (!match || !data.startsWith('data:audio/mp3;base64,')) continue;
    const midi = (Number(match[3]) + 1) * 12 + natural[match[1]] + (match[2] === '#' ? 1 : match[2] === 'b' ? -1 : 0);
    const bytes = Uint8Array.from(atob(data.split(',')[1]), char => char.charCodeAt(0));
    pianoSamples.push({ midi, buffer: await audio.decodeAudioData(bytes.buffer) });
    progress(Math.round(pianoSamples.length / entries.length * 100));
  }
};
// SuiSampler inherits the soundfont player's play method in pinned 1.0.44.
Object.getPrototypeOf(Smo.SuiSampler.prototype).play = function () {
  if (!this.velocity || !pianoSamples.length) return;
  const audio = Smo.SuiOscillator.audio;
  void audio.resume();
  const nearest = pianoSamples.reduce((best, sample) => Math.abs(sample.midi - this.midinumber) < Math.abs(best.midi - this.midinumber) ? sample : best);
  const source = audio.createBufferSource();
  source.buffer = nearest.buffer;
  source.playbackRate.value = 2 ** ((this.midinumber - nearest.midi + (this.detune || 0) / 100) / 12);
  const gain = audio.createGain();
  const start = audio.currentTime + Math.max(0, this.delayTime || 0);
  const end = start + Math.max(.03, this.duration);
  gain.gain.setValueAtTime(Math.min(1, this.velocity / 127), start);
  gain.gain.setTargetAtTime(.0001, end, .025);
  source.connect(gain); gain.connect(audio.destination);
  source.start(start); source.stop(end + .15);
  source.onended = () => { source.disconnect(); gain.disconnect(); };
};
window.loadProjectXml = async (musicxml) => {
  if (application) throw new Error('Score already open');
  const document = new DOMParser().parseFromString(musicxml, 'application/xml');
  if (document.querySelector('parsererror') || document.documentElement.tagName !== 'score-partwise') throw new Error('Invalid MusicXML');
  // music21 writes the same title in both fields; Smoosic treats the second as
  // a subtitle. Do not display the project title twice.
  const movement = document.querySelector('movement-title');
  if (movement?.textContent === document.querySelector('work-title')?.textContent) movement.remove();
  // Convert explicitly: configure's string parser silently substitutes a default
  // score on failure, which must never replace a user's project.
  Smo.SuiApplication.initSync();
  await Smo.SuiApplication.registerFonts();
  let score, conversionError;
  const warn = console.warn;
  // Upstream catches import errors and returns an unrelated default score.
  // Surface that failure instead of allowing it to be saved over the project.
  try {
    console.warn = (...args) => { conversionError = args[0]; warn.apply(console, args); };
    score = Smo.XmlToSmo.convert(document);
  } finally { console.warn = warn; }
  if (conversionError) throw new Error(`MusicXML import failed: ${conversionError}`);
  if (!score?.staves?.length) throw new Error('MusicXML contains no editable staves');
  application = await Smo.SuiApplication.configure({ mode: 'application', domContainer: 'smoo', initialScore: score });
};
window.exportProjectXml = async () => {
  if (!application?.view) throw new Error('Editor is not ready');
  await application.view.renderer.renderPromise();
  return new XMLSerializer().serializeToString(Smo.SmoToXml.convert(application.view.storeScore));
};
