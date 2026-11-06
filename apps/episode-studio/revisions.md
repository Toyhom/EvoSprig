# Plan a revision before rendering

`POST /api/episode/revisions/plan` compares two production snapshots. Each snapshot contains `plan`, optional `references`, `voices`, `style` and `render_profile`. Use the same service authentication as the rest of Episode Studio.

```json
{
  "before": {"plan": {"characters": [], "locations": [], "shots": []}},
  "after": {"plan": {"characters": [], "locations": [], "shots": []}},
  "selected_shots": []
}
```

Supply the actual screenplay and adopted asset records in these fields. The result separates `render` (shot IDs and reasons), `reuse` and `removed`. A changed character reference affects shots that use it; a changed take also affects shots continuing from its ending frame. An independent cut stops that dependency chain. No generation starts when requesting a plan.

Python clients can call `production_manifest()` and `plan_retake()` in [revisions.py](revisions.py). Keep the original snapshot with the adopted takes, compare it to your edited production, then use the canvas's saved-input debug operation to redo the indicated shots. This preserves the distinction between a changed plan and an actually generated replacement.

中文版：这个接口先比较修改前后的剧本、参考图、音色和渲染设置，返回需要重做、可以复用以及已移除的镜头。连续镜头会沿上一镜尾帧的依赖继续检查，独立切镜会中断传播。请求只计算修改范围；确认后通过画布的已保存输入调试重做相应镜头。将原快照与已采用素材一并保存，避免把新计划当成已生成的版本。
