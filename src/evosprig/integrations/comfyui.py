"""ComfyUI graph inspection, editing and compilation without loading model code."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

SCALARS = {"INT": "integer", "FLOAT": "number", "STRING": "string", "BOOLEAN": "boolean"}
VIRTUAL = {"SetNode", "GetNode", "Reroute", "PrimitiveNode"}
UI_ONLY = {"Note", "MarkdownNote", "Markdown Note", "忽略多组孤海", "Fast Groups Bypasser (rgthree)",
           "Fast Groups Muter (rgthree)", "Fast Bypasser (rgthree)", "Fast Muter (rgthree)"}
DISCONNECTED = object()


class WorkflowError(ValueError):
    """A graph cannot be compiled without changing its meaning."""


def is_widget(descriptor):
    kind = descriptor[0]
    return isinstance(kind, list) or kind in {*SCALARS, "COMBO"}


def fields(info: dict, live: dict | None = None, prefix: str = ""):
    for group in ("required", "optional", "hidden"):
        entries = info.get("input", {}).get(group, {})
        order = info.get("input_order", {}).get(group, list(entries))
        for name in order:
            if name in entries:
                full = prefix + name
                descriptor = entries[name]
                # VideoHelperSuite adds its upload button in frontend code;
                # its backend declares only a snapshot of available filenames.
                if (info.get("name") in {"VHS_LoadVideo", "VHS_LoadVideoFFmpeg"}
                        and name == "video" and isinstance(descriptor[0], list)):
                    descriptor = [descriptor[0], {**(descriptor[1] if len(descriptor) > 1 else {}),
                                                  "video_upload": True}]
                # Extensions can save a scalar widget in the hidden group.
                # Server-injected PROMPT/UNIQUE_ID fields are plain type names.
                if group == "hidden" and (not isinstance(descriptor, (list, tuple))
                                           or not descriptor
                                           or not is_widget(descriptor)):
                    continue
                kind, options = descriptor[0], descriptor[1] if len(descriptor) > 1 else {}
                if kind == "COMFY_DYNAMICCOMBO_V3":
                    choices = options.get("options", [])
                    yield full, [[option["key"] for option in choices], options], group == "required"
                    chosen = (live or {}).get(full)
                    for option in choices:
                        if live is None or option["key"] == chosen:
                            for child, desc, required in fields({"input": option["inputs"]}, live, full + "."):
                                yield child, desc, required if live is not None else False
                elif kind == "COMFY_AUTOGROW_V3":
                    template = options["template"]
                    names = template.get("names", [template.get("prefix", "") + str(i) for i in range(template.get("max", 0))])
                    children = list(fields({"input": template["input"]}))
                    if children:
                        _, desc, needed = children[0]
                        for index, child in enumerate(names):
                            yield full + "." + child, desc, needed and index < template.get("min", 0)
                else:
                    yield full, descriptor, group == "required"
                    # VideoHelperSuite declares codec-specific saved widgets
                    # alongside the format selector in object_info.
                    for format_name, widgets in options.get("formats", {}).items():
                        if isinstance(widgets, list) and (live is None or live.get(full) == format_name):
                            for widget in widgets:
                                if isinstance(widget, (list, tuple)) and len(widget) >= 2:
                                    yield widget[0], widget[1:3], False


def input_schema(descriptor: list | tuple) -> dict:
    kind = descriptor[0]
    options = descriptor[1] if len(descriptor) > 1 else {}
    if (isinstance(kind, list) or kind == "COMBO") and any(options.get(key) for key in ("image_upload", "audio_upload", "video_upload")):
        # Upload lists change between runs. File existence is checked by the
        # server when the prompt is submitted, not by a stale object_info list.
        schema = {"type": "string", "minLength": 1}
    elif isinstance(kind, list) or kind == "COMBO":
        schema = {"enum": deepcopy(kind if isinstance(kind, list) else options.get("options", []))}
        if options.get("multiselect"):
            schema = {"type": "array", "items": schema, "uniqueItems": True}
    elif kind in SCALARS:
        schema = {"type": SCALARS[kind]}
        if kind in {"INT", "FLOAT"}:
            schema.update({key: options[src] for src, key in (("min", "minimum"), ("max", "maximum"))
                           if src in options})
    else:
        schema = {"type": "array", "prefixItems": [{"type": "string"}, {"type": "integer", "minimum": 0}],
                  "minItems": 2, "maxItems": 2}
    if "default" in options:
        schema["default"] = deepcopy(options["default"])
    if options.get("tooltip"):
        schema["description"] = options["tooltip"]
    return schema


def is_link(value):
    return (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)
            and type(value[1]) is int)


def accepts_type(expected, actual):
    """Comfy ports accept overlapping comma-separated union types."""
    if not isinstance(expected, str):
        return True
    if not isinstance(actual, str):
        return False
    expected_types = {kind.strip() for kind in expected.split(",")}
    actual_types = {kind.strip() for kind in actual.split(",")}
    return bool(expected_types & actual_types or "*" in expected_types | actual_types
                or "COMFY_MATCHTYPE_V3" in expected_types | actual_types)


@dataclass(frozen=True)
class Diagnostic:
    node_id: str
    code: str
    message: str
    input_name: str | None = None


class ComfyWorkflow:
    """Keep the editable document and compile a separate execution graph.

    UI graphs require the server's object_info for widget names and ordering.
    Import and export preserve unknown extension metadata and disabled nodes.
    """

    def __init__(self, document: dict, object_info: dict | None = None):
        if not isinstance(document, dict) or not document:
            raise WorkflowError("workflow must be a nonempty object")
        self.document = deepcopy(document)
        self.object_info = deepcopy(object_info or {})
        self.ui = isinstance(document.get("nodes"), list)
        if self.ui:
            raw_nodes = document["nodes"]
            if any(not isinstance(n, dict) or "id" not in n or "type" not in n for n in raw_nodes):
                raise WorkflowError("UI nodes require id and type")
            self.nodes = {str(n["id"]): n for n in self.document["nodes"]}
            if len(self.nodes) != len(raw_nodes):
                raise WorkflowError("duplicate node IDs")
            self.links = {}
            for link in document.get("links", []):
                if isinstance(link, list) and len(link) >= 6:
                    key, source, slot, target, target_slot, kind = link[:6]
                elif isinstance(link, dict):
                    key, source, slot, target, target_slot, kind = (
                        link[k] for k in ("id", "origin_id", "origin_slot", "target_id", "target_slot", "type")
                    )
                else:
                    raise WorkflowError("unsupported link format")
                if str(key) in self.links:
                    raise WorkflowError("duplicate link IDs")
                self.links[str(key)] = (str(source), slot, str(target), target_slot, kind)
        else:
            prompt = self.document.get("prompt", self.document)
            if not isinstance(prompt, dict) or not prompt or any(
                not isinstance(n, dict) or not isinstance(n.get("class_type"), str)
                or not isinstance(n.get("inputs"), dict) for n in prompt.values()
            ):
                raise WorkflowError("expected a ComfyUI UI workflow or API prompt")
            self.nodes = prompt
            self.links = {}

    def export(self) -> dict:
        return deepcopy(self.document)

    def export_ui(self) -> dict:
        """Create an editable canvas for an API prompt using installed node schemas."""
        if self.ui:
            return self.export()
        prompt = self.compile()
        identifiers = {key: index + 1 for index, key in enumerate(prompt)}
        nodes, links, levels, rows = {}, [], {}, {}

        def level(key):
            if key not in levels:
                parents = [value[0] for value in prompt[key]["inputs"].values() if is_link(value)]
                levels[key] = 1 + max((level(parent) for parent in parents), default=-1)
            return levels[key]

        for key, source in prompt.items():
            info = self.object_info.get(source["class_type"])
            if info is None:
                raise WorkflowError(f"node {key}: export needs object_info for {source['class_type']}")
            inputs, widgets = [], []
            known = set()
            live = deepcopy(source["inputs"])
            for name, descriptor, _ in fields(info, live):
                known.add(name)
                kind, options = descriptor[0], descriptor[1] if len(descriptor) > 1 else {}
                value = source["inputs"].get(name)
                widget = is_widget(descriptor) and not options.get("forceInput")
                if widget:
                    choices = kind if isinstance(kind, list) else options.get("options", [])
                    fallback = choices[0] if choices else {"STRING": "", "BOOLEAN": False}.get(kind if isinstance(kind, str) else "", 0)
                    default = options.get("default", fallback)
                    saved = deepcopy(value) if name in source["inputs"] and not is_link(value) else deepcopy(default)
                    live[name] = saved
                    widgets.append(saved)
                    if options.get("control_after_generate") or name in {"seed", "noise_seed"}:
                        widgets.append("fixed")
                if not widget or is_link(value):
                    port = {"name": name, "type": "COMBO" if isinstance(kind, list) else kind, "link": None}
                    if widget:
                        port["widget"] = {"name": name}
                    inputs.append(port)
            if source["inputs"].keys() - known:
                raise WorkflowError(f"node {key}: refresh object_info for undeclared inputs")
            column = level(key)
            row = rows.get(column, 0)
            rows[column] = row + 1
            outputs = [{"name": (info.get("output_name") or info["output"])[slot],
                        "type": kind, "links": [], "slot_index": slot}
                       for slot, kind in enumerate(info.get("output", []))]
            nodes[key] = {"id": identifiers[key], "type": source["class_type"],
                          "title": source.get("_meta", {}).get("title", source["class_type"]),
                          "pos": [column * 360, row * 300], "size": [300, 220],
                          "flags": {}, "order": len(nodes), "mode": 0,
                          "inputs": inputs, "outputs": outputs, "widgets_values": widgets,
                          "properties": {"Node name for S&R": source["class_type"]}}
        for key, source in prompt.items():
            for name, value in source["inputs"].items():
                port_index = next((index for index, port in enumerate(nodes[key]["inputs"]) if port["name"] == name), None)
                if is_link(value):
                    parent, slot = value
                elif port_index is not None:
                    # A forceInput scalar can be literal in an API prompt. Give
                    # it a real editable Primitive node on the ComfyUI canvas.
                    kind = {int: "INT", float: "FLOAT", bool: "BOOLEAN", str: "STRING"}.get(type(value))
                    if kind is None or not accepts_type(nodes[key]["inputs"][port_index]["type"], kind):
                        raise WorkflowError(f"node {key}.{name}: cannot represent this literal as a canvas input")
                    parent, slot = f"literal_{len(nodes)}", 0
                    while parent in nodes:
                        parent += "_"
                    identifiers[parent] = len(nodes) + 1
                    nodes[parent] = {"id": identifiers[parent], "type": "PrimitiveNode", "title": name,
                                     "pos": [nodes[key]["pos"][0] - 180, nodes[key]["pos"][1] + 250],
                                     "size": [160, 80], "flags": {}, "mode": 0, "order": len(nodes),
                                     "inputs": [], "outputs": [{"name": kind, "type": kind, "links": []}],
                                     "widgets_values": [value], "properties": {}}
                else:
                    continue
                output = nodes[parent]["outputs"][slot]
                identifier = len(links) + 1
                nodes[key]["inputs"][port_index]["link"] = identifier
                output["links"].append(identifier)
                links.append([identifier, identifiers[parent], slot, identifiers[key], port_index, output["type"]])
        document = {"last_node_id": len(nodes), "last_link_id": len(links), "nodes": list(nodes.values()),
                    "links": links, "groups": [], "config": {}, "extra": {}, "version": 0.4}
        # Recompile before returning so unsupported extension layouts fail here.
        rebuilt = ComfyWorkflow(document, self.object_info).compile()
        for key, source in prompt.items():
            for name, value in source["inputs"].items():
                expected = [str(identifiers[value[0]]), value[1]] if is_link(value) else value
                if rebuilt[str(identifiers[key])]["inputs"].get(name) != expected:
                    raise WorkflowError(f"node {key}.{name}: canvas export changed this input")
        return document

    def class_type(self, node_id: str) -> str:
        node = self.nodes[str(node_id)]
        return node["type" if self.ui else "class_type"]

    def _widgets(self, node_id: str) -> dict[str, tuple[Any, int | str]]:
        node = self.nodes[node_id]
        info = self.object_info.get(self.class_type(node_id))
        if info is None:
            raise WorkflowError(f"node {node_id}: install {self.class_type(node_id)} and refresh object_info")
        values = node.get("widgets_values", [])
        if isinstance(values, dict):
            return {name: (deepcopy(values[name]), name) for name, _, _ in fields(info, values) if name in values}
        result, live, index = {}, {}, 0
        for name, descriptor, _ in fields(info, live):
            options = descriptor[1] if len(descriptor) > 1 else {}
            if options.get("forceInput") or not is_widget(descriptor):
                continue
            if index >= len(values):
                raise WorkflowError(f"node {node_id}: missing saved widget {name}")
            result[name] = (deepcopy(values[index]), index)
            live[name] = values[index]
            index += 1
            if options.get("control_after_generate") or name in {"seed", "noise_seed"}:
                if index < len(values) and values[index] in ("fixed", "increment", "decrement", "randomize"):
                    index += 1
        # Extensions may append preview/UI widgets. Preserve these in the UI document.
        return result

    def describe(self) -> list[dict]:
        result = []
        for key, node in self.nodes.items():
            kind = self.class_type(key)
            info = self.object_info.get(kind, {})
            item = {"id": key, "class_type": kind, "title": node.get("title", node.get("_meta", {}).get("title", kind)),
                    "mode": node.get("mode", 0), "inputs": {}, "outputs": info.get("output", []),
                    "available": kind in self.object_info or kind in VIRTUAL or kind in UI_ONLY}
            try:
                defaults = self._widgets(key) if self.ui and kind not in VIRTUAL | UI_ONLY else {}
            except WorkflowError:
                defaults = {}
            for name, descriptor, required in fields(info):
                item["inputs"][name] = {"schema": input_schema(descriptor), "required": required}
                if name in defaults:
                    item["inputs"][name]["value"] = defaults[name][0]
                elif not self.ui and name in node["inputs"]:
                    item["inputs"][name]["value"] = deepcopy(node["inputs"][name])
            result.append(item)
        return result

    def set_input(self, node_id: str, name: str, value: Any):
        node_id = str(node_id)
        node = self.nodes[node_id]
        info = self.object_info.get(self.class_type(node_id))
        live = {key: val for key, (val, _) in self._widgets(node_id).items()} if self.ui else node["inputs"]
        descriptor = next((d for n, d, _ in fields(info or {}, live) if n == name), None)
        if descriptor is None:
            raise WorkflowError(f"node {node_id}: unknown input {name}; refresh object_info")
        Draft202012Validator(input_schema(descriptor)).validate(value)
        if not self.ui:
            node["inputs"][name] = deepcopy(value)
        else:
            if any(port["name"] == name and port.get("link") is not None for port in node.get("inputs", [])):
                raise WorkflowError(f"node {node_id}.{name} is connected; edit its source node")
            widget = self._widgets(node_id).get(name)
            if widget is None:
                raise WorkflowError(f"node {node_id}.{name} has no editable widget")
            options = descriptor[1] if len(descriptor) > 1 else {}
            if options.get("options") and all(isinstance(o, dict) and "inputs" in o for o in options["options"]):
                old = self._widgets(node_id)
                live = {key: val for key, (val, _) in old.items()}
                live[name] = deepcopy(value)
                if isinstance(node["widgets_values"], dict):
                    node["widgets_values"][name] = deepcopy(value)
                else:
                    widgets = []
                    consumed = max((index for _, index in old.values()), default=-1) + 1
                    for key, desc, _ in fields(info, live):
                        kind = desc[0]
                        settings = desc[1] if len(desc) > 1 else {}
                        if settings.get("forceInput") or not is_widget(desc):
                            continue
                        choices = kind if isinstance(kind, list) else settings.get("options", [])
                        default = settings.get("default", choices[0] if choices else 0)
                        live[key] = live.get(key, default)
                        widgets.append(deepcopy(live[key]))
                        if key in old and (settings.get("control_after_generate") or key in {"seed", "noise_seed"}):
                            index = old[key][1] + 1
                            previous = node["widgets_values"]
                            if index < len(previous) and previous[index] in ("fixed", "increment", "decrement", "randomize"):
                                widgets.append(previous[index])
                                consumed = max(consumed, index + 1)
                    widgets.extend(node["widgets_values"][consumed:])
                    node["widgets_values"] = widgets
            else:
                node["widgets_values"][widget[1]] = deepcopy(value)
        return self

    def set_enabled(self, node_id: str, enabled: bool):
        if not self.ui:
            raise WorkflowError("bypass changes require a UI workflow")
        self.nodes[str(node_id)]["mode"] = 0 if enabled else 4
        return self

    def disconnect(self, node_id: str, name: str):
        node = self.nodes[str(node_id)]
        if not self.ui:
            node["inputs"].pop(name, None)
            return self
        port = next((p for p in node.get("inputs", []) if p["name"] == name), None)
        if port is None or port.get("link") is None:
            return self
        link_id = str(port["link"])
        old = self.links.pop(link_id, None)
        self.document["links"] = [link for link in self.document["links"]
                                  if str(link[0] if isinstance(link, list) else link["id"]) != link_id]
        if old and old[0] in self.nodes:
            for output in self.nodes[old[0]].get("outputs", []):
                output["links"] = [key for key in output.get("links", []) or [] if str(key) != link_id]
        port["link"] = None
        return self

    def connect(self, node_id: str, name: str, source_id: str, slot: int):
        node_id, source_id = str(node_id), str(source_id)
        target, source = self.nodes[node_id], self.nodes[source_id]
        info = self.object_info.get(self.class_type(node_id), {})
        descriptor = next((d for n, d, _ in fields(info) if n == name), None)
        output_types = self.object_info.get(self.class_type(source_id), {}).get("output", [])
        if descriptor is None or slot < 0 or slot >= len(output_types):
            raise WorkflowError("connect requires valid input and output ports")
        expected, actual = descriptor[0], output_types[slot]
        if not accepts_type(expected, actual):
            raise WorkflowError(f"{node_id}.{name} expects {expected}, got {actual}")
        if not self.ui:
            target["inputs"][name] = [source_id, slot]
            return self
        self.disconnect(node_id, name)
        ports = target.setdefault("inputs", [])
        port = next((p for p in ports if p["name"] == name), None)
        if port is None:
            port = {"name": name, "type": actual}
            if name in self._widgets(node_id):
                port["widget"] = {"name": name}
            ports.append(port)
        next_id = max([int(k) for k in self.links if k.isdigit()] + [int(self.document.get("last_link_id", 0))]) + 1
        port["link"] = next_id
        while len(source.setdefault("outputs", [])) <= slot:
            index = len(source["outputs"])
            source["outputs"].append({"name": output_types[index], "type": output_types[index], "links": []})
        source["outputs"][slot]["links"] = [*(source["outputs"][slot].get("links") or []), next_id]
        link = (source_id, slot, node_id, ports.index(port), actual)
        self.links[str(next_id)] = link
        record = [next_id, source["id"], slot, target["id"], ports.index(port), actual]
        if self.document.get("links") and isinstance(self.document["links"][0], dict):
            record = dict(zip(("id", "origin_id", "origin_slot", "target_id", "target_slot", "type"), record))
        self.document.setdefault("links", []).append(record)
        self.document["last_link_id"] = next_id
        return self

    def _resolve(self, node_id: str, slot: int, trail: frozenset = frozenset()):
        if (node_id, slot) in trail:
            raise WorkflowError(f"virtual link cycle at node {node_id}")
        trail = trail | {(node_id, slot)}
        node = self.nodes.get(node_id)
        if node is None:
            raise WorkflowError(f"link references missing node {node_id}")
        kind = self.class_type(node_id)
        if node.get("mode", 0) == 2:
            raise WorkflowError(f"connected node {node_id} is muted")
        if kind == "GetNode":
            label = node.get("widgets_values", [None])[0]
            setters = [k for k, n in self.nodes.items() if self.class_type(k) == "SetNode"
                       and n.get("widgets_values", [None])[0] == label]
            if len(setters) != 1:
                raise WorkflowError(f"GetNode {node_id}: expected one SetNode for {label}")
            return self._resolve(setters[0], 0, trail)
        if kind == "PrimitiveNode":
            return deepcopy(node.get("widgets_values", [None])[0])
        if kind in {"SetNode", "Reroute"} or node.get("mode", 0) == 4:
            ports = node.get("inputs", [])
            if kind in {"SetNode", "Reroute"}:
                candidates = [p for p in ports if p.get("link") is not None]
            else:
                outputs = node.get("outputs", [])
                if slot < 0 or slot >= len(outputs):
                    raise WorkflowError(f"node {node_id}: invalid output slot {slot}")
                output_type = outputs[slot].get("type")
                candidates = [p for p in ports if p.get("link") is not None and p.get("type") == output_type]
                if len(candidates) > 1 and slot < len(ports) and ports[slot] in candidates:
                    candidates = [ports[slot]]
            if not candidates and node.get("mode", 0) == 4:
                # Bypassed source nodes (image/audio loaders, for example) have
                # no passthrough input. ComfyUI leaves their consumers unbound.
                return DISCONNECTED
            if len(candidates) != 1:
                raise WorkflowError(f"node {node_id}: bypass has no unambiguous connected input")
            return self._link_value(candidates[0]["link"], trail)
        return [node_id, slot]

    def _link_value(self, link_id, trail=frozenset()):
        link = self.links.get(str(link_id))
        if link is None:
            raise WorkflowError(f"missing link {link_id}")
        return self._resolve(link[0], link[1], trail)

    def compile(self, outputs: list[str] | None = None) -> dict:
        if not self.ui:
            prompt = deepcopy(self.nodes)
        else:
            prompt = {}

            def compile_node(key):
                if key in prompt:
                    return
                if key not in self.nodes:
                    raise WorkflowError(f"requested output or dependency {key} is unavailable")
                node = self.nodes[key]
                kind = self.class_type(key)
                if kind in VIRTUAL | UI_ONLY or node.get("mode", 0) in {2, 4}:
                    return
                inputs = {name: value for name, (value, _) in self._widgets(key).items()}
                for port in node.get("inputs", []):
                    if port.get("link") is not None:
                        value = self._link_value(port["link"])
                        if value is not DISCONNECTED:
                            inputs[port["name"]] = value
                prompt[key] = {"class_type": kind, "inputs": inputs, "_meta": {"title": node.get("title", kind)}}
                for value in inputs.values():
                    if is_link(value):
                        compile_node(value[0])

            for key in self.nodes if outputs is None else map(str, outputs):
                compile_node(key)
        if outputs is not None:
            keep = set()

            def visit(key):
                if key in keep:
                    return
                if key not in prompt:
                    raise WorkflowError(f"requested output or dependency {key} is unavailable")
                keep.add(key)
                for value in prompt[key]["inputs"].values():
                    if is_link(value):
                        visit(value[0])

            for key in outputs:
                visit(str(key))
            prompt = {k: v for k, v in prompt.items() if k in keep}
        problems = self.validate_prompt(prompt)
        if problems:
            raise WorkflowError("; ".join(p.message for p in problems[:12]))
        return prompt

    def validate_prompt(self, prompt: dict) -> list[Diagnostic]:
        problems, visiting, visited = [], set(), set()

        def visit(key):
            if key in visiting:
                problems.append(Diagnostic(key, "cycle", f"execution cycle at node {key}"))
                return
            if key in visited or key not in prompt:
                return
            visiting.add(key)
            node = prompt[key]
            info = self.object_info.get(node["class_type"])
            if self.object_info and info is None:
                problems.append(Diagnostic(key, "missing_node", f"node {key}: install {node['class_type']}"))
            declared = {n: (d, required) for n, d, required in fields(info or {}, node["inputs"])}
            for name, (descriptor, required) in declared.items():
                if required and name not in node["inputs"]:
                    problems.append(Diagnostic(key, "missing_input", f"node {key}: provide {name}", name))
            for name, value in node["inputs"].items():
                if is_link(value):
                    source, slot = value
                    if source not in prompt:
                        problems.append(Diagnostic(key, "missing_source", f"node {key}.{name}: missing source {source}", name))
                    else:
                        source_info = self.object_info.get(prompt[source]["class_type"])
                        if source_info and (slot < 0 or slot >= len(source_info.get("output", []))):
                            problems.append(Diagnostic(key, "invalid_slot", f"node {key}.{name}: invalid source slot", name))
                        elif source_info and name in declared:
                            expected = declared[name][0][0]
                            actual = source_info["output"][slot]
                            if not accepts_type(expected, actual):
                                problems.append(Diagnostic(key, "type_mismatch", f"node {key}.{name}: expects {expected}, got {actual}", name))
                        visit(source)
                elif name in declared:
                    for error in Draft202012Validator(input_schema(declared[name][0])).iter_errors(value):
                        problems.append(Diagnostic(key, "invalid_value", f"node {key}.{name}: {error.message[:200]}", name))
            visiting.remove(key)
            visited.add(key)

        for key in prompt:
            visit(key)
        return problems
