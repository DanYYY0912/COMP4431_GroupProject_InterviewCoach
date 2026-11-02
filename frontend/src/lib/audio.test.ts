import { afterEach, describe, expect, it, vi } from 'vitest';
import { encodeWav, recordMicrophone, visemeOpenness } from './audio';

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
  it('closes the mouth for silence and bounded consonants', () => {
    expect(visemeOpenness(0)).toBe(0);
    expect(visemeOpenness(21)).toBe(0.08);
    expect(visemeOpenness(1)).toBeGreaterThan(0.5);
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
