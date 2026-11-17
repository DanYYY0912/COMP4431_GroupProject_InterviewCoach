import { afterEach, describe, expect, it, vi } from 'vitest';
import { encodeWav, recordMicrophone, playQuestion } from './audio';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

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
  function setup(voices: { name: string; lang: string; localService: boolean }[]) {
    const events = new EventTarget();
    const synthesis = {
      getVoices: vi.fn(() => voices),
      speak: vi.fn(),
      cancel: vi.fn(),
      addEventListener: vi.fn(events.addEventListener.bind(events)),
      removeEventListener: vi.fn(events.removeEventListener.bind(events)),
    };
    vi.stubGlobal('speechSynthesis', synthesis);
    vi.stubGlobal(
      'SpeechSynthesisUtterance',
      class {
        constructor(public text: string) {}
      },
    );
    const callbacks = { onStart: vi.fn(), onEnd: vi.fn(), onNotice: vi.fn(), onViseme: vi.fn() };
    return {
      synthesis,
      callbacks,
      voicesChanged: () => events.dispatchEvent(new Event('voiceschanged')),
    };
  }
  it('never selects a remote voice when no local language match exists', () => {
    vi.useFakeTimers();
    const { synthesis, callbacks } = setup([
      { name: 'Microsoft Danny', lang: 'zh-HK', localService: false },
      { name: 'Alex', lang: 'en-US', localService: true },
    ]);
    playQuestion('你好', 'zh-HK', callbacks);
    vi.advanceTimersByTime(1500);
    expect(synthesis.speak).not.toHaveBeenCalled();
    expect(callbacks.onNotice).toHaveBeenCalledWith(expect.stringMatching(/local.*male.*voice/i));
    expect(callbacks.onEnd).toHaveBeenCalledOnce();
    expect(callbacks.onStart).not.toHaveBeenCalled();
  });
  it('uses a local voice and ignores old speech callbacks after stop', () => {
    const voice = { name: 'Daniel', lang: 'en-GB', localService: true };
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
    expect(callbacks.onViseme).toHaveBeenLastCalledWith(0);
  });

  it('waits for local voices to load and releases its listener once playback is requested', () => {
    vi.useFakeTimers();
    const { synthesis, callbacks, voicesChanged } = setup([]);
    playQuestion('Hello', 'en-HK', callbacks);
    expect(synthesis.speak).not.toHaveBeenCalled();
    synthesis.getVoices.mockReturnValue([{ name: 'Daniel', lang: 'en-GB', localService: true }]);
    voicesChanged();
    voicesChanged();
    expect(synthesis.speak).toHaveBeenCalledOnce();
    expect(callbacks.onStart).not.toHaveBeenCalled();
    expect(synthesis.removeEventListener).toHaveBeenCalled();
    const utterance = synthesis.speak.mock.calls[0][0] as SpeechSynthesisUtterance;
    utterance.onstart?.({} as SpeechSynthesisEvent);
    vi.advanceTimersByTime(5000);
    expect(callbacks.onStart).toHaveBeenCalledOnce();
    expect(callbacks.onNotice).not.toHaveBeenCalled();
  });

  it('never starts a late voice callback after cancellation', () => {
    vi.useFakeTimers();
    const { synthesis, callbacks, voicesChanged } = setup([]);
    const stop = playQuestion('Hello', 'en-HK', callbacks);
    stop();
    synthesis.getVoices.mockReturnValue([{ name: 'Daniel', lang: 'en-GB', localService: true }]);
    voicesChanged();
    vi.advanceTimersByTime(10000);
    expect(synthesis.speak).not.toHaveBeenCalled();
    expect(callbacks.onNotice).not.toHaveBeenCalled();
    expect(callbacks.onStart).not.toHaveBeenCalled();
    expect(callbacks.onEnd).toHaveBeenCalledOnce();
  });

  it('provides approximate boundary cues only during real speech and resets on completion', () => {
    const { synthesis, callbacks } = setup([{ name: 'Daniel', lang: 'en-GB', localService: true }]);
    playQuestion('Map apple', 'en-HK', callbacks);
    const utterance = synthesis.speak.mock.calls[0][0] as SpeechSynthesisUtterance;
    utterance.onboundary?.({ charIndex: 4, name: 'word' } as SpeechSynthesisEvent);
    expect(callbacks.onViseme).not.toHaveBeenCalled();
    utterance.onstart?.({} as SpeechSynthesisEvent);
    expect(callbacks.onViseme).toHaveBeenLastCalledWith(0.65);
    utterance.onboundary?.({ charIndex: 0, name: 'word' } as SpeechSynthesisEvent);
    expect(callbacks.onViseme.mock.lastCall?.[0]).toBeLessThan(0.2);
    utterance.onboundary?.({ charIndex: 4, name: 'word' } as SpeechSynthesisEvent);
    expect(callbacks.onViseme.mock.lastCall?.[0]).toBeGreaterThan(0.8);
    utterance.onend?.({} as SpeechSynthesisEvent);
    expect(callbacks.onViseme).toHaveBeenLastCalledWith(0);
    utterance.onboundary?.({ charIndex: 4, name: 'word' } as SpeechSynthesisEvent);
    expect(callbacks.onViseme).toHaveBeenLastCalledWith(0);
  });

  it('reports blocked or silent playback without pretending speech started', () => {
    vi.useFakeTimers();
    const { synthesis, callbacks } = setup([{ name: 'Daniel', lang: 'en-GB', localService: true }]);
    playQuestion('Hello', 'en-HK', callbacks);
    vi.advanceTimersByTime(4000);
    expect(callbacks.onStart).not.toHaveBeenCalled();
    expect(callbacks.onNotice).toHaveBeenCalledWith(expect.stringContaining('Read question'));
    expect(callbacks.onEnd).toHaveBeenCalledOnce();
    expect(callbacks.onViseme).toHaveBeenLastCalledWith(0);
    expect(synthesis.cancel).toHaveBeenCalledOnce();
  });

  it('explains an autoplay rejection and ignores subsequent browser callbacks', () => {
    vi.useFakeTimers();
    const { synthesis, callbacks } = setup([{ name: 'Daniel', lang: 'en-GB', localService: true }]);
    playQuestion('Hello', 'en-HK', callbacks);
    const utterance = synthesis.speak.mock.calls[0][0] as SpeechSynthesisUtterance;
    utterance.onerror?.({ error: 'not-allowed' } as SpeechSynthesisErrorEvent);
    utterance.onstart?.({} as SpeechSynthesisEvent);
    vi.advanceTimersByTime(5000);
    expect(callbacks.onStart).not.toHaveBeenCalled();
    expect(callbacks.onNotice).toHaveBeenCalledExactlyOnceWith(
      expect.stringContaining('browser blocked audio'),
    );
    expect(callbacks.onEnd).toHaveBeenCalledOnce();
    expect(callbacks.onViseme).toHaveBeenLastCalledWith(0);
  });

  it('selects a known male English voice even when a female voice is listed first', () => {
    const male = { name: 'Daniel', lang: 'en-GB', localService: true };
    const { synthesis } = setup([{ name: 'Samantha', lang: 'en-HK', localService: true }, male]);
    playQuestion('Tell me about your project.', 'en-HK', {
      onStart: vi.fn(),
      onEnd: vi.fn(),
      onNotice: vi.fn(),
    });
    const utterance = synthesis.speak.mock.calls[0][0] as SpeechSynthesisUtterance;
    expect(utterance.voice).toBe(male);
    expect(utterance.lang).toBe('en-GB');
  });

  it.each(['Microsoft Danny', 'Microsoft WanLung'])(
    'selects local male Cantonese voice %s over Sinji',
    (name) => {
      const male = { name, lang: 'zh-HK', localService: true };
      const { synthesis, callbacks } = setup([
        { name: 'Sinji', lang: 'zh-HK', localService: true },
        male,
      ]);
      playQuestion('可唔可以講下你嘅專題？', 'zh-HK', callbacks);
      const utterance = synthesis.speak.mock.calls[0][0] as SpeechSynthesisUtterance;
      expect(utterance.voice).toBe(male);
      expect(callbacks.onNotice).not.toHaveBeenCalled();
    },
  );

  it('accepts a male Cantonese voice labelled with a yue locale', () => {
    const male = { name: 'Microsoft Danny', lang: 'yue-HK', localService: true };
    const { synthesis, callbacks } = setup([male]);
    playQuestion('你好', 'zh-HK', callbacks);
    expect((synthesis.speak.mock.calls[0][0] as SpeechSynthesisUtterance).voice).toBe(male);
  });

  it.each(['Samantha', 'Unidentified system voice', 'Female voice'])(
    'does not silently use %s for Jamie when no known male voice exists',
    (name) => {
      vi.useFakeTimers();
      const { synthesis, callbacks } = setup([{ name, lang: 'en-GB', localService: true }]);
      playQuestion('Tell me about your project.', 'en-HK', callbacks);
      vi.advanceTimersByTime(1500);
      expect(synthesis.speak).not.toHaveBeenCalled();
      expect(callbacks.onNotice).toHaveBeenCalledWith(expect.stringMatching(/local.*male.*voice/i));
      expect(callbacks.onStart).not.toHaveBeenCalled();
      expect(callbacks.onEnd).toHaveBeenCalledOnce();
    },
  );

  it('never substitutes Mandarin or a remote Cantonese voice for a missing local male Cantonese voice', () => {
    vi.useFakeTimers();
    const { synthesis, callbacks } = setup([
      { name: 'Microsoft Yunxi', lang: 'zh-CN', localService: true },
      { name: 'Sinji', lang: 'zh-HK', localService: true },
      { name: 'Microsoft Danny', lang: 'zh-HK', localService: false },
    ]);
    playQuestion('你好', 'zh-HK', callbacks);
    vi.advanceTimersByTime(1500);
    expect(synthesis.speak).not.toHaveBeenCalled();
    expect(callbacks.onNotice).toHaveBeenCalledWith(expect.stringMatching(/local.*male.*voice/i));
    expect(callbacks.onEnd).toHaveBeenCalledOnce();
  });
});
