import {BaseEdge,getSmoothStepPath,type Edge,type EdgeProps} from '@xyflow/react';
import {roundedPath,type Point} from './routing';

function WorkflowEdge(props:EdgeProps<Edge<{points?:Point[]}>>){
  const {sourceX,sourceY,targetX,targetY,data}=props;
  const points=data?.points;
  let [path,labelX,labelY]=getSmoothStepPath(props);
  if(points?.length){
    const routed=[{x:sourceX,y:sourceY},...points.slice(1,-1),{x:targetX,y:targetY}];
    path=roundedPath(routed);
    const lengths=routed.slice(1).map((p,i)=>Math.hypot(p.x-routed[i].x,p.y-routed[i].y));
    let remaining=lengths.reduce((a,b)=>a+b,0)/2;
    for(let i=0;i<lengths.length;i++){
      if(remaining<=lengths[i]){const ratio=lengths[i]?remaining/lengths[i]:0;labelX=routed[i].x+(routed[i+1].x-routed[i].x)*ratio;labelY=routed[i].y+(routed[i+1].y-routed[i].y)*ratio;break;}
      remaining-=lengths[i];
    }
  }
  return <BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} style={props.style} interactionWidth={20}
    label={props.label} labelX={labelX} labelY={labelY} labelStyle={{fontSize:11,fill:'#76808d'}} labelBgStyle={{fill:'#fafafa'}}/>;
}
export const edgeTypes={workflow:WorkflowEdge};
