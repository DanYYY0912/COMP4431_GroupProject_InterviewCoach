import { api } from './api';
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

export function visemeOpenness(id: number) {
  if (id === 0) return 0;
  if ([18, 19, 20, 21].includes(id)) return 0.08;
  if ([1, 2, 3, 4, 5, 6].includes(id)) return 0.8;
  return 0.35;
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

export async function azureRecognizer(
  stream: MediaStream,
  language: Language,
  onText: (text: string, final: boolean) => void,
  onError: (message: string) => void,
) {
  const token = await api.token();
  const sdk = await import('microsoft-cognitiveservices-speech-sdk');
  sdk.Recognizer.enableTelemetry(false);
  const config = sdk.SpeechConfig.fromAuthorizationToken(token.token, token.region);
  config.speechRecognitionLanguage = language;
  const azureStream = stream.clone();
  const recognizer = new sdk.SpeechRecognizer(config, sdk.AudioConfig.fromStreamInput(azureStream));
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    recognizer.close();
    azureStream.getTracks().forEach((track) => track.stop());
  };
  recognizer.recognizing = (_, event) => onText(event.result.text, false);
  recognizer.recognized = (_, event) => {
    if (event.result.reason === sdk.ResultReason.RecognizedSpeech) onText(event.result.text, true);
  };
  recognizer.canceled = (_, event) => {
    if (event.reason === sdk.CancellationReason.Error)
      onError('Azure speech stopped. Finish recording to try the local transcription fallback.');
  };
  try {
    await new Promise<void>((resolve, reject) =>
      recognizer.startContinuousRecognitionAsync(resolve, reject),
    );
  } catch (error) {
    close();
    throw error;
  }
  return {
    stop: () =>
      new Promise<void>((resolve) => {
        if (closed) {
          resolve();
          return;
        }
        const timeout = setTimeout(() => {
          close();
          resolve();
        }, 5000);
        const complete = () => {
          clearTimeout(timeout);
          close();
          resolve();
        };
        recognizer.stopContinuousRecognitionAsync(complete, complete);
      }),
  };
}

type PlaybackCallbacks = {
  onStart: () => void;
  onMouth: (value: number) => void;
  onEnd: () => void;
  onNotice: (text: string) => void;
};
export function playQuestion(
  text: string,
  language: Language,
  cloudConsent: boolean,
  callbacks: PlaybackCallbacks,
): () => void {
  let stopped = false;
  let stopAudio: (() => void) | null = null;
  let frame = 0;
  let closeSynth: (() => void) | null = null;
  const stop = () => {
    if (stopped) return;
    stopped = true;
    cancelAnimationFrame(frame);
    stopAudio?.();
    closeSynth?.();
    callbacks.onMouth(0);
    callbacks.onEnd();
  };
  const browser = () => {
    if (stopped) return;
    if (!('speechSynthesis' in window)) {
      callbacks.onNotice('Speech playback is unavailable. Read the question in the captions.');
      callbacks.onEnd();
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = language;
    utterance.rate = 0.93;
    const localVoices = speechSynthesis
      .getVoices()
      .filter(
        (voice) =>
          voice.localService &&
          (voice.lang.toLowerCase() === language.toLowerCase() ||
            (language === 'en-HK' && voice.lang.startsWith('en'))),
      );
    if (!localVoices.length) {
      callbacks.onNotice(
        'No local voice is available for this language. Captions remain available.',
      );
      callbacks.onEnd();
      return;
    }
    utterance.voice = localVoices[0];
    utterance.onstart = () => {
      if (stopped) return;
      callbacks.onStart();
      callbacks.onNotice('Playing the local system voice. Mouth motion is approximate.');
      const animate = () => {
        if (stopped) return;
        callbacks.onMouth(0.25 + Math.abs(Math.sin(performance.now() / 100)) * 0.55);
        frame = requestAnimationFrame(animate);
      };
      animate();
    };
    utterance.onend = () => {
      if (stopped) return;
      cancelAnimationFrame(frame);
      callbacks.onMouth(0);
      callbacks.onEnd();
    };
    utterance.onerror = () => {
      if (stopped) return;
      cancelAnimationFrame(frame);
      callbacks.onMouth(0);
      callbacks.onEnd();
      callbacks.onNotice('Speaker playback failed. You can continue with captions.');
    };
    stopAudio = () => speechSynthesis.cancel();
    speechSynthesis.speak(utterance);
  };
  if (!cloudConsent) {
    browser();
    return stop;
  }
  void (async () => {
    try {
      const token = await api.token();
      if (stopped) return;
      const sdk = await import('microsoft-cognitiveservices-speech-sdk');
      if (stopped) return;
      const config = sdk.SpeechConfig.fromAuthorizationToken(token.token, token.region);
      config.speechSynthesisVoiceName =
        language === 'zh-HK' ? 'zh-HK-HiuMaanNeural' : 'en-HK-YanNeural';
      config.speechSynthesisOutputFormat = sdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm;
      const synthesizer = new sdk.SpeechSynthesizer(config, null);
      closeSynth = () => synthesizer.close();
      const visemes: { time: number; id: number }[] = [];
      synthesizer.visemeReceived = (_, event) =>
        visemes.push({ time: event.audioOffset / 10000000, id: event.visemeId });
      const audio = await new Promise<ArrayBuffer>((resolve, reject) =>
        synthesizer.speakTextAsync(
          text,
          (result) => {
            if (result.reason === sdk.ResultReason.SynthesizingAudioCompleted)
              resolve(result.audioData);
            else reject(new Error('Speech synthesis unavailable'));
          },
          reject,
        ),
      );
      synthesizer.close();
      closeSynth = null;
      if (stopped) return;
      const context = new AudioContext();
      stopAudio = () => {
        void context.close();
      };
      const buffer = await context.decodeAudioData(audio);
      if (stopped) {
        await context.close();
        return;
      }
      await context.resume();
      if (stopped) return;
      const source = context.createBufferSource();
      const analyser = context.createAnalyser();
      analyser.fftSize = 256;
      source.buffer = buffer;
      source.connect(analyser);
      analyser.connect(context.destination);
      const amplitude = new Uint8Array(analyser.fftSize);
      const started = context.currentTime;
      let index = -1;
      source.onended = () => {
        cancelAnimationFrame(frame);
        callbacks.onMouth(0);
        callbacks.onEnd();
        void context.close();
      };
      source.start();
      callbacks.onStart();
      const animate = () => {
        if (stopped) return;
        const elapsed = context.currentTime - started;
        while (index + 1 < visemes.length && visemes[index + 1].time <= elapsed) index++;
        if (index >= 0) callbacks.onMouth(visemeOpenness(visemes[index].id));
        else {
          analyser.getByteTimeDomainData(amplitude);
          const level = Math.sqrt(
            amplitude.reduce((sum, n) => sum + ((n - 128) / 128) ** 2, 0) / amplitude.length,
          );
          callbacks.onMouth(Math.min(1, level * 7));
        }
        frame = requestAnimationFrame(animate);
      };
      stopAudio = () => {
        source.onended = null;
        try {
          source.stop();
        } catch {
          /* already ended */
        }
        void context.close();
      };
      animate();
      if (!visemes.length)
        callbacks.onNotice(
          'Voice is playing with audio-driven mouth motion. This voice did not supply viseme timing.',
        );
    } catch {
      if (!stopped) {
        callbacks.onNotice('Azure voice is unavailable. Trying a local system voice.');
        browser();
      }
    }
  })();
  return stop;
}
