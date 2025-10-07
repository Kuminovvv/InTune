import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { OverlayState, ServerMessage } from '@/types';

interface AppContextValue {
  overlay: OverlayState;
  startListening: () => Promise<void>;
  stopListening: () => Promise<void>;
  shorten: () => Promise<void>;
  codeHint: () => Promise<void>;
  reindex: (paths: string[]) => Promise<void>;
  config: Record<string, unknown> | null;
  refreshConfig: () => Promise<void>;
  saveConfig: (config: Record<string, unknown>) => Promise<void>;
}

const defaultOverlay: OverlayState = {
  status: null,
  partial: '',
  answer: null,
  lastError: null,
  reindexedDocs: null,
};

const Context = createContext<AppContextValue | undefined>(undefined);

function reduceMessage(state: OverlayState, message: ServerMessage): OverlayState {
  switch (message.type) {
    case 'status':
      return { ...state, status: message };
    case 'partial_transcript':
      return { ...state, partial: message.text };
    case 'answer':
      return { ...state, answer: message, partial: '', lastError: null };
    case 'error':
      return { ...state, lastError: message };
    case 'reindex_done':
      return { ...state, reindexedDocs: message.docs };
    default:
      return state;
  }
}

export const AppProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [overlay, setOverlay] = useState<OverlayState>(defaultOverlay);
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const unsubscribe = window.electronAPI.onMessage((raw) => {
      setOverlay((current) => reduceMessage(current, raw as ServerMessage));
    });
    return unsubscribe;
  }, []);

  const refreshConfig = useCallback(async () => {
    const next = await window.electronAPI.getConfig();
    setConfig(next);
  }, []);

  useEffect(() => {
    void refreshConfig();
  }, [refreshConfig]);

  const startListening = useCallback(async () => {
    await window.electronAPI.startListen();
  }, []);

  const stopListening = useCallback(async () => {
    await window.electronAPI.stopListen();
  }, []);

  const shorten = useCallback(async () => {
    await window.electronAPI.shorten();
  }, []);

  const codeHint = useCallback(async () => {
    await window.electronAPI.codeHint();
  }, []);

  const reindex = useCallback(async (paths: string[]) => {
    await window.electronAPI.reindex(paths);
  }, []);

  const saveConfig = useCallback(
    async (next: Record<string, unknown>) => {
      await window.electronAPI.saveConfig(next);
      await refreshConfig();
    },
    [refreshConfig],
  );

  const value = useMemo<AppContextValue>(
    () => ({ overlay, startListening, stopListening, shorten, codeHint, reindex, config, refreshConfig, saveConfig }),
    [overlay, startListening, stopListening, shorten, codeHint, reindex, config, refreshConfig, saveConfig],
  );

  return <Context.Provider value={value}>{children}</Context.Provider>;
};

export const useAppContext = (): AppContextValue => {
  const ctx = useContext(Context);
  if (!ctx) {
    throw new Error('useAppContext must be used within AppProvider');
  }
  return ctx;
};
