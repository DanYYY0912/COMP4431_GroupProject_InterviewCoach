import { useEffect, useRef, useState } from 'react';
import { api, errorMessage } from './api';
import { sessionSchema } from './types';
import type { Answer, ControlAction, Session } from './types';

export function useLiveSession(id: string) {
  const [session, setSession] = useState<Session | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [state, setState] = useState('ready');
  const [streamText, setStreamText] = useState('');
  const socket = useRef<WebSocket | null>(null);
  const pending = useRef(false);
  const mutationVersion = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    let active = true;
    let ws: WebSocket | null = null;
    api
      .session(id)
      .then((data) => {
        if (!active) return;
        setSession(data);
        setState(data.state);
      })
      .catch((e) => {
        if (active) setError(errorMessage(e));
      });
    if (typeof WebSocket !== 'undefined') {
      ws = new WebSocket(
        `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/sessions/${encodeURIComponent(id)}/live`,
      );
      socket.current = ws;
      ws.onmessage = (event) => {
        if (!active) return;
        try {
          const message = JSON.parse(event.data);
          if (message.version !== 1) return;
          if (message.type === 'session') {
            const data = sessionSchema.parse(message.payload);
            setSession(data);
            setState(data.state);
            setBusy(false);
            pending.current = false;
            setStreamText('');
            if (timer.current) clearTimeout(timer.current);
          } else if (message.type === 'state' && typeof message.payload?.state === 'string')
            setState(message.payload.state);
          else if (message.type === 'text_delta' && typeof message.payload?.text === 'string')
            setStreamText((current) => current + message.payload.text);
          else if (message.type === 'error') {
            setError(String(message.payload?.message || 'The coach could not respond. Try again.'));
            setBusy(false);
            pending.current = false;
            if (timer.current) clearTimeout(timer.current);
          }
        } catch (e) {
          setError(errorMessage(e));
          setBusy(false);
          pending.current = false;
        }
      };
      ws.onclose = () => {
        if (active && pending.current) {
          setError('Connection interrupted. Checking the saved session before you continue.');
          void api
            .session(id)
            .then(setSession)
            .catch((e) => setError(errorMessage(e)))
            .finally(() => {
              if (active) {
                setBusy(false);
                pending.current = false;
              }
            });
        }
      };
    }
    return () => {
      active = false;
      if (timer.current) clearTimeout(timer.current);
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
      socket.current = null;
    };
  }, [id]);
  async function send(type: 'answer' | 'control', payload: Answer | { action: ControlAction }) {
    const interrupts =
      type === 'control' &&
      ['pause', 'cancel', 'end'].includes((payload as { action: ControlAction }).action);
    if (pending.current && !interrupts) return;
    const version = ++mutationVersion.current;
    setError('');
    setBusy(true);
    pending.current = true;
    setStreamText('');
    if (typeof WebSocket !== 'undefined' && socket.current?.readyState === WebSocket.OPEN) {
      socket.current.send(JSON.stringify({ version: 1, type, payload }));
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        if (!pending.current) return;
        socket.current?.close();
      }, 90000);
      return;
    }
    try {
      const data =
        type === 'answer'
          ? await api.answer(id, payload as Answer)
          : await api.control(id, (payload as { action: ControlAction }).action);
      if (version === mutationVersion.current) {
        setSession(data);
        setState(data.state);
      }
    } catch (e) {
      if (version === mutationVersion.current) setError(errorMessage(e));
    } finally {
      if (version === mutationVersion.current) {
        setBusy(false);
        pending.current = false;
      }
    }
  }
  return {
    session,
    busy,
    error,
    setError,
    state,
    streamText,
    answer: (answer: Answer) => send('answer', answer),
    control: (action: ControlAction) => send('control', { action }),
  };
}
