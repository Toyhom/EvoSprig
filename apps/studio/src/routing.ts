export type Point={x:number;y:number};
export type Box=Point&{width:number;height:number};
const same=(a:Point,b:Point)=>Math.abs(a.x-b.x)<.1&&Math.abs(a.y-b.y)<.1;
export function compactPath(points:Point[]):Point[]{
  const result:Point[]=[];
  for(const point of points){
    if(result.length&&same(result.at(-1)!,point))continue;
    while(result.length>1){const a=result.at(-2)!,b=result.at(-1)!;
      const collinear=(a.x===b.x&&b.x===point.x)||(a.y===b.y&&b.y===point.y);
      const forward=(b.x-a.x)*(point.x-b.x)+(b.y-a.y)*(point.y-b.y)>=0;
      if(collinear&&forward)result.pop();else break;}
    result.push(point);
  }
  return result;
}
export function segmentClear(a:Point,b:Point,boxes:Box[]):boolean{
  return !boxes.some(box=>a.x===b.x
    ? a.x>box.x&&a.x<box.x+box.width&&Math.max(a.y,b.y)>box.y&&Math.min(a.y,b.y)<box.y+box.height
    : a.y>box.y&&a.y<box.y+box.height&&Math.max(a.x,b.x)>box.x&&Math.min(a.x,b.x)<box.x+box.width);
}
export function routeAround(start:Point,end:Point,sourceDown:boolean,targetDown:boolean,boxes:Box[]):Point[]|undefined{
  const sameDirection=sourceDown===targetDown;
  const gap=sourceDown?end.y-start.y:end.x-start.x;
  if(sameDirection&&gap>0&&(sourceDown?start.x===end.x:start.y===end.y)&&segmentClear(start,end,boxes))return [start,end];
  const stub=sameDirection&&gap>0?Math.min(24,gap/3):24;
  const a={x:start.x+(sourceDown?0:stub),y:start.y+(sourceDown?stub:0)};
  const b={x:end.x-(targetDown?0:stub),y:end.y-(targetDown?stub:0)};
  const obstacles=boxes.map(v=>({x:v.x-8,y:v.y-8,width:v.width+16,height:v.height+16}));
  const candidates:Point[][]=[[a,{x:b.x,y:a.y},b],[a,{x:a.x,y:b.y},b]];
  const xs=new Set([a.x,b.x,(a.x+b.x)/2,...obstacles.flatMap(v=>[v.x-12,v.x+v.width+12])]);
  const ys=new Set([a.y,b.y,(a.y+b.y)/2,...obstacles.flatMap(v=>[v.y-12,v.y+v.height+12])]);
  for(const x of xs)candidates.push([a,{x,y:a.y},{x,y:b.y},b]);
  for(const y of ys)candidates.push([a,{x:a.x,y},{x:b.x,y},b]);
  const clear=(points:Point[])=>{
    if(points.length<2)return true;
    const next=points[1],previous=points.at(-2)!;
    if(sourceDown?next.y<a.y:next.x<a.x)return false;
    if(targetDown?previous.y>b.y:previous.x>b.x)return false;
    return points.slice(1).every((p,i)=>segmentClear(points[i],p,obstacles));
  };
  let routes=candidates.map(compactPath).filter(clear);
  if(!routes.length){
    const outerX=[Math.min(...xs)-16,Math.max(...xs)+16],outerY=[Math.min(...ys)-16,Math.max(...ys)+16];
    for(const x of outerX)for(const y of outerY){
      candidates.push([a,{x,y:a.y},{x,y},{x:b.x,y},b]);
      candidates.push([a,{x:a.x,y},{x,y},{x,y:b.y},b]);
    }
    routes=candidates.map(compactPath).filter(clear);
  }
  const length=(p:Point[])=>p.slice(1).reduce((sum,v,i)=>sum+Math.abs(v.x-p[i].x)+Math.abs(v.y-p[i].y),0)+p.length*10;
  routes.sort((p,q)=>length(p)-length(q));
  return routes[0]?compactPath([start,...routes[0],end]):undefined;
}
export function roundedPath(points:Point[],radius=9):string{
  if(!points.length)return '';
  let path=`M ${points[0].x} ${points[0].y}`;
  for(let i=1;i<points.length-1;i++){
    const a=points[i-1],b=points[i],c=points[i+1];
    const before=Math.hypot(b.x-a.x,b.y-a.y),after=Math.hypot(c.x-b.x,c.y-b.y);
    const r=Math.min(radius,before/2,after/2);
    if(!r){path+=` L ${b.x} ${b.y}`;continue;}
    const enter={x:b.x+(a.x-b.x)*r/before,y:b.y+(a.y-b.y)*r/before};
    const leave={x:b.x+(c.x-b.x)*r/after,y:b.y+(c.y-b.y)*r/after};
    path+=` L ${enter.x} ${enter.y} Q ${b.x} ${b.y} ${leave.x} ${leave.y}`;
  }
  const last=points.at(-1)!;return path+` L ${last.x} ${last.y}`;
}
