"""Stick-figure exercise illustrations generated as inline SVG (no external images, no licensing issues).

A pose gives absolute directions (degrees) for each body segment in the drawing plane:
0 = down, 90 = right (patient's front in side views), 180 = up, -90/270 = left.
Segments: trunk (pelvis->neck), and for near (n) / far (f) limbs: ua (upper arm), fa (forearm),
th (thigh), sh (shank), ft (foot). Far limbs are drawn lighter (depth cue).
`hl` lists segment groups to highlight in the accent colour (target area).
"""
from __future__ import annotations

import math
from functools import lru_cache

L = {"trunk": 34, "neck": 5, "head": 7, "ua": 17, "fa": 15, "th": 25, "sh": 23, "ft": 7}

STAND = dict(p=(60, 62), trunk=180, nua=0, nfa=0, fua=0, ffa=0, nth=0, nsh=0, nft=90, fth=0, fsh=0, fft=90)


def pose(**kw):
    d = dict(STAND)
    if kw.get("floor"):  # lying poses: unspecified arms rest along the body, not into the floor
        d.update(nua=92, nfa=95, fua=88, ffa=92)
    d.update(kw)
    return d


POSES = {
    # standing family
    "stand": pose(),
    "stand_arms_up": pose(nua=180, nfa=180, fua=175, ffa=175),
    "stand_arms_side": pose(nua=95, nfa=95, fua=-95, ffa=-95),
    "stand_arms_front": pose(nua=90, nfa=90, fua=85, ffa=85),
    "stand_elbow_curl": pose(nua=0, nfa=150, fua=0, ffa=150),
    "stand_overhead_press": pose(nua=150, nfa=180, fua=150, ffa=180),
    "stand_row": pose(trunk=180, nua=-30, nfa=60, fua=-30, ffa=60),
    "stand_side_bend": pose(trunk=160, nua=170, nfa=150, fua=10, ffa=10),
    "stand_bend_fwd": pose(p=(50, 62), trunk=100, nua=10, nfa=10, fua=5, ffa=5),
    "stand_extension": pose(trunk=200, nua=-20, nfa=-20, fua=-20, ffa=-20),
    "stand_neck_flex": pose(trunk=180, head_tilt=40),
    "stand_neck_side": pose(trunk=180, head_tilt=-35),
    "stand_calf_raise": pose(p=(60, 58), nft=150, fft=150),
    "stand_single_leg": pose(nth=70, nsh=0, nua=95, nfa=95, fua=-95, ffa=-95),
    "stand_hip_abd": pose(nth=35, nsh=35, fua=-10, ffa=-10),
    "stand_hip_ext": pose(nth=-30, nsh=-30, nua=60, nfa=80),
    "stand_quad_stretch": pose(nth=-10, nsh=170, nft=170, nua=-20, nfa=150),
    "stand_hamstring_step": pose(p=(50, 62), trunk=120, nth=55, nsh=80, nft=150, fth=0, fsh=0),
    "stand_calf_stretch_wall": pose(p=(55, 62), trunk=160, nth=20, nsh=0, fth=-25, fsh=-25, fft=65, nua=120, nfa=100, fua=120, ffa=100, prop="wall"),
    "squat": pose(p=(52, 76), trunk=150, nth=80, nsh=-20, fth=80, fsh=-20, nua=90, nfa=90, fua=90, ffa=90),
    "mini_squat": pose(p=(56, 69), trunk=165, nth=40, nsh=-15, fth=40, fsh=-15, nua=80, nfa=80, fua=80, ffa=80),
    "wall_sit": pose(p=(46, 76), trunk=180, nth=90, nsh=0, fth=90, fsh=0, prop="wall_back"),
    "lunge": pose(p=(58, 74), trunk=180, nth=60, nsh=-10, fth=-40, fsh=-80, fft=10),
    "step_up": pose(p=(58, 60), nth=50, nsh=-5, prop="step"),
    "walk": pose(nth=25, nsh=5, fth=-20, fsh=-35, nua=-25, nfa=-15, fua=25, ffa=40),
    "march": pose(nth=85, nsh=0, nua=-30, nfa=60, fua=30, ffa=90),
    "tandem": pose(nth=8, nsh=8, fth=-8, fsh=-8, nua=95, nfa=95, fua=-95, ffa=-95),
    "wall_pushup": pose(p=(52, 62), trunk=150, nua=110, nfa=95, fua=110, ffa=95, prop="wall"),
    "wall_slide": pose(trunk=180, nua=150, nfa=170, fua=150, ffa=170, prop="wall_back"),
    "doorway_stretch": pose(nua=-90, nfa=180, fua=-90, ffa=180, prop="door"),
    "pendulum": pose(p=(50, 62), trunk=95, nua=0, nfa=0, fua=150, ffa=150, prop="table"),
    "band_ext_rot": pose(nua=0, nfa=60, fua=0, ffa=100, prop="band"),
    "band_pull": pose(nua=90, nfa=90, fua=90, ffa=90, prop="band"),
    "wrist_stretch": pose(nua=90, nfa=90, fua=80, ffa=60),
    "grip": pose(nua=0, nfa=90, fua=0, ffa=0, prop="ball_hand"),
    # sitting family
    "sit": pose(p=(50, 70), trunk=180, nth=90, nsh=0, fth=90, fsh=0, nua=0, nfa=80, fua=0, ffa=80, prop="chair"),
    "sit_knee_ext": pose(p=(50, 70), trunk=180, nth=90, nsh=90, nft=180, fth=90, fsh=0, nua=0, nfa=70, prop="chair"),
    "sit_lean": pose(p=(50, 70), trunk=150, nth=90, nsh=0, fth=90, fsh=0, nua=20, nfa=60, prop="chair"),
    "sit_rotation": pose(p=(50, 70), trunk=180, nth=90, nsh=0, fth=90, fsh=0, nua=90, nfa=-90, fua=-60, ffa=-60, prop="chair"),
    "sit_ankle": pose(p=(50, 70), trunk=180, nth=90, nsh=40, nft=150, fth=90, fsh=0, nua=0, nfa=70, prop="chair"),
    "sit_to_stand": pose(p=(56, 66), trunk=140, nth=60, nsh=-10, fth=60, fsh=-10, nua=90, nfa=90, fua=90, ffa=90, prop="chair"),
    "sit_slump": pose(p=(50, 70), trunk=160, head_tilt=40, nth=90, nsh=90, nft=180, fth=90, fsh=0, nua=10, nfa=10, prop="chair"),
    "sit_arm_ex": pose(p=(50, 70), trunk=180, nth=90, nsh=0, fth=90, fsh=0, nua=90, nfa=90, fua=0, ffa=90, prop="table_low"),
    "long_sit": pose(p=(30, 92), trunk=170, nth=90, nsh=90, nft=180, fth=90, fsh=90, fft=180, nua=20, nfa=40),
    # supine family (head to the left)
    "supine": pose(p=(66, 96), trunk=-90, nth=90, nsh=90, nft=180, fth=90, fsh=90, fft=180, nua=92, nfa=95, fua=88, ffa=92, floor=True),
    "hook_lying": pose(p=(66, 96), trunk=-90, nth=135, nsh=45, nft=90, fth=135, fsh=45, fft=90, nua=92, nfa=95, floor=True),
    "bridge": pose(p=(68, 84), trunk=-110, nth=110, nsh=10, nft=90, fth=110, fsh=10, fft=90, nua=92, nfa=95, floor=True),
    "knee_to_chest": pose(p=(66, 96), trunk=-90, nth=170, nsh=60, nft=150, fth=90, fsh=90, fft=180, nua=170, nfa=60, floor=True),
    "slr": pose(p=(66, 96), trunk=-90, nth=140, nsh=140, nft=230, fth=135, fsh=45, fft=90, nua=92, nfa=95, floor=True),
    "dead_bug": pose(p=(66, 96), trunk=-90, nth=180, nsh=90, nft=180, fth=120, fsh=120, fft=210, nua=180, nfa=180, fua=170, ffa=170, floor=True),
    "supine_arm_up": pose(p=(66, 96), trunk=-90, nth=135, nsh=45, nft=90, fth=135, fsh=45, fft=90, nua=180, nfa=180, fua=88, ffa=92, floor=True),
    "supine_twist": pose(p=(66, 96), trunk=-90, nth=150, nsh=60, nft=90, fth=150, fsh=60, fft=90, nua=-170, nfa=-170, fua=170, ffa=170, floor=True, rot=True),
    "heel_slide": pose(p=(66, 96), trunk=-90, nth=120, nsh=60, nft=90, fth=90, fsh=90, fft=180, nua=92, nfa=95, floor=True),
    "chin_tuck_supine": pose(p=(66, 96), trunk=-90, head_tilt=-20, nth=135, nsh=45, nft=90, fth=135, fsh=45, fft=90, nua=92, nfa=95, floor=True),
    "breath_supine": pose(p=(66, 96), trunk=-90, nth=135, nsh=45, nft=90, fth=135, fsh=45, fft=90, nua=150, nfa=60, floor=True, breath=True),
    # side-lying
    "side_lying": pose(p=(66, 96), trunk=-90, nth=90, nsh=90, nft=180, fth=90, fsh=90, fft=180, nua=-170, nfa=-170, fua=88, ffa=92, floor=True),
    "clam": pose(p=(66, 96), trunk=-90, nth=130, nsh=60, nft=90, fth=110, fsh=60, fft=90, nua=-170, nfa=-170, floor=True),
    "side_leg_raise": pose(p=(66, 96), trunk=-90, nth=110, nsh=110, nft=200, fth=90, fsh=90, fft=180, nua=-170, nfa=-170, floor=True),
    "side_plank": pose(p=(66, 86), trunk=-110, nth=100, nsh=100, nft=180, fth=100, fsh=100, fft=180, nua=-10, nfa=-90, fua=170, ffa=170, floor=True),
    # prone family
    "prone": pose(p=(66, 98), trunk=-90, nth=90, nsh=90, nft=0, fth=90, fsh=90, fft=0, nua=-170, nfa=-170, fua=-100, ffa=-100, floor=True, prone=True),
    "prone_press_up": pose(p=(70, 98), trunk=-120, nth=90, nsh=90, nft=0, fth=90, fsh=90, fft=0, nua=-10, nfa=-90, fua=-10, ffa=-90, floor=True, prone=True),
    "prone_leg_lift": pose(p=(66, 98), trunk=-90, nth=75, nsh=75, nft=-15, fth=90, fsh=90, fft=0, nua=92, nfa=95, floor=True, prone=True),
    "prone_y": pose(p=(66, 98), trunk=-90, nth=90, nsh=90, nft=0, fth=90, fsh=90, fft=0, nua=-150, nfa=-150, fua=-150, ffa=-150, floor=True, prone=True),
    "prone_knee_flex": pose(p=(66, 98), trunk=-90, nth=90, nsh=180, nft=90, fth=90, fsh=90, fft=0, nua=92, nfa=95, floor=True, prone=True),
    "plank": pose(p=(70, 82), trunk=-95, nth=95, nsh=95, nft=10, fth=95, fsh=95, fft=10, nua=0, nfa=-90, fua=0, ffa=-90, floor=True),
    # quadruped
    "quadruped": pose(p=(80, 70), trunk=-90, nth=0, nsh=90, nft=90, fth=0, fsh=90, fft=90, nua=0, nfa=0, fua=0, ffa=0, floor=True),
    "cat": pose(p=(80, 68), trunk=-80, back_curve=-10, head_tilt=30, nth=0, nsh=90, nft=90, fth=0, fsh=90, fft=90, nua=0, nfa=0, fua=0, ffa=0, floor=True),
    "camel": pose(p=(80, 72), trunk=-100, back_curve=12, head_tilt=-25, nth=0, nsh=90, nft=90, fth=0, fsh=90, fft=90, nua=0, nfa=0, fua=0, ffa=0, floor=True),
    "bird_dog": pose(p=(80, 70), trunk=-90, nth=0, nsh=90, nft=90, fth=90, fsh=90, fft=0, nua=0, nfa=0, fua=-90, ffa=-90, floor=True),
    "child_pose": pose(p=(84, 86), trunk=-145, nth=-40, nsh=90, nft=90, fth=-40, fsh=90, fft=90, nua=-90, nfa=-90, fua=-90, ffa=-90, floor=True),
    "kneeling_hip_flexor": pose(p=(62, 66), trunk=180, nth=95, nsh=0, nft=90, fth=-25, fsh=-90, fft=-90, nua=60, nfa=80, floor=True),
    # head/face/hand close-ups
    "head_jaw": pose(trunk=180, jaw=True),
    "hand_fingers": pose(nua=0, nfa=90, fua=0, ffa=0, fingers=True),
    "bike": pose(p=(56, 62), trunk=160, nth=70, nsh=-10, fth=20, fsh=10, nua=60, nfa=80, fua=60, ffa=80, prop="bike"),
    "treadmill": pose(nth=25, nsh=5, fth=-20, fsh=-35, nua=-25, nfa=-15, fua=25, ffa=40, prop="treadmill"),
    "balance_board": pose(p=(60, 58), nua=95, nfa=95, fua=-95, ffa=-95, prop="board"),
}

HL_GROUPS = {
    "neck": ["neck", "head"], "head": ["head"], "jaw": ["head"], "trunk": ["trunk"], "upper_back": ["trunk_up"],
    "low_back": ["trunk_low"], "pelvis": ["pelvis"], "shoulder": ["nua", "shoulder"], "arm": ["nua"], "elbow": ["nua", "nfa"],
    "forearm": ["nfa"], "wrist": ["nfa", "nhand"], "hand": ["nhand"], "hip": ["nth", "pelvis"], "thigh": ["nth"],
    "knee": ["nth", "nsh"], "leg": ["nsh"], "ankle": ["nsh", "nft"], "foot": ["nft"], "core": ["trunk_low", "pelvis"],
    "chest": ["trunk_up"], "whole": ["trunk", "nth", "nsh", "nua", "nfa"], "abdomen": ["trunk_low"],
}


def _pt(o, ang, ln):
    a = math.radians(ang)
    return (o[0] + ln * math.sin(a), o[1] + ln * math.cos(a))


def _line(a, b, cls):
    return f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" class="{cls}"/>'


@lru_cache(maxsize=512)
def svg(pose_name: str, highlight: str = "", size: int = 120) -> str:
    ps = POSES.get(pose_name, POSES["stand"])
    hl = set()
    for h in (highlight or "").split(","):
        hl.update(HL_GROUPS.get(h.strip(), []))
    segs = []  # (a, b, kind, name)
    pel = (0.0, 0.0)
    tr = ps["trunk"]
    curve = ps.get("back_curve", 0)
    mid = _pt(pel, tr, L["trunk"] / 2)
    neck = _pt(mid, tr + curve, L["trunk"] / 2)
    sh = _pt(neck, tr + 180, 3)
    head_dir = tr + ps.get("head_tilt", 0) * (1 if tr >= 0 else -1)
    neck_end = _pt(neck, head_dir, L["neck"])
    hc = _pt(neck, head_dir, L["neck"] + L["head"])

    def limb(prefix, origin, names, far):
        o = origin
        for s_ in names:
            ang = ps.get(prefix + s_)
            if ang is None:
                return o
            e = _pt(o, ang, L[s_])
            segs.append((o, e, "far" if far else "seg", "n" + s_))
            o = e
        return o

    limb("f", pel, ["th", "sh", "ft"], True)
    fhand = limb("f", sh, ["ua", "fa"], True)
    segs.append((pel, mid, "seg", "trunk_low"))
    segs.append((mid, neck, "seg", "trunk_up"))
    segs.append((neck, neck_end, "seg", "neck"))
    hand = limb("n", sh, ["ua", "fa"], False)
    limb("n", pel, ["th", "sh", "ft"], False)
    # auto-fit: lowest point on the floor line, keep within the frame
    xs = [c for a, b, *_ in segs for c in (a[0], b[0])] + [hc[0] - L["head"], hc[0] + L["head"]]
    ys = [c for a, b, *_ in segs for c in (a[1], b[1])] + [hc[1] - L["head"], hc[1] + L["head"]]
    floor_y = 104
    dy = floor_y - max(ys)
    cx = (min(xs) + max(xs)) / 2
    dx = 60 - cx
    T = lambda q: (q[0] + dx, q[1] + dy)
    pelT, handT, fhandT, hcT, shT = T(pel), T(hand), T(fhand), T(hc), T(sh)
    parts = [f'<line x1="2" y1="{floor_y + 1.5}" x2="118" y2="{floor_y + 1.5}" class="prop"/>']
    prop = ps.get("prop")
    px, py = pelT
    if prop == "wall":
        wx = max(handT[0], fhandT[0]) + 2
        parts.append(f'<line x1="{wx:.1f}" y1="6" x2="{wx:.1f}" y2="{floor_y}" class="prop"/>')
    elif prop == "wall_back":
        wx = min(xs) + dx - 2
        parts.append(f'<line x1="{wx:.1f}" y1="6" x2="{wx:.1f}" y2="{floor_y}" class="prop"/>')
    elif prop == "door":
        parts.append(f'<rect x="{min(handT[0], fhandT[0]) - 2:.1f}" y="4" width="{abs(handT[0] - fhandT[0]) + 4:.1f}" height="{floor_y - 4}" class="propf"/>')
    elif prop == "chair":
        parts.append(f'<path d="M{px - 14:.1f} {py + 3:.1f} H{px + 12:.1f} M{px - 11:.1f} {py + 3:.1f} V{floor_y} M{px + 9:.1f} {py + 3:.1f} V{floor_y} M{px - 14:.1f} {py + 3:.1f} V{py - 26:.1f}" class="prop"/>')
    elif prop in ("table", "table_low"):
        ty = min(handT[1], fhandT[1]) + 2 if prop == "table" else handT[1] + 2
        x0 = max(handT[0], fhandT[0]) - 6
        parts.append(f'<path d="M{x0:.1f} {ty:.1f} H118 M114 {ty:.1f} V{floor_y}" class="prop"/>')
    elif prop == "step":
        parts.append(f'<rect x="{px + 4:.1f}" y="{floor_y - 12}" width="34" height="12" class="propf"/>')
    elif prop == "band":
        parts.append(f'<line x1="114" y1="20" x2="114" y2="{floor_y}" class="prop"/><line x1="114" y1="{handT[1]:.1f}" x2="{handT[0]:.1f}" y2="{handT[1]:.1f}" class="band"/>')
    elif prop == "bike":
        parts.append(f'<circle cx="{px + 8:.1f}" cy="{floor_y - 12}" r="9" class="prop"/><path d="M{px - 8:.1f} {py + 2:.1f} H{px + 6:.1f} M{px + 8:.1f} {floor_y - 12} L{px:.1f} {py + 2:.1f} M{handT[0] + 2:.1f} {handT[1]:.1f} L{px + 18:.1f} {floor_y - 6}" class="prop"/>')
    elif prop == "treadmill":
        parts.append(f'<path d="M10 {floor_y - 2} H104 L110 {floor_y - 10} M106 {handT[1]:.1f} V{floor_y - 8}" class="prop"/>')
    elif prop == "board":
        parts.append(f'<path d="M36 {floor_y + 1} L46 {floor_y - 3} H74 L84 {floor_y + 1}" class="prop"/>')
    for a, b, kind, name in segs:
        c = kind
        if kind == "seg" and (name in hl or (name.startswith("trunk") and "trunk" in hl)):
            c += " hl"
        a, b = T(a), T(b)
        parts.append(_line(a, b, c))
    if "pelvis" in hl:
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" class="dot"/>')
    if "shoulder" in hl:
        parts.append(f'<circle cx="{shT[0]:.1f}" cy="{shT[1]:.1f}" r="4" class="dot"/>')
    parts.append(f'<circle cx="{hcT[0]:.1f}" cy="{hcT[1]:.1f}" r="{L["head"]}" class="head{" hlf" if "head" in hl else ""}"/>')
    if ps.get("jaw"):
        parts.append(f'<path d="M{hcT[0] - 3:.1f} {hcT[1] + 3:.1f} q3 3 6 0" class="seg hl"/>')
    if "nhand" in hl or prop == "ball_hand" or ps.get("fingers"):
        parts.append(f'<circle cx="{handT[0]:.1f}" cy="{handT[1]:.1f}" r="3.2" class="dot"/>')
    if ps.get("breath"):
        c = T(_pt(pel, tr, L["trunk"] * 0.45))
        parts.append(f'<ellipse cx="{c[0]:.1f}" cy="{c[1] - 6:.1f}" rx="9" ry="3.5" class="breath"/>')
    style = ("<style>.seg{stroke:#0f2c4c;stroke-width:3.2;stroke-linecap:round;fill:none}"
             ".far{stroke:#a9bccc;stroke-width:2.8;stroke-linecap:round;fill:none}"
             ".hl{stroke:#e0761f}.head{fill:#fff;stroke:#0f2c4c;stroke-width:2.4}.hlf{fill:#fde3cc;stroke:#e0761f}"
             ".dot{fill:#e0761f}.prop{stroke:#9aa9b6;stroke-width:2;fill:none;stroke-linecap:round}"
             ".propf{fill:#eef2f6;stroke:#9aa9b6;stroke-width:1.5}.band{stroke:#3aa6d6;stroke-width:1.6;stroke-dasharray:3 2}"
             ".breath{fill:none;stroke:#3aa6d6;stroke-width:1.8;stroke-dasharray:3 2}</style>")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 110" width="{size}" height="{int(size * 110 / 120)}" '
            f'role="img" aria-hidden="true">{style}{"".join(parts)}</svg>')
