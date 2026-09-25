"""Bounded local estimates of tempo, tonal centre and meter from actual PCM.

Spectral-flux autocorrelation estimates pulse; chroma/profile correlation
estimates key. Meter is an accent-pattern suggestion, never a certainty.
"""
from pathlib import Path
import subprocess
import numpy as np
from scipy import signal
from .transcription import ffmpeg_executable, _creation_flags

SAMPLE_RATE = 11025
MAX_SECONDS = 120
KEYS = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def estimate_pcm(y: np.ndarray, sample_rate: int = SAMPLE_RATE) -> dict:
    y = np.asarray(y, dtype=np.float32)
    if len(y) < sample_rate * 3 or not np.all(np.isfinite(y)):
        raise ValueError('Audio cần ít nhất 3 giây để dò thông số.')
    if float(np.sqrt(np.mean(y * y))) < 1e-5:
        raise ValueError('Audio quá yên lặng để dò tempo và giọng.')
    hop, fft = 256, 4096
    frequencies, _, spectrum = signal.stft(y, fs=sample_rate, nperseg=fft, noverlap=fft-hop, boundary=None)
    magnitude = np.abs(spectrum)
    # Local spectral peaks reduce the influence of noise and broad transients.
    mask = (frequencies >= 65) & (frequencies <= 2100)
    pitches = np.rint(69 + 12*np.log2(frequencies[mask]/440)).astype(int) % 12
    peaks = (magnitude[1:-1] > magnitude[:-2]) & (magnitude[1:-1] >= magnitude[2:])
    peak_energy = np.pad(peaks, ((1, 1), (0, 0))) * magnitude
    chroma = np.bincount(pitches, weights=np.sum(peak_energy[mask], axis=1), minlength=12)
    key_scores = []
    for suffix, profile in [('', MAJOR), ('m', MINOR)]:
        for root in range(12):
            correlation = float(np.corrcoef(chroma, np.roll(profile, root))[0, 1]) if np.std(chroma) > 0 else 0
            # Use the key spellings supported by the score editor.
            key = KEYS[root] + suffix
            if suffix: key = {'Dbm': 'C#m', 'Ebm': 'D#m', 'Abm': 'G#m'}.get(key, key)
            key_scores.append((correlation, key))
    key_scores.sort(reverse=True)
    key_confidence = max(0., min(1., (key_scores[0][0]-key_scores[1][0])*4))

    flux = np.maximum(0, np.diff(np.log1p(magnitude * 100), axis=1)).sum(axis=0)
    flux = np.maximum(0, flux - np.median(flux))
    frame_rate = sample_rate/hop
    onset_peaks, _ = signal.find_peaks(flux, distance=max(1, int(frame_rate*.18)), prominence=max(float(flux.max())*.06, 1e-8))
    tempo, meter, tempo_confidence, meter_confidence = None, None, 0., 0.
    if len(onset_peaks) >= 4 and float(flux.max()) > 1e-6:
        ac = signal.correlate(flux, flux, mode='full', method='fft')[len(flux)-1:]
        lags = np.arange(max(1, int(frame_rate*60/200)), min(len(ac), int(frame_rate*60/50)+1))
        # Prefer a plausible beat octave without hiding half/double ambiguity.
        bpms = frame_rate*60/lags
        scores = ac[lags] * np.exp(-.5*(np.log2(bpms/110)/.8)**2)
        peak = int(lags[int(np.argmax(scores))])
        denominator = ac[peak-1] - 2*ac[peak] + ac[peak+1]
        adjustment = .5*(ac[peak-1]-ac[peak+1])/denominator if abs(denominator) > 1e-9 else 0
        lag = peak + float(np.clip(adjustment, -.5, .5))
        tempo = round(frame_rate*60/lag, 1)
        tempo_confidence = float(np.clip(ac[peak]/max(ac[0], 1e-9), 0, 1))
        # Compare accents on the pulse grid, independent of the initial beat.
        phase = max(range(peak), key=lambda p: float(flux[np.arange(p, len(flux)-1, lag).astype(int)].sum()))
        grid = np.arange(phase, len(flux), lag)
        accents = np.array([flux[max(0, int(i)-2):int(i)+3].max() for i in grid])
        candidates = []
        if len(accents) >= 12:
            for count in (3, 4):
                means = np.array([np.mean(accents[p::count]) for p in range(count)])
                contrast = float((means.max()-np.median(means))/max(means.max(), 1e-9))
                candidates.append((contrast, count))
            candidates.sort(reverse=True)
            meter_confidence = max(0., candidates[0][0]-candidates[1][0])
            if meter_confidence >= .08: meter = [candidates[0][1], 4]
    return {
        'tempo': tempo, 'key': key_scores[0][1] if np.sum(chroma) > 1e-7 else None,
        'meter': meter, 'tempo_confidence': round(tempo_confidence, 3),
        'key_confidence': round(key_confidence, 3), 'meter_confidence': round(meter_confidence, 3),
        'analyzed_seconds': round(len(y)/sample_rate, 1),
        'method': 'spectral-flux / chroma-profile / beat-accent',
        'alternatives': [{'key': key, 'score': round(value, 3)} for value, key in key_scores[:3]],
    }


def analyze_audio(path: Path) -> dict:
    executable = ffmpeg_executable()
    if not executable: raise ValueError('Cần FFmpeg để đọc audio.')
    try:
        result = subprocess.run([executable, '-v', 'error', '-i', str(path), '-t', str(MAX_SECONDS), '-vn', '-ac', '1', '-ar', str(SAMPLE_RATE), '-f', 'f32le', 'pipe:1'], capture_output=True, timeout=90, creationflags=_creation_flags())
    except subprocess.TimeoutExpired as exc:
        raise ValueError('Dò audio quá thời gian. Hãy thử tệp ngắn hơn.') from exc
    if result.returncode: raise ValueError('Không đọc được audio để dò thông số.')
    return estimate_pcm(np.frombuffer(result.stdout, dtype='<f4'))
