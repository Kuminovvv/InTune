import React, { useEffect, useMemo, useState } from 'react';
import { FolderPlusIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import { useAppContext } from '@/context/AppContext';

const defaultConfig: Record<string, unknown> = {
  language: 'ru',
  vad: { aggressiveness: 2, silence_sec: 0.8 },
  audio: { device_name: 'System Default', auto_reconnect: true },
  stt: { model: 'medium', use_gpu: true },
  ollama: { model: 'qwen2.5:7b-instruct', timeout_sec: 120 },
  overlay: { x: 20, y: 20, width: 640, height: 180, opacity: 1 },
  rag: { top_k: 5, db_path: './data/knowledge.db', embed_model: 'bge-small-ru-en' },
  profile: 'frontend',
  logging: { level: 'info' },
};

function updateNestedConfig(source: Record<string, unknown>, path: string[], value: unknown): Record<string, unknown> {
  if (path.length === 0) {
    return source;
  }
  const [head, ...rest] = path;
  return {
    ...source,
    [head]: rest.length === 0
      ? value
      : updateNestedConfig((source[head] as Record<string, unknown>) ?? {}, rest, value),
  };
}

const SettingsPage: React.FC = () => {
  const { config, saveConfig, reindex } = useAppContext();
  const [form, setForm] = useState<Record<string, unknown>>(defaultConfig);
  const [pathsInput, setPathsInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [reindexing, setReindexing] = useState(false);

  useEffect(() => {
    if (config) {
      setForm(config);
    }
  }, [config]);

  const formAudio = useMemo(() => (form.audio as Record<string, unknown>) ?? {}, [form]);
  const formVAD = useMemo(() => (form.vad as Record<string, unknown>) ?? {}, [form]);
  const formOverlay = useMemo(() => (form.overlay as Record<string, unknown>) ?? {}, [form]);
  const formRag = useMemo(() => (form.rag as Record<string, unknown>) ?? {}, [form]);
  const formSTT = useMemo(() => (form.stt as Record<string, unknown>) ?? {}, [form]);
  const formOllama = useMemo(() => (form.ollama as Record<string, unknown>) ?? {}, [form]);

  const handleField = (path: string[], value: unknown) => {
    setForm((prev) => updateNestedConfig(prev, path, value));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    try {
      await saveConfig(form);
    } finally {
      setSaving(false);
    }
  };

  const handleReindex = async () => {
    if (!pathsInput.trim()) {
      return;
    }
    setReindexing(true);
    try {
      const paths = pathsInput
        .split(/\n|;/)
        .map((item) => item.trim())
        .filter(Boolean);
      await reindex(paths);
      setPathsInput('');
    } finally {
      setReindexing(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface text-slate-100 p-6">
      <h1 className="text-2xl font-semibold mb-6">Настройки</h1>
      <form onSubmit={handleSubmit} className="space-y-8">
        <section className="rounded-lg border border-slate-700 bg-slate-900/60 p-5">
          <h2 className="text-lg font-semibold mb-4">Речь и аудио</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-300">Язык распознавания</span>
              <select
                value={(form.language as string) ?? 'auto'}
                onChange={(e) => handleField(['language'], e.target.value)}
                className="rounded border border-slate-600 bg-slate-950 px-3 py-2"
              >
                <option value="ru">Русский</option>
                <option value="en">English</option>
                <option value="auto">Auto</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-300">Loopback устройство</span>
              <input
                type="text"
                value={(formAudio.device_name as string) ?? ''}
                onChange={(e) => handleField(['audio', 'device_name'], e.target.value)}
                className="rounded border border-slate-600 bg-slate-950 px-3 py-2"
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={Boolean(formAudio.auto_reconnect)}
                onChange={(e) => handleField(['audio', 'auto_reconnect'], e.target.checked)}
                className="h-4 w-4 rounded border-slate-600 bg-slate-950"
              />
              <span className="text-slate-300">Автопереподключение</span>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-300">VAD aggressiveness (0-3)</span>
              <input
                type="number"
                min={0}
                max={3}
                value={(formVAD.aggressiveness as number) ?? 2}
                onChange={(e) => handleField(['vad', 'aggressiveness'], Number(e.target.value))}
                className="rounded border border-slate-600 bg-slate-950 px-3 py-2"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-300">VAD пауза (сек)</span>
              <input
                type="number"
                min={0}
                step={0.1}
                value={(formVAD.silence_sec as number) ?? 0.8}
                onChange={(e) => handleField(['vad', 'silence_sec'], Number(e.target.value))}
                className="rounded border border-slate-600 bg-slate-950 px-3 py-2"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-300">Модель STT</span>
              <input
                type="text"
                value={(formSTT.model as string) ?? ''}
                onChange={(e) => handleField(['stt', 'model'], e.target.value)}
                className="rounded border border-slate-600 bg-slate-950 px-3 py-2"
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={Boolean(formSTT.use_gpu)}
                onChange={(e) => handleField(['stt', 'use_gpu'], e.target.checked)}
                className="h-4 w-4 rounded border-slate-600 bg-slate-950"
              />
              <span className="text-slate-300">Использовать GPU</span>
            </label>
          </div>
        </section>

        <section className="rounded-lg border border-slate-700 bg-slate-900/60 p-5">
          <h2 className="text-lg font-semibold mb-4">LLM и Overlay</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-300">Модель Ollama</span>
              <input
                type="text"
                value={(formOllama.model as string) ?? ''}
                onChange={(e) => handleField(['ollama', 'model'], e.target.value)}
                className="rounded border border-slate-600 bg-slate-950 px-3 py-2"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-300">Таймаут Ollama (сек)</span>
              <input
                type="number"
                min={10}
                value={(formOllama.timeout_sec as number) ?? 120}
                onChange={(e) => handleField(['ollama', 'timeout_sec'], Number(e.target.value))}
                className="rounded border border-slate-600 bg-slate-950 px-3 py-2"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-300">Профиль</span>
              <select
                value={(form.profile as string) ?? 'frontend'}
                onChange={(e) => handleField(['profile'], e.target.value)}
                className="rounded border border-slate-600 bg-slate-950 px-3 py-2"
              >
                <option value="frontend">Frontend</option>
                <option value="backend">Backend</option>
                <option value="system_design">System Design</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-300">Overlay ширина</span>
              <input
                type="number"
                value={(formOverlay.width as number) ?? 640}
                onChange={(e) => handleField(['overlay', 'width'], Number(e.target.value))}
                className="rounded border border-slate-600 bg-slate-950 px-3 py-2"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-300">Overlay высота</span>
              <input
                type="number"
                value={(formOverlay.height as number) ?? 180}
                onChange={(e) => handleField(['overlay', 'height'], Number(e.target.value))}
                className="rounded border border-slate-600 bg-slate-950 px-3 py-2"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-300">Overlay прозрачность</span>
              <input
                type="number"
                min={0.1}
                max={1}
                step={0.1}
                value={(formOverlay.opacity as number) ?? 1}
                onChange={(e) => handleField(['overlay', 'opacity'], Number(e.target.value))}
                className="rounded border border-slate-600 bg-slate-950 px-3 py-2"
              />
            </label>
          </div>
        </section>

        <section className="rounded-lg border border-slate-700 bg-slate-900/60 p-5">
          <h2 className="text-lg font-semibold mb-4">База знаний</h2>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm md:col-span-2">
              <span className="text-slate-300">Пути для импорта (по одному на строку или через ;)</span>
              <textarea
                value={pathsInput}
                onChange={(e) => setPathsInput(e.target.value)}
                rows={3}
                placeholder="C:\\Users\\me\\resume.pdf\nC:\\Projects\\portfolio"
                className="rounded border border-slate-600 bg-slate-950 px-3 py-2"
              />
            </label>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => void handleReindex()}
                disabled={reindexing}
                className="inline-flex items-center gap-2 rounded bg-primary/80 px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-primary disabled:opacity-60"
              >
                <FolderPlusIcon className="h-4 w-4" />
                Импорт / Reindex
              </button>
              {reindexing && <ArrowPathIcon className="h-5 w-5 animate-spin text-primary" />}
            </div>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-slate-300">Top-K</span>
              <input
                type="number"
                min={1}
                value={(formRag.top_k as number) ?? 5}
                onChange={(e) => handleField(['rag', 'top_k'], Number(e.target.value))}
                className="rounded border border-slate-600 bg-slate-950 px-3 py-2"
              />
            </label>
          </div>
        </section>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 rounded bg-primary/80 px-6 py-2 text-sm font-semibold text-slate-900 transition hover:bg-primary disabled:opacity-60"
          >
            Сохранить
          </button>
        </div>
      </form>
    </div>
  );
};

export default SettingsPage;
