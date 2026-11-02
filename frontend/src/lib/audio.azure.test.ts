import { afterEach, describe, expect, it, vi } from 'vitest';
import { azureRecognizer } from './audio';
import { api } from './api';

const sdkMock = vi.hoisted(() => ({ close: vi.fn(), start: vi.fn() }));
vi.mock('microsoft-cognitiveservices-speech-sdk', () => ({
  Recognizer: { enableTelemetry: vi.fn() },
  SpeechConfig: { fromAuthorizationToken: () => ({}) },
  AudioConfig: { fromStreamInput: () => ({}) },
  SpeechRecognizer: class {
    close = sdkMock.close;
    startContinuousRecognitionAsync = sdkMock.start;
  },
}));
afterEach(() => vi.restoreAllMocks());
describe('Azure recognition lifecycle', () => {
  it('stops the cloned microphone immediately when aborted during startup', async () => {
    vi.spyOn(api, 'token').mockResolvedValue({
      token: 'test-token',
      region: 'test-region',
      expires_in: 540,
    });
    const stop = vi.fn();
    const stream = { clone: () => ({ getTracks: () => [{ stop }] }) } as unknown as MediaStream;
    const controller = new AbortController();
    const pending = azureRecognizer(stream, 'en-HK', vi.fn(), vi.fn(), controller.signal);
    const rejected = expect(pending).rejects.toThrow('Recording canceled');
    await vi.waitFor(() => expect(sdkMock.start).toHaveBeenCalledOnce());
    controller.abort();
    expect(stop).toHaveBeenCalledOnce();
    expect(sdkMock.close).toHaveBeenCalledOnce();
    await rejected;
  });
});
