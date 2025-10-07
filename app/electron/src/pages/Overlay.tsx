import React from 'react';
import { SparklesIcon, SpeakerWaveIcon, StopIcon, BoltIcon, CodeBracketIcon } from '@heroicons/react/24/outline';
import { useAppContext } from '@/context/AppContext';

const statusLabel: Record<string, string> = {
  ready: 'Готов слушать',
  listening: 'Слушаю…',
  thinking: 'Формирую подсказку',
  reindex: 'Обновляю знания',
};

const OverlayPage: React.FC = () => {
  const { overlay, startListening, stopListening, shorten, codeHint } = useAppContext();
  const currentStatus = overlay.status?.state ?? 'ready';
  const statusText = statusLabel[currentStatus] ?? overlay.status?.msg ?? 'Готов слушать';

  return (
    <div className="p-4 w-full h-full bg-surface/95 text-slate-100 flex flex-col gap-3 select-none">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-primary">
          <SparklesIcon className="h-6 w-6" />
          <span className="font-semibold tracking-wide uppercase text-sm">Interview Copilot</span>
        </div>
        <div className="flex gap-2 text-xs text-slate-400">
          <kbd className="px-2 py-1 bg-slate-800/70 rounded">Ctrl+Space</kbd>
          <span>— показать/скрыть</span>
        </div>
      </header>

      <section className="rounded-lg border border-slate-700 bg-slate-900/60 p-4 shadow-lg shadow-slate-900/50">
        <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">Статус</div>
        <div className="flex items-center gap-2 text-lg font-semibold">
          <SpeakerWaveIcon className="h-5 w-5 text-primary" />
          <span>{statusText}</span>
        </div>
        {overlay.partial && (
          <p className="mt-3 text-sm text-slate-300">Слышу: {overlay.partial}</p>
        )}
        {overlay.answer && (
          <div className="mt-4 border-t border-slate-700 pt-4 text-sm">
            <div className="uppercase text-xs text-slate-400 mb-2">Подсказка</div>
            <p className="font-medium text-slate-100 whitespace-pre-line">{overlay.answer.hint}</p>
          </div>
        )}
        {overlay.lastError && (
          <div className="mt-4 rounded border border-red-500/60 bg-red-500/10 p-3 text-sm text-red-200">
            Ошибка ({overlay.lastError.stage}): {overlay.lastError.msg}
          </div>
        )}
        {overlay.reindexedDocs !== null && (
          <div className="mt-3 text-xs text-slate-400">Переиндексировано документов: {overlay.reindexedDocs}</div>
        )}
      </section>

      <footer className="mt-auto flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void startListening()}
          className="inline-flex items-center gap-2 rounded bg-primary/80 px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-primary"
        >
          <SpeakerWaveIcon className="h-4 w-4" />
          Старт
        </button>
        <button
          type="button"
          onClick={() => void stopListening()}
          className="inline-flex items-center gap-2 rounded border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:bg-slate-800"
        >
          <StopIcon className="h-4 w-4" />
          Стоп
        </button>
        <button
          type="button"
          onClick={() => void shorten()}
          className="inline-flex items-center gap-2 rounded border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:bg-slate-800"
        >
          <BoltIcon className="h-4 w-4" />
          Короче
        </button>
        <button
          type="button"
          onClick={() => void codeHint()}
          className="inline-flex items-center gap-2 rounded border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:bg-slate-800"
        >
          <CodeBracketIcon className="h-4 w-4" />
          Код
        </button>
      </footer>
    </div>
  );
};

export default OverlayPage;
