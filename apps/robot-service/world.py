"""CPU Franka tabletop world. Actions use IK, joint motors and a grasp constraint."""

import base64
import io
import math

import pybullet as p
import pybullet_data
from PIL import Image

COLORS = {
    "red": [0.85, 0.12, 0.12, 1],
    "blue": [0.12, 0.32, 0.85, 1],
    "yellow": [0.96, 0.72, 0.08, 1],
}
HOME = [0, -0.45, 0, -2.15, 0, 1.75, 0.78]
START = {"red": [0.42, -0.19, 0.026], "blue": [0.55, -0.04, 0.026], "yellow": [0.4, 0.10, 0.026]}


class World:
    def __init__(self, snapshot=None):
        self.cid = p.connect(p.DIRECT)
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self.cid)
        p.setGravity(0, 0, -9.81, physicsClientId=self.cid)
        p.setTimeStep(1 / 240, physicsClientId=self.cid)
        p.loadURDF("plane.urdf", physicsClientId=self.cid)
        self.robot = p.loadURDF(
            "franka_panda/panda.urdf", useFixedBase=True, physicsClientId=self.cid
        )
        self.objects = {}
        for name, color in COLORS.items():
            shape = p.createCollisionShape(
                p.GEOM_BOX, halfExtents=[0.025] * 3, physicsClientId=self.cid
            )
            visual = p.createVisualShape(
                p.GEOM_BOX, halfExtents=[0.025] * 3, rgbaColor=color, physicsClientId=self.cid
            )
            state = (snapshot or {}).get("objects", {}).get(name)
            self.objects[name] = p.createMultiBody(
                baseMass=0.05,
                baseCollisionShapeIndex=shape,
                baseVisualShapeIndex=visual,
                basePosition=state["position"] if state else START[name],
                baseOrientation=state["orientation"] if state else [0, 0, 0, 1],
                physicsClientId=self.cid,
            )
            p.changeDynamics(self.objects[name], -1, lateralFriction=1.2, physicsClientId=self.cid)
        # The tray is a flat surface with a raised rim.
        for center, size in [
            ([0.59, 0.25, 0.003], [0.14, 0.09, 0.003]),
            ([0.45, 0.25, 0.015], [0.005, 0.09, 0.015]),
            ([0.73, 0.25, 0.015], [0.005, 0.09, 0.015]),
            ([0.59, 0.16, 0.015], [0.14, 0.005, 0.015]),
            ([0.59, 0.34, 0.015], [0.14, 0.005, 0.015]),
        ]:
            col = p.createCollisionShape(p.GEOM_BOX, halfExtents=size, physicsClientId=self.cid)
            vis = p.createVisualShape(
                p.GEOM_BOX,
                halfExtents=size,
                rgbaColor=[0.38, 0.44, 0.48, 1],
                physicsClientId=self.cid,
            )
            p.createMultiBody(
                baseMass=0,
                baseCollisionShapeIndex=col,
                baseVisualShapeIndex=vis,
                basePosition=center,
                physicsClientId=self.cid,
            )
        joints = (snapshot or {}).get("joints", HOME)
        for joint, value in enumerate(joints):
            p.resetJointState(self.robot, joint, value, physicsClientId=self.cid)
        p.setJointMotorControlArray(
            self.robot,
            list(range(7)),
            p.POSITION_CONTROL,
            targetPositions=joints,
            forces=[120] * 7,
            physicsClientId=self.cid,
        )
        self.grip(0.04)
        self.frames = []
        self.step(80)

    def close(self):
        p.disconnect(self.cid)

    def step(self, count, record=False):
        for i in range(count):
            p.stepSimulation(physicsClientId=self.cid)
            if record and i % 12 == 0:
                self.frames.append(self.image())

    def grip(self, width):
        for index in (9, 10):
            p.setJointMotorControl2(
                self.robot, index, p.POSITION_CONTROL, width, force=40, physicsClientId=self.cid
            )

    def move(self, xyz):
        joints = p.calculateInverseKinematics(
            self.robot,
            11,
            xyz,
            p.getQuaternionFromEuler([math.pi, 0, 0]),
            maxNumIterations=150,
            residualThreshold=1e-5,
            physicsClientId=self.cid,
        )
        p.setJointMotorControlArray(
            self.robot,
            list(range(7)),
            p.POSITION_CONTROL,
            targetPositions=joints[:7],
            forces=[120] * 7,
            physicsClientId=self.cid,
        )
        self.step(180, record=True)

    def snapshot(self):
        return {
            "objects": {
                name: dict(
                    zip(
                        ("position", "orientation"),
                        p.getBasePositionAndOrientation(body, physicsClientId=self.cid),
                    )
                )
                for name, body in self.objects.items()
            },
            "joints": [
                p.getJointState(self.robot, i, physicsClientId=self.cid)[0] for i in range(7)
            ],
        }

    def image(self):
        view = p.computeViewMatrix([1.12, -1.12, 1.03], [0.43, 0.03, 0.05], [0, 0, 1])
        proj = p.computeProjectionMatrixFOV(48, 4 / 3, 0.05, 4)
        rgba = p.getCameraImage(
            640, 480, view, proj, renderer=p.ER_TINY_RENDERER, physicsClientId=self.cid
        )[2]
        return Image.fromarray(rgba).convert("RGB")

    def observation(self):
        image = self.image()
        out = io.BytesIO()
        image.save(out, format="JPEG", quality=85)
        return {
            "images": ["data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()],
            "objects": {
                k: [round(x, 4) for x in v["position"]]
                for k, v in self.snapshot()["objects"].items()
            },
            "tray": {"x": [0.49, 0.69], "y": [0.20, 0.30], "surface_z": 0.006},
            "cube_size": 0.05,
            "frame": "robot_base",
            "units": "meters",
        }

    def act(self, action):
        if action["kind"] == "finish":
            return {"success": True, "moved": False}
        name, target = action["object"], action["position"]
        if name not in self.objects:
            return {"success": False, "error": "unknown object"}
        if not all(math.isfinite(x) for x in target) or not (
            0.25 <= target[0] <= 0.74 and -0.34 <= target[1] <= 0.34 and 0.025 <= target[2] <= 0.20
        ):
            return {"success": False, "error": "target outside configured workspace"}
        body = self.objects[name]
        source, orientation = p.getBasePositionAndOrientation(body, physicsClientId=self.cid)
        self.frames.append(self.image())
        self.grip(0.04)
        self.move([source[0], source[1], 0.32])
        self.move(source)
        self.grip(0)
        self.step(100, record=True)
        contacts = p.getContactPoints(self.robot, body, physicsClientId=self.cid)
        fingers = {c[3] for c in contacts}
        if not fingers.intersection({9, 10}):
            self.grip(0.04)
            self.move([source[0], source[1], 0.32])
            return {"success": False, "error": "gripper did not contact the object"}
        # Attach only after contact; preserve the measured relative pose.
        hand = p.getLinkState(self.robot, 11, physicsClientId=self.cid)
        inv = p.invertTransform(hand[0], hand[1])
        actual = p.getBasePositionAndOrientation(body, physicsClientId=self.cid)
        local = p.multiplyTransforms(*inv, *actual)
        constraint = p.createConstraint(
            self.robot,
            11,
            body,
            -1,
            p.JOINT_FIXED,
            [0, 0, 0],
            local[0],
            [0, 0, 0],
            parentFrameOrientation=local[1],
            physicsClientId=self.cid,
        )
        self.move([source[0], source[1], 0.32])
        self.move([target[0], target[1], 0.32])
        self.move([target[0], target[1], target[2] + 0.012])
        p.removeConstraint(constraint, physicsClientId=self.cid)
        self.grip(0.04)
        self.step(100, record=True)
        self.move([target[0], target[1], 0.32])
        self.move([0.3, -0.25, 0.4])
        self.step(100, record=True)
        actual = p.getBasePositionAndOrientation(body, physicsClientId=self.cid)[0]
        error = math.dist(actual, target)
        return {
            "success": error < 0.045,
            "object": name,
            "position": list(actual),
            "target_error_m": round(error, 4),
        }
