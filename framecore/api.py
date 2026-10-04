"""Transport-independent API used by HTTP and MCP."""
from .commands import storyboard
from .model import EditorError
from .motion import registry
from .providers import PROVIDERS

READS = {"get_project", "get_selection", "get_timeline", "get_frame_context", "list_assets", "list_projects", "list_motion", "get_history", "get_providers", "get_job", "preview", "list_templates", "list_icons", "list_library", "list_fonts", "list_backgrounds", "get_editing_guide", "inspect_project", "capture_frame"}
WRITES = {"add_scene", "duplicate_scene", "add_text", "add_video", "add_image", "add_audio", "add_caption", "add_shape",
          "move_element", "resize_element", "set_property", "trim_clip", "split_clip", "move_clip", "delete_clip", "apply_motion",
          "set_brand", "set_format", "style_captions", "set_track", "assemble_storyboard", "rename_project",
          "undo", "redo", "propose_changes", "apply_proposal", "cancel_proposal", "set_selection", "set_playhead",
          "add_icon", "add_library_asset", "set_background", "apply_template", "duplicate_clip", "set_audio", "set_keyframes", "set_duration"}
FIELDS = {
    "add_library_asset": {"asset_id":"string", "start":"number", "duration":"number", "x":"number", "y":"number", "width":"number", "height":"number"},
    "set_background": {"background_id":"string", "animated":"boolean"},
    "add_icon": {"icon_id":"string", "start":"number", "duration":"number", "x":"number", "y":"number", "width":"number", "height":"number"},
    "apply_template": {"template_id":"string", "title":"string", "replace":"boolean"},
    "duplicate_clip": {"element_id":"string", "start":"number"},
    "set_audio": {"element_id":"string", "audio":"object"},
    "set_keyframes": {"element_id":"string", "keyframes":"array"},
    "set_duration": {"duration":"number"},
    "capture_frame": {"time":"number"},
    "add_text": {"text": "string", "start": "number", "duration": "number"},
    "move_clip": {"element_id": "string", "start": "number", "track_id": "string"},
    "move_element": {"element_id": "string", "x": "number", "y": "number"},
    "resize_element": {"element_id": "string", "width": "number", "height": "number"},
    "set_property": {"element_id": "string", "property": "string", "value": None},
    "trim_clip": {"element_id": "string", "start": "number", "duration": "number"},
    "split_clip": {"element_id": "string", "time": "number"},
    "delete_clip": {"element_id": "string"},
    "apply_motion": {"element_id": "string", "motion_id": "string", "duration": "number"},
    "set_format": {"format": "string"},
    "set_brand": {"brand": "object", "restyle": "boolean"},
    "style_captions": {"style": "object"},
    "set_track": {"track_id": "string", "property": "string", "value": "boolean"},
    "set_selection": {"element_ids": "array"}, "set_playhead": {"time": "number"},
    "propose_changes": {"commands": "array", "description": "string"},
    "apply_proposal": {"proposal_id": "string"},
    "cancel_proposal": {"proposal_id": "string"},
    "assemble_storyboard": {"scenes": "array", "replace": "boolean", "template_id":"string"},
    "add_scene": {"name": "string", "start": "number", "duration": "number", "message": "string"},
    "duplicate_scene": {"scene_id": "string", "start": "number"},
    "rename_project": {"name": "string"},
}
for kind in ("video", "image", "audio", "caption", "shape"):
    FIELDS["add_" + kind] = {"assetId": "string", "text": "string", "start": "number", "duration": "number", "style": "object"}


class API:
    def __init__(self, store, jobs):
        self.store, self.jobs = store, jobs

    def call(self, name, args=None, actor="agent"):
        args = dict(args or {})
        pid = args.pop("project_id", None)
        revision = args.pop("expected_revision", None)
        if name == "list_projects": return {"projects": self.store.list()}
        if name == "list_motion": return {"components": registry()}
        if name == "list_templates":
            from .templates import catalog
            return {"templates": catalog()}
        if name == "list_icons":
            from .library import catalog
            return {"icons": catalog("icon")}
        if name == "list_library":
            from .library import catalog
            return {"assets": catalog()}
        if name == "list_fonts":
            from .library import fonts
            return {"fonts": fonts()}
        if name == "list_backgrounds":
            from .backgrounds import catalog
            return {"backgrounds": catalog()}
        if name == "get_editing_guide":
            from .inspection import GUIDE
            return {"instructions": GUIDE}
        if name == "inspect_project":
            from .inspection import inspect
            return inspect(self.store.read(pid)["project"])
        if name == "capture_frame":
            from .inspection import capture
            return capture(self.store, pid, args.get("time"))
        if name == "get_providers": return {"providers": PROVIDERS.describe()}
        if name == "get_job": return self.jobs.get(args["job_id"])
        if name == "create_project": return self.store.create(args.get("name", "Nowy projekt"), args.get("format", "9:16"), args.get("duration", 15), args.get("brief", ""), args.get("workflow", "Premiera produktu"))
        if name == "add_asset":
            from pathlib import Path
            from .server import import_asset
            source = Path(args["source_file"]).resolve()
            import_root = (self.store.root.parent / "imports").resolve()
            if not source.is_relative_to(import_root) or not source.is_file():
                raise EditorError(f"Umieść materiały w katalogu importu: {import_root}")
            return import_asset(self.store, pid, source.read_bytes(), source.name, args.get("role", "media"), revision, actor)
        if name == "plan_storyboard":
            p = self.store.read(pid)["project"]
            from .templates import template_scenes
            scenes = template_scenes(args.get("template_id", "product"), p["duration"], args.get("title",p["metadata"]["name"]))
            return {"scenes": scenes, "template_id":args.get("template_id", "product"), "method": "deterministic_starter", "note": "Edytowalny plan startowy; bez wywołania modelu językowego."}
        if name.startswith("generate_") or name == "transcribe":
            return PROVIDERS.generate(args.get("provider_id"), name.removeprefix("generate_"), args)
        if name in {"render", "export"}: return self.jobs.start(pid, revision, args.get("quality", "final"))
        if name == "get_project": return self.store.read(pid)
        if name in {"get_selection", "get_frame_context", "preview"}:
            context = self.store.context(pid)
            if name == "preview": context["composition"] = f"/composition/{pid}"
            return context
        if name == "get_timeline":
            p = self.store.read(pid)["project"]
            return {"revision": p["revision"], "tracks": p["tracks"], "elements": p["elements"], "scenes": p["scenes"], "duration": p["duration"]}
        if name == "list_assets": return {"assets": self.store.read(pid)["project"]["assets"]}
        if name == "get_history":
            s = self.store.read(pid)
            return {"history": s["history"], "cursor": s["cursor"], "canUndo": s["canUndo"], "canRedo": s["canRedo"]}
        if name in WRITES:
            return self.store.execute(pid, name, args, revision, actor)
        raise EditorError(f"Nieznane narzędzie: {name}", "unknown_tool")

    def tools(self):
        names = sorted(READS | WRITES | {"create_project", "add_asset", "plan_storyboard", "render", "export", "generate_image", "generate_video", "generate_audio", "generate_voice", "transcribe"})
        result = []
        for name in names:
            props = {"project_id": {"type": "string"}, "expected_revision": {"type": "integer"}}
            props.update({k: ({"type": v} if v else {}) for k,v in FIELDS.get(name, {}).items()})
            if name in {"render", "export"}: props["quality"] = {"type": "string", "enum": ["final", "draft"]}
            if name == "get_job": props["job_id"] = {"type": "string"}
            if name == "add_asset": props.update(source_file={"type": "string"}, role={"type": "string"})
            if name == "create_project": props.update(name={"type": "string"}, format={"type": "string"}, duration={"type": "number"}, brief={"type": "string"}, workflow={"type": "string"})
            if name == "plan_storyboard": props.update(title={"type": "string"}, workflow={"type": "string"}, template_id={"type": "string"})
            if name.startswith("generate_") or name == "transcribe": props.update(provider_id={"type": "string"}, prompt={"type": "string"})
            required = [] if name in {"list_projects", "list_motion", "list_templates", "list_icons", "list_library", "list_fonts", "list_backgrounds", "get_editing_guide", "get_providers", "create_project", "get_job"} else ["project_id"]
            if name in WRITES - {"set_selection", "set_playhead"} or name in {"render", "export", "add_asset"}: required.append("expected_revision")
            required += {"move_clip": ["start"], "move_element": ["x", "y"], "resize_element": ["width", "height"],
                         "set_property": ["property", "value"], "trim_clip": ["duration"], "apply_motion": ["motion_id"],
                         "set_format": ["format"], "set_brand": ["brand"], "style_captions": ["style"],
                         "assemble_storyboard": ["scenes"], "propose_changes": ["commands"],
                         "apply_proposal": ["proposal_id"], "cancel_proposal": ["proposal_id"],
                         "set_playhead": ["time"], "set_selection": ["element_ids"], "get_job": ["job_id"],
                         "add_asset": ["source_file"], "duplicate_scene": ["scene_id"], "add_icon":["icon_id"],
                         "apply_template":["template_id"], "add_library_asset":["asset_id"], "set_background":["background_id"], "set_audio":["audio"], "set_keyframes":["keyframes"], "set_duration":["duration"]}.get(name, [])
            result.append({"name": name, "description": name.replace("_", " ") + ". Wspólny projekt i historia; przed zmianą odczytaj aktualną rewizję.",
                           "inputSchema": {"type": "object", "properties": props, "required": required},
                           "annotations": {"readOnlyHint": name in READS, "destructiveHint": name in {"delete_clip", "assemble_storyboard"}}})
        return result
