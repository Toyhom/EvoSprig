# Robot simulation tools

A CPU Franka Panda tabletop service for visual agents. It exposes camera observations, cube poses, pick-and-place actions and geometric task checks. Each action saves a scene snapshot and an idempotent receipt so the application can resume.

Use Python 3.10 or 3.11 for the prebuilt PyBullet wheel, in a separate environment from EvoSprig:

```bash
python3.11 -m venv .venv-robot
.venv-robot/bin/pip install -r apps/robot-service/requirements.txt
.venv-robot/bin/python apps/robot-service/app.py --workspace .evosprig/robot
```

The service listens on `127.0.0.1:18890`. Set `--port` to change it and update the application's deployment profile.

| Tool | Input | Returns |
| --- | --- | --- |
| `POST /start` | `scene: tabletop` | Episode ID and scene image |
| `POST /observe` | Episode ID | Camera image, object poses and tray bounds |
| `POST /act` | Episode ID and a move/finish action | Motion outcome, final position and rendered clip |
| `POST /check` | Episode ID and geometric goals | Per-goal checks and task success |

Writes require `Idempotency-Key`. Reusing a key for a different action returns HTTP 409. Scene snapshots and receipts commit together; replaying a completed action returns its original result. Each request restores its own PyBullet world. Run one service process per workspace.

The supplied backend uses simulated poses for localization, inverse kinematics and joint motors for motion, and a constraint attached after gripper contact. It provides a CPU environment for [RAI manipulation (EvoSprig)](../../examples/rai-manipulation/). To use a different simulator, implement these four tool contracts and preserve the action receipt behavior.

```bash
.venv-robot/bin/python -m pip install pytest
.venv-robot/bin/python -m pytest apps/robot-service/tests -q
```
