import {useEffect, useState, useRef, type ReactNode, type CSSProperties} from 'react';
import {Icon} from './studio-ui';
import type {Lang} from './types';

const defaults = {sidebar:240, inspector:370, results:240, sidebarVisible:true, inspectorVisible:true, resultsVisible:true};
type Layout = typeof defaults;
const key = 'evosprig.workspace-layout.v1';
export function useWorkspaceLayout() {
  const [layout,setLayout] = useState<Layout>(()=>{
    try {
      const saved=JSON.parse(localStorage.getItem(key)??'{}');
      return Object.fromEntries(Object.entries(defaults).map(([name,value])=>[name,
        typeof saved[name]===typeof value && (typeof value!=='number'||Number.isFinite(saved[name]))?saved[name]:value])) as Layout;
    } catch { return {...defaults}; }
  });
  const [viewport,setViewport]=useState({width:window.innerWidth,height:window.innerHeight});
  useEffect(()=>{const resize=()=>setViewport({width:window.innerWidth,height:window.innerHeight});window.addEventListener('resize',resize);return()=>window.removeEventListener('resize',resize);},[]);
  useEffect(()=>{const timer=setTimeout(()=>{try{localStorage.setItem(key,JSON.stringify(layout));}catch{/* Browser storage may be unavailable. */}},150);return()=>clearTimeout(timer);},[layout]);
  const sidebarMax=Math.floor(Math.max(200,Math.min(400,viewport.width*.26)));
  const sidebar=Math.max(200,Math.min(sidebarMax,layout.sidebar));
  const inspectorMax=Math.floor(Math.max(280,Math.min(640,(viewport.width-(layout.sidebarVisible?sidebar:0))*.55)));
  const inspector=Math.max(280,Math.min(inspectorMax,layout.inspector));
  const resultsMax=Math.floor(Math.max(150,Math.min(640,viewport.height*.5)));
  const results=Math.max(150,Math.min(resultsMax,layout.results));
  return {layout,setLayout,reset:()=>setLayout({...defaults}),sidebarMax,inspectorMax,resultsMax,sidebar,inspector,results,
    style:{'--sidebar-width':`${sidebar}px`,'--inspector-width':`${inspector}px`,'--results-height':`${results}px`} as CSSProperties};
}

export function ResizeHandle({label,controls,axis='x',value,min,max,reverse=false,onChange,onReset,className=''}:{label:string;controls:string;axis?:'x'|'y';value:number;min:number;max:number;reverse?:boolean;onChange:(value:number)=>void;onReset:()=>void;className?:string}) {
  const drag=useRef<{position:number;value:number}|null>(null);
  const [dragging,setDragging]=useState(false);
  const clamp=(next:number)=>onChange(Math.round(Math.max(min,Math.min(max,next))));
  return <div className={`resize-handle resize-${axis} ${className}${dragging?' is-dragging':''}`} role="separator" tabIndex={0}
    aria-label={label} aria-controls={controls} aria-orientation={axis==='x'?'vertical':'horizontal'} aria-valuemin={min} aria-valuemax={Math.floor(max)} aria-valuenow={Math.round(value)}
    title={label} onDoubleClick={onReset}
    onPointerDown={e=>{if(e.button!==0)return;e.preventDefault();e.currentTarget.setPointerCapture(e.pointerId);drag.current={position:axis==='x'?e.clientX:e.clientY,value};setDragging(true);}}
    onPointerMove={e=>{if(drag.current)clamp(drag.current.value+((axis==='x'?e.clientX:e.clientY)-drag.current.position)*(reverse?-1:1));}}
    onPointerUp={e=>{drag.current=null;setDragging(false);if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);}}
    onLostPointerCapture={()=>{drag.current=null;setDragging(false);}}
    onPointerCancel={()=>{drag.current=null;setDragging(false);}}
    onKeyDown={e=>{const direction=axis==='x'?{ArrowLeft:-1,ArrowRight:1}:{ArrowUp:-1,ArrowDown:1};const delta=direction[e.key as keyof typeof direction];if(delta){e.preventDefault();clamp(value+delta*(reverse?-1:1)*(e.shiftKey?40:10));}else if(e.key==='Home'||e.key==='End'){e.preventDefault();clamp(e.key==='Home'?min:max);}else if(e.key==='Enter'){e.preventDefault();onReset();}}}><span/></div>;
}

export function LayoutMenu({lang,layout,onChange,onReset}:{lang:Lang;layout:Layout;onChange:(value:Layout)=>void;onReset:()=>void}) {
  const ref=useRef<HTMLDetailsElement>(null);
  useEffect(()=>{const outside=(e:PointerEvent)=>{if(ref.current&&!ref.current.contains(e.target as Node))ref.current.open=false;};document.addEventListener('pointerdown',outside);return()=>document.removeEventListener('pointerdown',outside);},[]);
  return <details ref={ref} className="layout-menu" onKeyDown={e=>{if(e.key==='Escape'&&ref.current){ref.current.open=false;ref.current.querySelector('summary')?.focus();}}}>
    <summary aria-label={lang==='zh'?'工作区布局':'Workspace layout'} title={lang==='zh'?'工作区布局':'Workspace layout'}><Icon name="layers"/></summary>
    <div className="layout-popover"><strong>{lang==='zh'?'显示面板':'Show panels'}</strong>
      {([['sidebarVisible','Project sidebar','项目栏'],['inspectorVisible','Node inspector','节点设置'],['resultsVisible','Run panel','运行面板']] as const).map(([key,en,zh])=><label className="check" key={key}><input type="checkbox" checked={layout[key]} onChange={e=>onChange({...layout,[key]:e.target.checked})}/>{lang==='zh'?zh:en}</label>)}
      <button onClick={()=>{onReset();if(ref.current)ref.current.open=false;}}><Icon name="refresh"/>{lang==='zh'?'恢复默认布局':'Reset layout'}</button>
      <small>{lang==='zh'?'拖动分隔条调整大小；双击恢复。':'Drag dividers to resize. Double-click to reset.'}</small>
    </div>
  </details>;
}

export function WorkspaceDialog({label,onClose,children}:{label:string;onClose:()=>void;children:ReactNode}) {
  const ref=useRef<HTMLDialogElement>(null);
  const opener=useRef<HTMLElement|null>(null);
  useEffect(()=>{
    const dialog=ref.current!;
    if(!opener.current && document.activeElement instanceof HTMLElement)opener.current=document.activeElement;
    dialog.showModal();
    return()=>{
      dialog.close();
      queueMicrotask(()=>{
        if(dialog.isConnected && dialog.open)return;
        const target=opener.current;
        if(target?.isConnected && target.getClientRects().length)target.focus();
        else document.querySelector<HTMLButtonElement>('button[aria-controls="project-navigation"]')?.focus();
      });
    };
  },[]);
  return <dialog ref={ref} className="workspace-dialog" aria-label={label} onCancel={event=>{event.preventDefault();onClose();}}>{children}</dialog>;
}
