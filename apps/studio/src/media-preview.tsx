import { useMemo, useState } from 'react';
import type { Lang } from './types';

type Asset = { uri: string; kind: 'image' | 'video'; label: string; poster?:string };

function safeImage(uri:unknown):uri is string {
  if(typeof uri!=='string')return false;
  if(uri.length<2*1024*1024&&/^data:image\/(png|jpeg|webp|gif);base64,[A-Za-z0-9+/]+=*$/.test(uri))return true;
  try{const url=new URL(uri);return !url.username&&!url.password&&(url.protocol==='https:'||(url.protocol==='http:'&&['localhost','127.0.0.1','[::1]'].includes(url.hostname)));}catch{return false;}
}

function mediaAssets(value: unknown): Asset[] {
  const assets: Asset[] = [];
  const seen = new Set<string>();
  let visited = 0;
  function visit(item: unknown, path: string[], depth: number, poster?:unknown) {
    if (++visited > 1200 || depth > 16 || assets.length >= 12 || !item || typeof item !== 'object') return;
    const entry = item as Record<string, unknown>;
    const kind = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(String(entry.media_type)) ? 'image'
      : ['video/mp4', 'video/webm'].includes(String(entry.media_type)) ? 'video' : null;
    if (kind && typeof entry.uri === 'string' && !seen.has(entry.uri)) {
      let safe = false;
      try {
        const url = new URL(entry.uri);
        safe = !url.username && !url.password && (url.protocol === 'https:' ||
          (url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)));
        if (kind === 'image' && entry.uri.length < 2 * 1024 * 1024)
          safe ||= /^data:image\/(png|jpeg|webp|gif);base64,[A-Za-z0-9+/]+=*$/.test(entry.uri);
      } catch { /* An asset must have an absolute media URL. */ }
      if (safe) {
        seen.add(entry.uri);
        assets.push({ uri: entry.uri, kind, label: path.join(' / ') || 'Media', ...(kind==='video'&&safeImage(poster)?{poster}:{}) });
      }
      return;
    }
    for (const [name, child] of Object.entries(item)) {
      if (visited >= 1200 || assets.length >= 12) break;
      const frame=name==='tail'?entry.last_frame:entry.frame??entry.first_frame;
      const preview=frame&&typeof frame==='object'?(frame as Record<string,unknown>).uri:undefined;
      visit(child, [...path, name], depth + 1, preview);
    }
  }
  visit(value, [], 0);
  return assets;
}

export function MediaPreview({ value, lang }: { value: unknown; lang: Lang }) {
  const assets = useMemo(() => mediaAssets(value), [value]);
  const [visible, setVisible] = useState(false);
  if (!assets.length) return null;
  return <section className="media-preview" aria-label={lang === 'zh' ? '媒体资产' : 'Media assets'}>
    <button aria-expanded={visible} onClick={() => setVisible(!visible)}>
      {lang === 'zh' ? (visible ? '收起媒体' : '查看媒体') : (visible ? 'Hide media' : 'Show media')} · {assets.length}
    </button>
    {visible && <div className="media-grid">{assets.map(asset => <figure key={asset.uri}>
      {asset.kind === 'image'
        ? <img src={asset.uri} alt={asset.label} loading="lazy" referrerPolicy="no-referrer" />
        : <video src={asset.uri} poster={asset.poster} controls preload="none" playsInline />}
      <figcaption><span>{asset.label}</span><a href={asset.uri} target="_blank" rel="noopener noreferrer">
        {lang === 'zh' ? '打开原文件' : 'Open asset'}
      </a></figcaption>
    </figure>)}</div>}
  </section>;
}
