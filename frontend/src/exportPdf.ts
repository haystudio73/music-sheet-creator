import { OpenSheetMusicDisplay } from 'opensheetmusicdisplay';
import { jsPDF } from 'jspdf';
import 'svg2pdf.js';
import { t } from './i18n';

const FONT_FAMILY = 'Score PDF Noto Sans';
const FONT_FILE = 'notosans.ttf';
// Fixed print width, independent of the viewport, sidebar and screen zoom.
const PAGE_WIDTH_PX = 794;
let fontPromise: Promise<ArrayBuffer> | undefined;

async function fetchFont(): Promise<ArrayBuffer> {
  const fontUrls = [`/fonts/${FONT_FILE}`, `./fonts/${FONT_FILE}`];
  for (const url of fontUrls) {
    try {
      const res = await fetch(url);
      if (res.ok) {
        const bytes = await res.arrayBuffer();
        const font = await new FontFace(FONT_FAMILY, bytes).load();
        document.fonts.add(font);
        return bytes;
      }
    } catch {
      // Continue to fallback candidate URL
    }
  }
  throw new Error(t('Không tải được font để xuất PDF. Vui lòng tải lại trang và thử lại.'));
}

function loadFont(): Promise<ArrayBuffer> {
  // Reuse one FontFace across exports; a failed load can be retried.
  return fontPromise ??= fetchFont().catch(error => { fontPromise = undefined; throw error; });
}

function fontBase64(bytes: ArrayBuffer): string {
  const data = new Uint8Array(bytes);
  let binary = '';
  for (let start = 0; start < data.length; start += 8192) {
    binary += String.fromCharCode(...data.subarray(start, start + 8192));
  }
  return btoa(binary);
}

/** Render a fresh, paginated score; never capture preview selections or colors. */
export async function createScorePdf(musicxml: string): Promise<Blob> {
  const fontBytes = await loadFont();
  const mount = document.createElement('div');
  mount.dataset.pdfRender = 'true';
  mount.setAttribute('aria-hidden', 'true');
  Object.assign(mount.style, {
    position: 'fixed', left: '-100000px', top: '0', width: `${PAGE_WIDTH_PX}px`,
    background: '#fff', color: '#000', pointerEvents: 'none',
  });
  document.body.append(mount);
  let osmd: OpenSheetMusicDisplay | undefined;
  try {
    osmd = new OpenSheetMusicDisplay(mount, {
      autoResize: false, backend: 'svg', pageFormat: 'A4_P',
      drawingParameters: 'default', defaultFontFamily: FONT_FAMILY,
      drawTitle: true, drawSubtitle: false, drawComposer: true,
      drawPartNames: false, disableCursor: true,
      darkMode: false, defaultColorMusic: '#000000', defaultColorLabel: '#000000',
    });
    osmd.EngravingRules.HorizontalBetweenLyricsDistance = 0.6;
    osmd.Zoom = 1;
    await osmd.load(musicxml);
    osmd.render();
    const pages = Array.from(mount.querySelectorAll<SVGSVGElement>('svg'));
    if (!pages.length) throw new Error(t('Không tạo được khuông nhạc để xuất PDF.'));

    const pdf = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'a4', compress: true, putOnlyUsedFonts: true });
    pdf.addFileToVFS(FONT_FILE, fontBase64(fontBytes));
    // OSMD uses bold/italic for some labels; map every style to the bundled
    // Unicode font so Vietnamese text never falls back to the ASCII PDF fonts.
    for (const style of ['normal', 'bold', 'italic', 'bolditalic']) {
      pdf.addFont(FONT_FILE, FONT_FAMILY, style);
    }
    pdf.setFont(FONT_FAMILY, 'normal');
    const xml = new DOMParser().parseFromString(musicxml, 'application/xml');
    pdf.setProperties({ title: xml.querySelector('work-title, movement-title')?.textContent || 'Lead sheet', creator: 'Bản Nhạc Local' });
    const width = pdf.internal.pageSize.getWidth();
    const height = pdf.internal.pageSize.getHeight();

    for (const [index, svg] of pages.entries()) {
      if (index) pdf.addPage('a4', 'portrait');
      // VexFlow may choose a system font for tempo or chord labels. Normalize
      // text only; musical glyphs remain sharp SVG paths in the PDF.
      svg.querySelectorAll('text').forEach(text => {
        // VexFlow's tempo uses pt. svg2pdf only accepts px/em/unitless font
        // sizes, otherwise it emits invisible text at font size zero.
        const fontSize = getComputedStyle(text).fontSize;
        text.setAttribute('font-size', fontSize);
        text.style.fontSize = fontSize;
        text.setAttribute('font-family', FONT_FAMILY);
        text.style.fontFamily = FONT_FAMILY;
      });
      const svgWidth = svg.viewBox?.baseVal?.width || svg.width?.baseVal?.value || parseFloat(svg.getAttribute('width') || '0');
      const svgHeight = svg.viewBox?.baseVal?.height || svg.height?.baseVal?.value || parseFloat(svg.getAttribute('height') || '0');
      if (!(svgWidth > 0 && svgHeight > 0)) throw new Error(t('Không tạo được khuông nhạc để xuất PDF.'));
      const scale = Math.min(width / svgWidth, height / svgHeight);
      await pdf.svg(svg, { x: (width - svgWidth * scale) / 2, y: 0, width: svgWidth * scale, height: svgHeight * scale });
      // Yield between pages so the UI can update while exporting long scores.
      await new Promise<void>(resolve => setTimeout(resolve, 0));
    }
    return pdf.output('blob');
  } finally {
    osmd?.clear();
    mount.remove();
  }
}
