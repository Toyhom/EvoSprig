# RAI manipulation (EvoSprig)

![The robot workflow in EvoSprig Studio](canvas.png)

An EvoSprig reproduction of [RAI's tabletop manipulation application](https://github.com/RobotecAI/rai/blob/main/docs/demos/manipulation.md). Give a robot arm a task: it looks at the scene, moves an object, then looks again before choosing the next action.

## Clear the table

> Put the red cube and the yellow cube inside the tray. Keep the blue cube where it is.

[![Play the robot's pick-and-place sequence](assets/sorting.webp)](assets/sorting.mp4)

## Build a stack

> Put the red cube on top of the blue cube. Leave the yellow cube where it is.

[![Play the stacking sequence](assets/stacking.webp)](assets/stacking.mp4)

## Try it

Start the [robot tool service](../../apps/robot-service/), then set `MOONSHOT_API_KEY` and open the application:

```bash
evosprig serve --project examples/rai-manipulation/agent.yaml \
  --profile examples/rai-manipulation/deployment.example.yaml \
  --studio-dir apps/studio/dist --workspace .evosprig/rai
```

Open **http://127.0.0.1:18766**, paste the [sample request](request.json) and enable writes. The camera, decision and motion appear inside the **manipulate** loop. The final **check** node measures object positions against the supplied goals.

The supplied tools run a Franka Panda in CPU PyBullet, with camera images and simulated object poses; the model profile uses Kimi K3.1 Pro. Original RAI connects its perception and manipulation tools to ROS 2 / O3DE. [Tool contracts](../../apps/robot-service/) define the integration points.

## Make it your robot agent

- Change the task and its geometric goals in the request.
- Edit the controller and manipulation skill on the canvas or in [Python](build_agent.py).
- Configure the loop limit, model and tool endpoints for your environment.
- Select `controller` and `manipulation` in **Improve** to search their instructions using your task suite and environment outcomes.

[RAI paper](https://arxiv.org/abs/2505.07532) · [Original application](https://github.com/RobotecAI/rai/blob/main/examples/manipulation_common.py) · [Build applications](../../docs/build-applications.md)
