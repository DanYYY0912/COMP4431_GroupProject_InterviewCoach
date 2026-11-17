import { afterEach, describe, expect, it, vi } from 'vitest';
import { encodeWav, recordMicrophone, playQuestion } from './audio';

afterEach(() => vi.unstubAllGlobals());

describe('local audio encoding', () => {
  it('writes a mono PCM WAV with a valid 16 kHz header', () => {
    const wav = encodeWav([new Float32Array([0, 0.5, -0.5, 1])], 16000);
    const header = new DataView(wav);
    expect(new TextDecoder().decode(wav.slice(0, 4))).toBe('RIFF');
    expect(header.getUint32(24, true)).toBe(16000);
    expect(header.getUint16(22, true)).toBe(1);
    expect(header.getUint32(40, true)).toBe(8);
    expect(header.getInt16(46, true)).toBe(16383);
  });
  it('releases microphone permission if audio initialization fails', async () => {
    const stop = vi.fn();
    vi.stubGlobal('navigator', {
      mediaDevices: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }) },
    });
    vi.stubGlobal(
      'AudioContext',
      class {
        constructor() {
          throw new Error('Audio device unavailable');
        }
      },
    );
    await expect(recordMicrophone(vi.fn())).rejects.toThrow('Audio device unavailable');
    expect(stop).toHaveBeenCalledOnce();
  });
});

describe('local question playback', () => {
  function setup(voices: { lang: string; localService: boolean }[]) {
    const synthesis = { getVoices: vi.fn(() => voices), speak: vi.fn(), cancel: vi.fn() };
    vi.stubGlobal('speechSynthesis', synthesis);
    vi.stubGlobal(
      'SpeechSynthesisUtterance',
      class {
        constructor(public text: string) {}
      },
    );
    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn(() => 1),
    );
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    const callbacks = { onStart: vi.fn(), onEnd: vi.fn(), onMouth: vi.fn(), onNotice: vi.fn() };
    return { synthesis, callbacks };
  }
  it('never selects a remote voice when no local language match exists', () => {
    const { synthesis, callbacks } = setup([
      { lang: 'zh-HK', localService: false },
      { lang: 'en-US', localService: true },
    ]);
    playQuestion('你好', 'zh-HK', callbacks);
    expect(synthesis.speak).not.toHaveBeenCalled();
    expect(callbacks.onNotice).toHaveBeenCalledWith(expect.stringContaining('No local voice'));
    expect(callbacks.onEnd).toHaveBeenCalledOnce();
  });
  it('uses a local voice and prevents old speech events restarting mouth movement after stop', () => {
    const voice = { lang: 'en-GB', localService: true };
    const { synthesis, callbacks } = setup([voice]);
    const stop = playQuestion('Hello', 'en-HK', callbacks);
    const utterance = synthesis.speak.mock.calls[0][0] as SpeechSynthesisUtterance;
    expect(utterance.voice).toBe(voice);
    utterance.onstart?.({} as SpeechSynthesisEvent);
    expect(callbacks.onStart).toHaveBeenCalledOnce();
    stop();
    stop();
    utterance.onstart?.({} as SpeechSynthesisEvent);
    utterance.onend?.({} as SpeechSynthesisEvent);
    expect(synthesis.cancel).toHaveBeenCalledOnce();
    expect(callbacks.onStart).toHaveBeenCalledOnce();
    expect(callbacks.onEnd).toHaveBeenCalledOnce();
    expect(callbacks.onMouth).toHaveBeenLastCalledWith(0);
  });
});
