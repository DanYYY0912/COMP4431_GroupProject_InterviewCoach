import type { Language } from './types';

export function encodeWav(chunks: Float32Array[], sampleRate: number): ArrayBuffer {
  const samples = chunks.reduce((sum, c) => sum + c.length, 0);
  const merged = new Float32Array(samples);
  let cursor = 0;
  for (const chunk of chunks) {
    merged.set(chunk, cursor);
    cursor += chunk.length;
  }
  const ratio = sampleRate / 16000;
  const length = Math.floor(samples / ratio);
  const buffer = new ArrayBuffer(44 + length * 2);
  const view = new DataView(buffer);
  function string(offset: number, value: string) {
    for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i));
  }
  string(0, 'RIFF');
  view.setUint32(4, 36 + length * 2, true);
  string(8, 'WAVE');
  string(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, 16000, true);
  view.setUint32(28, 32000, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  string(36, 'data');
  view.setUint32(40, length * 2, true);
  for (let i = 0; i < length; i++) {
    const start = Math.floor(i * ratio),
      end = Math.min(Math.floor((i + 1) * ratio), samples);
    let sum = 0;
    for (let j = start; j < end; j++) sum += merged[j];
    const sample = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)));
    view.setInt16(44 + i * 2, sample < 0 ? sample * 32768 : sample * 32767, true);
  }
  return buffer;
}

export type RecordedAnswer = {
  blob: Blob;
  duration: number;
  pauseCount: number;
  silenceSeconds: number;
};
export async function recordMicrophone(
  onLevel: (level: number) => void,
): Promise<{ stream: MediaStream; stop: () => Promise<RecordedAnswer> }> {
  if (!navigator.mediaDevices?.getUserMedia)
    throw new Error('This browser cannot access a microphone. You can type your answer.');
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
  });
  let createdContext: AudioContext | null = null;
  try {
    const context = new AudioContext();
    createdContext = context;
    await context.resume();
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(4096, 1, 1);
    const mute = context.createGain();
    mute.gain.value = 0;
    const chunks: Float32Array[] = [];
    let silence = 0,
      pauseLength = 0,
      pauseCount = 0,
      speechSeen = false,
      samples = 0;
    processor.onaudioprocess = (event) => {
      const chunk = event.inputBuffer.getChannelData(0);
      if (samples >= context.sampleRate * 300) return;
      chunks.push(new Float32Array(chunk));
      samples += chunk.length;
      const rms = Math.sqrt(chunk.reduce((sum, v) => sum + v * v, 0) / chunk.length);
      onLevel(Math.min(1, rms * 7));
      const elapsed = chunk.length / context.sampleRate;
      if (rms < 0.012) {
        silence += elapsed;
        if (speechSeen) pauseLength += elapsed;
      } else {
        if (pauseLength >= 0.6) pauseCount++;
        pauseLength = 0;
        speechSeen = true;
      }
    };
    source.connect(processor);
    processor.connect(mute);
    mute.connect(context.destination);
    let stopped = false;
    return {
      stream,
      stop: async () => {
        if (stopped) return { blob: new Blob(), duration: 0, pauseCount: 0, silenceSeconds: 0 };
        stopped = true;
        processor.disconnect();
        source.disconnect();
        mute.disconnect();
        stream.getTracks().forEach((track) => track.stop());
        onLevel(0);
        const rate = context.sampleRate;
        await context.close();
        return {
          blob: new Blob([encodeWav(chunks, rate)], { type: 'audio/wav' }),
          duration: samples / rate,
          pauseCount,
          silenceSeconds: Math.round(silence * 10) / 10,
        };
      },
    };
  } catch (error) {
    stream.getTracks().forEach((track) => track.stop());
    if (createdContext && createdContext.state !== 'closed')
      await createdContext.close().catch(() => {});
    throw error;
  }
}

type PlaybackCallbacks = {
  onStart: () => void;
  onEnd: () => void;
  onNotice: (text: string) => void;
  onViseme?: (openness: number) => void;
};

// Browser boundaries identify words/characters, not phonemes. These cues are only
// approximate mouth shapes; the renderer supplies motion while speech is active.
function boundaryOpenness(text: string, index: number): number {
  const word =
    text
      .slice(index)
      .match(/^[\p{L}\p{N}]+/u)?.[0]
      ?.toLowerCase() || '';
  if (/^[bmp]/.test(word)) return 0.12;
  if (/^[a]/.test(word)) return 0.95;
  if (/^[ei]/.test(word)) return 0.5;
  if (/^[ou]/.test(word)) return 0.75;
  if (/[a]/.test(word)) return 0.85;
  return word ? 0.65 : 0.1;
}

// Web Speech exposes names and locales, but no gender field. Keep Jamie on
// identifiable male voices; never guess from list order or lower a female voice's pitch.
function jamieVoice(voices: SpeechSynthesisVoice[], language: Language) {
  const names =
    language === 'en-HK'
      ? /\b(daniel|alex|jamie|aaron|david|mark|george|james|oliver|thomas|guy|ryan)\b/i
      : /\b(danny|wanlung(?:neural)?|yunsong(?:neural)?)\b/i;
  const localVoices = voices.filter((voice) => {
    const locale = voice.lang.replaceAll('_', '-').toLowerCase();
    const languageMatches =
      language === 'en-HK'
        ? locale === 'en' || locale.startsWith('en-')
        : locale === 'zh-hk' || locale === 'yue' || locale.startsWith('yue-');
    return voice.localService && languageMatches && names.test(voice.name);
  });
  return (
    localVoices.find(
      (voice) => voice.lang.replaceAll('_', '-').toLowerCase() === language.toLowerCase(),
    ) ?? localVoices[0]
  );
}

export function playQuestion(
  text: string,
  language: Language,
  callbacks: PlaybackCallbacks,
): () => void {
  let stopped = false;
  let started = false;
  let requested = false;
  let voicesTimer: ReturnType<typeof setTimeout> | undefined;
  let startTimer: ReturnType<typeof setTimeout> | undefined;
  const synthesis = 'speechSynthesis' in window ? window.speechSynthesis : null;
  const clearVoiceWait = () => {
    clearTimeout(voicesTimer);
    synthesis?.removeEventListener('voiceschanged', voicesChanged);
  };
  const finish = () => {
    if (stopped) return;
    stopped = true;
    clearVoiceWait();
    clearTimeout(startTimer);
    callbacks.onViseme?.(0);
    callbacks.onEnd();
  };
  const stop = () => {
    if (stopped) return;
    finish();
    if (requested) synthesis?.cancel();
  };
  if (!synthesis) {
    callbacks.onNotice('Speech playback is unavailable. Read the question on screen.');
    finish();
    return stop;
  }
  const speech = synthesis;
  function requestPlayback(): boolean {
    if (stopped || requested) return true;
    const voice = jamieVoice(speech.getVoices(), language);
    if (!voice) return false;
    clearVoiceWait();
    requested = true;
    try {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = voice.lang;
      utterance.rate = 0.93;
      utterance.voice = voice;
      utterance.onstart = () => {
        if (stopped || started) return;
        started = true;
        clearTimeout(startTimer);
        callbacks.onStart();
        callbacks.onViseme?.(0.65);
      };
      utterance.onboundary = (event) => {
        if (!stopped && started) callbacks.onViseme?.(boundaryOpenness(text, event.charIndex));
      };
      utterance.onend = finish;
      utterance.onerror = (event) => {
        if (stopped) return;
        callbacks.onNotice(
          event.error === 'not-allowed'
            ? 'Your browser blocked audio playback. Select Read question to try again, or read the question on screen.'
            : 'Speaker playback failed. Select Read question to try again, or read the question on screen.',
        );
        finish();
      };
      startTimer = setTimeout(() => {
        if (stopped || started) return;
        callbacks.onNotice(
          'Audio did not start. Select Read question to try again, or read the question on screen.',
        );
        stop();
      }, 4000);
      speech.speak(utterance);
    } catch {
      callbacks.onNotice(
        'Speaker playback failed. Select Read question to try again, or read the question on screen.',
      );
      stop();
    }
    return true;
  }
  function voicesChanged() {
    requestPlayback();
  }
  if (!requestPlayback()) {
    speech.addEventListener('voiceschanged', voicesChanged);
    voicesTimer = setTimeout(() => {
      if (requestPlayback()) return;
      callbacks.onNotice(
        `No local male voice is available for Jamie in ${language === 'zh-HK' ? 'Cantonese' : 'English'}. Enable a matching male voice in your system speech settings, then select Read question. The written question remains available.`,
      );
      finish();
    }, 1500);
    // A voice list can become available between the first check and listener setup.
    requestPlayback();
  }
  return stop;
}
