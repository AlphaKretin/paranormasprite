"""
bundle_data.py
--------------
Loads a character asset bundle and exposes all metadata needed for the viewer
(body list, expressions, sprite rects) without touching the filesystem cache.

All pure logic is copied verbatim from composite_portraits.py and de-globalised.
"""

import os
import re
from dataclasses import dataclass, field

from scanner import load_bundle

# ---------------------------------------------------------------------------
# Constants (copied from composite_portraits.py)
# ---------------------------------------------------------------------------

EYE_FRAME_PREF   = ["n1", "n0", "f0", "f1", "b0", "b1", "n2"]
MOUTH_FRAME_PREF = ["1", "0", "2"]

_BASE_FAMILY_RE = re.compile(r"^(base|b[0-9x])$")


# ---------------------------------------------------------------------------
# Hierarchy helpers (copied verbatim from composite_portraits.py)
# ---------------------------------------------------------------------------

def _get_char_code(env):
    for type_name in ("Sprite", "Texture2D"):
        for obj in env.objects:
            if obj.type.name == type_name:
                d = obj.read()
                m = re.match(r"dice_([a-z]+)", d.m_Name)
                if m:
                    return m.group(1)
    return None


def build_transform_tree(env):
    pid_to_go = {}
    for obj in env.objects:
        if obj.type.name == "GameObject":
            pid_to_go[obj.path_id] = obj.read().m_Name

    transforms = {}
    for obj in env.objects:
        if obj.type.name == "Transform":
            t = obj.read_typetree()
            lp = t.get("m_LocalPosition", {"x": 0.0, "y": 0.0})
            transforms[obj.path_id] = {
                "go_name" : pid_to_go.get(t["m_GameObject"]["m_PathID"], ""),
                "parent"  : t["m_Father"]["m_PathID"],
                "children": [c["m_PathID"] for c in t.get("m_Children", [])],
                "lp"      : (lp.get("x", 0.0), lp.get("y", 0.0)),
            }
    return transforms


def _world_pos(pid, transforms, memo):
    if pid in memo:
        return memo[pid]
    t = transforms.get(pid)
    if t is None:
        r = (0.0, 0.0)
    else:
        lx, ly = t["lp"]
        p = t["parent"]
        if p == 0 or p not in transforms:
            r = (lx, ly)
        else:
            px, py = _world_pos(p, transforms, memo)
            r = (px + lx, py + ly)
    memo[pid] = r
    return r


def find_node(transforms, name):
    for pid, t in transforms.items():
        if t["go_name"] == name:
            return pid
    return None


def children_names(transforms, pid):
    return [(c, transforms[c]["go_name"])
            for c in transforms[pid]["children"] if c in transforms]


# ---------------------------------------------------------------------------
# Expression helpers (copied verbatim)
# ---------------------------------------------------------------------------

def parse_eye_name(name):
    m = re.fullmatch(r"(e_\w+?)_([a-z]\d+)", name)
    return (m.group(1), m.group(2)) if m else None


def parse_mouth_name(name):
    m = re.fullmatch(r"(m_\w+?)_(\d+)", name)
    return (m.group(1), m.group(2)) if m else None


def expression_core(base):
    _, _, tag = base.partition("_")
    if re.search(r"_[a-z]$", tag):
        tag = tag[:-2]
    return tag


def expr_unique(base, core):
    _, _, tag = base.partition("_")
    if tag == core:
        return ""
    if tag.startswith(core + "_"):
        return tag[len(core) + 1:]
    return tag


# ---------------------------------------------------------------------------
# Group / add-parts derivation (copied verbatim)
# ---------------------------------------------------------------------------

def derive_groups(transforms, body_params):
    top_pid = find_node(transforms, "top")
    if top_pid is None:
        return []

    body_set = set(body_params)
    groups, cur_bodies, cur_eyes, cur_mouths = [], [], {}, {}

    def flush():
        if cur_bodies:
            groups.append({"bodies": list(cur_bodies),
                           "eyes": dict(cur_eyes),
                           "mouths": dict(cur_mouths)})

    for _, go_name in children_names(transforms, top_pid):
        if go_name in body_set:
            if cur_eyes or cur_mouths:
                flush()
                cur_bodies, cur_eyes, cur_mouths = [], {}, {}
            cur_bodies.append(go_name)
        elif go_name == "add_parts":
            pass
        else:
            ep = parse_eye_name(go_name)
            if ep:
                cur_eyes.setdefault(ep[0], []).append(ep[1])
                continue
            mp = parse_mouth_name(go_name)
            if mp:
                cur_mouths.setdefault(mp[0], []).append(mp[1])

    flush()
    return groups


def derive_add_parts(transforms):
    add_pid = find_node(transforms, "add_parts")
    if add_pid is None:
        return {}

    result = {"cheek": []}
    for c_pid in transforms[add_pid]["children"]:
        if c_pid not in transforms:
            continue
        child_go = transforms[c_pid]["go_name"]
        if child_go == "basecmn":
            for gc_pid in transforms[c_pid]["children"]:
                if gc_pid in transforms:
                    name = transforms[gc_pid]["go_name"]
                    if name not in result["cheek"]:
                        result["cheek"].append(name)
        else:
            add_list, addrev_list, extras_list, cheek_list = [], [], [], []
            for gc in transforms[c_pid]["children"]:
                if gc not in transforms:
                    continue
                name = transforms[gc]["go_name"]
                if name.endswith("_addrev"):
                    addrev_list.append(name)
                elif re.search(r"_add\d+$", name):
                    extras_list.append(name)
                elif name.endswith("_cheek"):
                    cheek_list.append(name)
                else:
                    add_list.append(name)
            result[child_go] = {"add": add_list,
                                 "addrev": addrev_list,
                                 "extras": extras_list,
                                 "cheek": cheek_list}
    return result


# ---------------------------------------------------------------------------
# Sprite rect loading (copied verbatim)
# ---------------------------------------------------------------------------

def load_sprite_rects(env, transforms):
    memo = {}

    def wp(pid):
        return _world_pos(pid, transforms, memo)

    sprite_world: dict = {}

    top_pid = find_node(transforms, "top")
    if top_pid:
        for c_pid, c_name in children_names(transforms, top_pid):
            if c_name not in sprite_world:
                sprite_world[c_name] = wp(c_pid)

    add_pid = find_node(transforms, "add_parts")
    if add_pid:
        for c_pid, c_name in children_names(transforms, add_pid):
            if c_name not in sprite_world:
                sprite_world[c_name] = wp(c_pid)
            for gc_pid, gc_name in children_names(transforms, c_pid):
                if gc_name not in sprite_world:
                    sprite_world[gc_name] = wp(gc_pid)

    rects = {}
    for obj in env.objects:
        if obj.type.name == "Sprite":
            d = obj.read()
            if d.m_Name.startswith("dice_"):
                continue
            r = d.m_Rect
            name = d.m_Name
            wx, wy = sprite_world.get(name, (0.0, 0.0))
            rects[name] = (wx + r.x, wy + r.y, r.width, r.height)
    return rects


# ---------------------------------------------------------------------------
# Canvas helpers (copied verbatim)
# ---------------------------------------------------------------------------

def union_rect(rects_list):
    if not rects_list:
        return (0, 0, 0, 0)
    ls = [r[0] for r in rects_list]
    bs = [r[1] for r in rects_list]
    rs = [r[0]+r[2] for r in rects_list]
    ts = [r[1]+r[3] for r in rects_list]
    return (min(ls), min(bs), max(rs)-min(ls), max(ts)-min(bs))


def best_eye_frame(frames):
    for p in EYE_FRAME_PREF:
        if p in frames:
            return p
    return frames[0] if frames else None


def best_mouth_frame(frames):
    for p in MOUTH_FRAME_PREF:
        if p in frames:
            return p
    return frames[0] if frames else None


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class BodyInfo:
    name: str
    canvas_rect: tuple
    valid_pair_cores: list
    valid_mouth_cores: list  # non-empty only for back/mouth-only bodies
    eye_by_core: dict        # core → {e_base: [frames]}  (filtered)
    mouth_by_core: dict      # core → {m_base: [frames]}  (filtered)
    add_info: dict           # {add, addrev, extras, cheek}
    has_rev: bool
    has_extras: bool
    has_blush: bool          # True iff _BASE_FAMILY_RE matches body name


class BundleData:
    """
    Loads a Unity asset bundle and exposes all metadata needed by the viewer.
    Does NOT read any extracted PNG files — that is handled by PortraitEngine.
    """

    def __init__(self, bundle_path: str):
        self.char_code: str = ""
        self.sprite_rects: dict = {}
        self.bodies: list = []
        self._body_index: dict = {}
        self._load(bundle_path)

    # ---- public query API ----

    def get_body(self, name: str):
        return self._body_index.get(name)

    def available_cores(self, body: str) -> list:
        bi = self._body_index.get(body)
        if bi is None:
            return []
        seen = set()
        result = []
        for c in bi.valid_pair_cores + bi.valid_mouth_cores:
            if c not in seen:
                seen.add(c)
                result.append(c)
        return result

    def available_eye_frames(self, body: str, core: str) -> list:
        """Returns list of (e_base, frame) tuples."""
        bi = self._body_index.get(body)
        if bi is None:
            return []
        result = []
        for e_base, frames in bi.eye_by_core.get(core, {}).items():
            for frame in frames:
                result.append((e_base, frame))
        return result

    def available_mouth_frames(self, body: str, core: str) -> list:
        """Returns list of (m_base, frame) tuples."""
        bi = self._body_index.get(body)
        if bi is None:
            return []
        result = []
        for m_base, frames in bi.mouth_by_core.get(core, {}).items():
            for frame in frames:
                result.append((m_base, frame))
        return result

    # ---- internal ----

    def _load(self, bundle_path: str):
        env = load_bundle(bundle_path)
        self.char_code = (
            _get_char_code(env)
            or os.path.splitext(os.path.basename(bundle_path))[0]
        )

        transforms = build_transform_tree(env)
        self.sprite_rects = load_sprite_rects(env, transforms)

        body_params = []
        for obj in env.objects:
            if obj.type.name == "MonoBehaviour":
                try:
                    t = obj.read_typetree()
                    if "m_bodyParameters" in t:
                        body_params = t["m_bodyParameters"]
                        break
                except Exception:
                    pass

        if not body_params:
            return

        groups = derive_groups(transforms, body_params)
        add_parts = derive_add_parts(transforms)
        cheek_layers = add_parts.get("cheek", [])

        for group in groups:
            group_body_names = set(group["bodies"])
            eye_exprs = group["eyes"]
            mouth_exprs = group["mouths"]

            # Build core-indexed dicts for the whole group
            eye_by_core_all: dict = {}
            for e_base, e_frames in eye_exprs.items():
                eye_by_core_all.setdefault(expression_core(e_base), {})[e_base] = e_frames

            mouth_by_core_all: dict = {}
            for m_base, m_frames in mouth_exprs.items():
                mouth_by_core_all.setdefault(expression_core(m_base), {})[m_base] = m_frames

            for body in group["bodies"]:
                def core_applies(core, _body=body):
                    return core not in group_body_names or core == _body

                filtered_eye = {c: d for c, d in eye_by_core_all.items() if core_applies(c)}
                filtered_mouth = {c: d for c, d in mouth_by_core_all.items() if core_applies(c)}

                valid_pair_cores = sorted(
                    c for c in set(filtered_eye) & set(filtered_mouth)
                )
                valid_mouth_cores = (
                    sorted(filtered_mouth.keys())
                    if not eye_by_core_all else []
                )

                # Canvas rect: union of all possible layer rects for this body
                relevant = [body]
                for e_base, e_frames in eye_exprs.items():
                    f = best_eye_frame(e_frames)
                    if f:
                        relevant.append(f"{e_base}_{f}")
                for m_base, m_frames in mouth_exprs.items():
                    f = best_mouth_frame(m_frames)
                    if f:
                        relevant.append(f"{m_base}_{f}")
                raw_add = add_parts.get(body, {})
                if isinstance(raw_add, dict):
                    relevant += raw_add.get("add", [])
                    relevant += raw_add.get("addrev", [])
                    relevant += raw_add.get("extras", [])
                if cheek_layers and _BASE_FAMILY_RE.match(body):
                    relevant += cheek_layers
                rects = [self.sprite_rects[n] for n in relevant if n in self.sprite_rects]
                canvas_rect = union_rect(rects) if rects else self.sprite_rects.get(body) or (0, 0, 0, 0)

                raw = add_parts.get(body, {})
                # Cheek: body-specific _cheek sprites + common cheek from basecmn
                # (basecmn cheek only applied to base-family bodies per original logic)
                body_cheek  = list(raw.get("cheek", [])) if isinstance(raw, dict) else []
                common_cheek = list(cheek_layers) if _BASE_FAMILY_RE.match(body) else []
                all_cheek   = body_cheek + common_cheek
                add_info = {
                    "add":    list(raw.get("add", [])) if isinstance(raw, dict) else [],
                    "addrev": list(raw.get("addrev", [])) if isinstance(raw, dict) else [],
                    "extras": list(raw.get("extras", [])) if isinstance(raw, dict) else [],
                    "cheek":  all_cheek,
                }

                bi = BodyInfo(
                    name=body,
                    canvas_rect=canvas_rect,
                    valid_pair_cores=valid_pair_cores,
                    valid_mouth_cores=valid_mouth_cores,
                    eye_by_core=filtered_eye,
                    mouth_by_core=filtered_mouth,
                    add_info=add_info,
                    has_rev=bool(add_info["addrev"]),
                    has_extras=bool(add_info["extras"]),
                    has_blush=bool(all_cheek),
                )
                self.bodies.append(bi)
                self._body_index[body] = bi
