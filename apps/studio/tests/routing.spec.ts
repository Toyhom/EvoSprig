import {test,expect} from '@playwright/test';
import {compactPath,routeAround,segmentClear,roundedPath} from '../src/routing';

test('routing keeps ports directed and avoids intervening cards',()=>{
  for(const vertical of [false,true]){
    const start=vertical?{x:100,y:100}:{x:100,y:100};
    const end=vertical?{x:100,y:500}:{x:500,y:100};
    const obstacle=vertical?{x:20,y:220,width:160,height:120}:{x:220,y:20,width:120,height:160};
    const points=routeAround(start,end,vertical,vertical,[obstacle])!;
    expect(points).toBeDefined();expect(points[0]).toEqual(start);expect(points.at(-1)).toEqual(end);
    expect(points.slice(1).every((p,i)=>(p.x===points[i].x||p.y===points[i].y)&&segmentClear(points[i],p,[obstacle]))).toBe(true);
    expect(vertical?points[1].y>start.y:points[1].x>start.x).toBe(true);
    expect(vertical?points.at(-2)!.y<end.y:points.at(-2)!.x<end.x).toBe(true);
    expect(roundedPath(points)).not.toMatch(/NaN|Infinity/);
  }
});

test('backward links leave and enter on the requested sides',()=>{
  const points=routeAround({x:400,y:100},{x:100,y:300},false,true,[])!;
  expect(points[1].x).toBeGreaterThan(400);
  expect(points.at(-2)!.y).toBeLessThan(300);
  expect(points.slice(1).every((p,i)=>p.x===points[i].x||p.y===points[i].y)).toBe(true);
});

test('path simplification preserves reversals and unavailable routes fall back',()=>{
  expect(compactPath([{x:0,y:0},{x:20,y:0},{x:10,y:0}])).toHaveLength(3);
  expect(routeAround({x:0,y:0},{x:100,y:0},false,false,[{x:10,y:-100,width:80,height:200}])).toBeUndefined();
});

test('nearby facing ports connect without a detour',()=>{
  expect(routeAround({x:100,y:100},{x:100,y:130},true,true,[])).toEqual([{x:100,y:100},{x:100,y:130}]);
  const points=routeAround({x:100,y:100},{x:110,y:130},true,true,[])!;
  expect(points.every(p=>p.x>=100&&p.x<=110&&p.y>=100&&p.y<=130)).toBe(true);
});
