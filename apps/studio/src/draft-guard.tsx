import { useEffect, useRef, useState } from 'react';
import type { Lang } from './types';

type Action = () => void | Promise<unknown>;

export function useDraftGuard(dirty: boolean, save: () => Promise<boolean>, status: string, lang: Lang) {
  const [pending, setPending] = useState<Action | null>(null);
  const [working, setWorking] = useState(false);
  const [failed, setFailed] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const zh = lang === 'zh';

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  useEffect(() => {
    if (pending && !dialog.current?.open) dialog.current?.showModal();
    if (!pending && dialog.current?.open) dialog.current?.close();
  }, [pending]);

  const guard = (action: Action) => {
    if (working || pending) return;
    if (dirty) { setFailed(false); setPending(() => action); }
    else void action();
  };
  const proceed = async (persist: boolean) => {
    if (!pending || working) return;
    setWorking(true);
    try {
      if (persist && !await save()) { setFailed(true); return; }
      const action = pending;
      await action();
      setPending(null);
    } finally { setWorking(false); }
  };
  const prompt = <dialog ref={dialog} className="draft-dialog" aria-labelledby="draft-title"
    aria-describedby="draft-description" onCancel={event => { event.preventDefault(); if (!working) setPending(null); }}>
    <h2 id="draft-title">{zh ? '保留当前修改？' : 'Keep your changes?'}</h2>
    <p id="draft-description">{zh ? '当前项目有未保存的修改。可以保存后继续，或留在这里编辑。' : 'This project has unsaved changes. Save before continuing, or keep editing here.'}</p>
    {failed && <p role="alert" className="draft-error">{status}</p>}
    <div className="dialog-actions">
      <button autoFocus disabled={working} onClick={() => setPending(null)}>{zh ? '继续编辑' : 'Keep editing'}</button>
      <button disabled={working} onClick={() => proceed(false)}>{zh ? '放弃修改' : 'Discard changes'}</button>
      <button className="primary" disabled={working} onClick={() => proceed(true)}>{working ? (zh ? '处理中…' : 'Working…') : (zh ? '保存并继续' : 'Save and continue')}</button>
    </div>
  </dialog>;
  return { guard, prompt };
}
