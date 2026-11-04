import type { ElkNode } from 'elkjs/lib/elk-api';
import { MarkerType, type Edge, type Node } from '@xyflow/react';
import type { Graph, NodeSpec, Spec, Lang } from './types';
import {routeAround} from './routing';

export type Group = {id:string;label:string;members:string[];collapsed:boolean;direction?:'RIGHT'|'DOWN'};
export type CanvasState = {groups:Record<string,Group[]>};
export type FlowNode = Node<{label:string;config:NodeSpec}>;
export const pathKey=(path:string[])=>['graph',...path].join('/');
export function graphAt(spec:Spec,path:string[]):Graph {
  let graph=spec.graph;
  for(let i=0;i<path.length;) {
    const node=graph.nodes[path[i++]];const field=path[i++];
    graph=field==='body'?node.body!:node.branches![path[i++]];
  }
  return graph;
}
export function withGraph(spec:Spec,path:string[],graph:Graph):Spec {
  const next=structuredClone(spec);
  if(!path.length){next.graph=graph;return next;}
  const parentPath=path.slice(0,path.at(-2)==='branches'?-3:-2);
  const parent=graphAt(next,parentPath);const tail=path.slice(parentPath.length);const node=parent.nodes[tail[0]];
  if(tail[1]==='body')node.body=graph;else node.branches![tail[2]]=graph;
  return next;
}
export function childGraphs(node:NodeSpec):{label:string;path:string[]}[] {
  return node.body?[{label:'body',path:['body']}]:Object.keys(node.branches??{}).map(name=>({label:name,path:['branches',name]}));
}
export const layoutKey=(path:string[],id:string)=>path.length?pathKey(path)+'/'+id:id;
export function graphEdges(graph:Graph):Edge[] {return graph.edges.map((edge,index)=>({
  ...edge,id:`${edge.source}--${edge.target}--${index}`,type:'smoothstep',sourceHandle:typeof edge.when==='boolean'?String(edge.when):undefined,
  label:typeof edge.when==='boolean'?String(edge.when):undefined,data:{when:edge.when},markerEnd:{type:MarkerType.ArrowClosed,width:15,height:15},pathOptions:{borderRadius:12},
}));}
export function nodeSize(config:NodeSpec) {
  if(config.type==='join')return {width:148,height:64};
  if(config.type==='transform')return {width:224,height:98};
  if(config.type==='condition')return {width:244,height:128};
  if(config.type==='tool')return {width:256,height:112};
  if(config.type==='agent')return {width:302,height:166+(config.skills?.length?28:0)+(config.tools?.length?24:0)};
  if(config.body||Object.keys(config.branches??{}).length)return {width:280,height:170};
  if(config.type==='human')return {width:260,height:140};
  return {width:280,height:config.skills?.length?190:154};
}
export function leaves(id:string,groups:Group[]):string[] {
  const group=groups.find(x=>x.id===id);return group?group.members.flatMap(m=>leaves(m,groups)):[id];
}
export function cleanGroups(groups:Group[],nodeIds:string[]):Group[] {
  let next=groups.map(x=>({...x,members:[...x.members]}));
  for(let i=0;i<=groups.length;i++) {
    const valid=new Set([...nodeIds,...next.map(x=>x.id)]);
    next=next.map(x=>({...x,members:x.members.filter(m=>valid.has(m))})).filter(x=>x.members.length>0);
  }
  return next;
}
export function canvasView(nodes:FlowNode[],edges:Edge[],groups:Group[],lang:Lang,onToggle:(id:string)=>void,onOpen:(id:string,path:string[])=>void) {
  const groupIndex=new Map(groups.map(g=>[g.id,g]));
  const parents=new Map(groups.flatMap(g=>g.members.map(id=>[id,g.id] as const)));
  const representative=(id:string)=>{let visible=id;let parent=parents.get(id);while(parent){if(groupIndex.get(parent)?.collapsed)visible=parent;parent=parents.get(parent);}return visible;};
  const boxes=new Map<string,{x:number;y:number;width:number;height:number}>();
  for(const node of nodes)boxes.set(node.id,{...node.position,...nodeSize(node.data.config)});
  const box=(id:string):{x:number;y:number;width:number;height:number}=>{
    if(boxes.has(id))return boxes.get(id)!;
    const group=groups.find(g=>g.id===id)!;const items=group.members.map(box);
    const x=Math.min(...items.map(p=>p.x))-24,y=Math.min(...items.map(p=>p.y))-72;
    const width=Math.max(...items.map(p=>p.x+p.width))-x+24,height=Math.max(...items.map(p=>p.y+p.height))-y+24;
    const result={x,y,width:group.collapsed?280:Math.max(280,width),height:group.collapsed?112:height};boxes.set(id,result);return result;
  };
  const groupNodes:Node[]=groups.filter(g=>representative(g.id)===g.id).map(g=>{
    const b=box(g.id);return {id:g.id,type:'groupCard',position:{x:b.x,y:b.y},width:b.width,height:b.height,measured:{width:b.width,height:b.height},style:{width:b.width,height:b.height,pointerEvents:g.collapsed?'all':'none'},zIndex:g.collapsed?3:0,
      data:{group:g,count:leaves(g.id,groups).length,lang,direction:groupIndex.get(parents.get(g.id)??'')?.direction??'RIGHT',onToggle:()=>onToggle(g.id)},draggable:g.collapsed,selectable:true};
  });
  const visibleNodes:Node[]=nodes.filter(n=>representative(n.id)===n.id).map(n=>({...n,zIndex:2,type:'workflow',data:{...n.data,lang,direction:groups.find(g=>g.id===parents.get(n.id))?.direction??(parents.has(n.id)?'DOWN':'RIGHT'),onOpen:(path:string[])=>onOpen(n.id,path)},...nodeSize(n.data.config)}));
  const visibleEdges:Edge[]=[];const links=new Set<string>();
  for(const edge of edges){const source=representative(edge.source),target=representative(edge.target);if(source===target)continue;
    const grouped=source!==edge.source||target!==edge.target;const signature=source+'|'+target+'|'+edge.data?.when;
    if(grouped&&links.has(signature))continue;links.add(signature);
    visibleEdges.push({...edge,source,target,sourceHandle:source===edge.source?edge.sourceHandle:undefined,deletable:!grouped,selectable:!grouped});
  }
  const visible=[...groupNodes,...visibleNodes];
  const visibleIndex=new Map(visible.map(n=>[n.id,n]));
  const obstacles=visible.filter(n=>n.type!=='groupCard'||(n.data.group as Group).collapsed).map(n=>boxes.get(n.id)!);
  // Expanded group headers remain readable when edges cross their boundary.
  obstacles.push(...groupNodes.filter(n=>!(n.data.group as Group).collapsed).map(n=>{const b=boxes.get(n.id)!;return {...b,height:34};}));
  const routed=visibleEdges.map(edge=>{
    const source=visibleIndex.get(edge.source)!,target=visibleIndex.get(edge.target)!;
    const s=boxes.get(source.id)!,t=boxes.get(target.id)!;
    const downS=source.data.direction==='DOWN',downT=target.data.direction==='DOWN';
    const ratio=edge.sourceHandle&&typeof edge.data?.when==='boolean'?(edge.data.when?0.35:0.75):0.5;
    const start=downS?{x:s.x+s.width*ratio,y:s.y+s.height}:{x:s.x+s.width,y:s.y+s.height*ratio};
    const end=downT?{x:t.x+t.width/2,y:t.y}:{x:t.x,y:t.y+t.height/2};
    return {...edge,type:'workflow',data:{...edge.data,points:routeAround(start,end,downS,downT,obstacles)}};
  });
  return {nodes:visible,edges:routed,boxes};
}

export async function arrange(nodes:FlowNode[],edges:Edge[],groups:Group[]):Promise<FlowNode[]> {
  const view=canvasView(nodes,edges,groups,'en',()=>{},()=>{});
  const parents=new Map(groups.flatMap(g=>g.members.map(id=>[id,g.id] as const)));
  const {default:ELK}=await import('elkjs/lib/elk.bundled.js');
  const elk=new ELK();
  type Layout={width:number;height:number;positions:Map<string,{x:number;y:number}>};
  // Layout each compound independently: ELK's single INCLUDE_CHILDREN pass
  // applies a shared direction to hierarchy-crossing edges.
  const level=async(ids:string[],direction:string,groupId?:string):Promise<Layout>=>{
    const children=await Promise.all(ids.map(async id=>{
      const group=groups.find(g=>g.id===id);
      if(group&&!group.collapsed)return {id,...await level(group.members,group.direction??'DOWN',id)};
      const size=group?{width:280,height:112}:nodeSize(nodes.find(n=>n.id===id)!.data.config);
      return {id,...size,positions:new Map<string,{x:number;y:number}>()};
    }));
    const allowed=new Set(ids);
    const lift=(original:string)=>{let id=original;while(!allowed.has(id)&&parents.has(id))id=parents.get(id)!;return allowed.has(id)?id:null;};
    const links=new Map<string,{id:string;sources:string[];targets:string[]}>();
    for(const edge of edges){const source=lift(edge.source),target=lift(edge.target);if(source&&target&&source!==target)links.set(source+'|'+target,{id:source+'|'+target,sources:[source],targets:[target]});}
    const layout=await elk.layout<ElkNode>({id:groupId??'root',layoutOptions:{'elk.algorithm':'layered','elk.direction':direction,
      'elk.edgeRouting':'ORTHOGONAL','elk.padding':groupId?'[top=72,left=24,bottom=24,right=24]':'[top=60,left=40,bottom=40,right=40]',
      'elk.spacing.nodeNode':'44','elk.layered.spacing.nodeNodeBetweenLayers':direction==='DOWN'?'50':'80'},
      children:children.map(c=>({id:c.id,width:c.width,height:c.height})),edges:[...links.values()]});
    const positions=new Map<string,{x:number;y:number}>();
    for(const item of layout.children??[]){const position={x:item.x??0,y:item.y??0};positions.set(item.id,position);
      for(const [id,p] of children.find(c=>c.id===item.id)!.positions)positions.set(id,{x:position.x+p.x,y:position.y+p.y});}
    return {width:Math.max(280,layout.width??280),height:layout.height??112,positions};
  };
  const roots=[...nodes.map(n=>n.id),...groups.map(g=>g.id)].filter(id=>!parents.has(id));
  const {positions}=await level(roots,'RIGHT');
  const updates=new Map<string,{x:number;y:number}>();
  for(const group of groups.filter(g=>g.collapsed&&positions.has(g.id))){const before=view.boxes.get(group.id)!,after=positions.get(group.id)!;
    for(const id of leaves(group.id,groups)){const node=nodes.find(n=>n.id===id);if(node)updates.set(id,{x:node.position.x+after.x-before.x,y:node.position.y+after.y-before.y});}}
  return nodes.map(n=>({...n,position:updates.get(n.id)??positions.get(n.id)??n.position}));
}
