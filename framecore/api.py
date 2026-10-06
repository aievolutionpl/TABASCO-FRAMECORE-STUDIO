"""Transport-independent API used by HTTP and MCP."""
from .commands import storyboard
from .model import EditorError
from .motion import registry
from .providers import PROVIDERS

READS = {"get_media_analysis", "get_project", "get_selection", "get_timeline", "get_frame_context", "list_assets", "list_projects", "list_motion", "get_history", "get_providers", "get_job", "preview", "list_templates", "list_icons", "list_library", "list_fonts", "list_backgrounds", "get_editing_guide", "inspect_project", "capture_frame"}
WRITES = {"add_scene", "duplicate_scene", "add_text", "add_video", "add_image", "add_audio", "add_caption", "add_shape",
          "move_element", "resize_element", "set_property", "trim_clip", "split_clip", "move_clip", "delete_clip", "apply_motion",
          "set_brand", "set_format", "style_captions", "set_track", "assemble_storyboard", "rename_project",
          "undo", "redo", "propose_changes", "apply_proposal", "cancel_proposal", "set_selection", "set_playhead",
          "add_icon", "add_library_asset", "set_background", "apply_template", "duplicate_clip", "set_audio", "set_keyframes", "set_duration"}
FIELDS = {
    "get_media_analysis": {"asset_id": "string"},
    "analyze_media": {"asset_id": "string"},
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
READS.update({"get_production_status", "get_review", "get_motion_playbook", "get_quality_report", "resolve_frame_time", "list_reviews"})
WRITES.update({"set_production_contract", "set_scene_beat", "annotate_story_beats", "apply_motion_rules"})
FIELDS.update({
    "set_production_contract": {"contract":"object"}, "set_scene_beat":{"scene_id":"string", "beat":"object"},
    "create_review":{"times":"array"}, "get_review":{"review_id":"string"},
    "review_verdict":{"review_id":"string", "verdict":"string", "checklist":"object", "notes":"string"},
    "create_format_variant":{"format":"string"}, "package_delivery":{"job_id":"string"},
    "resolve_frame_time":{"spec":"string"}, "create_motion_strip":{"start":"string","end":"string","count":"integer"},
    "compare_reviews":{"baseline_id":"string","review_id":"string","threshold":"integer","max_diff_ratio":"number"},
    "analyze_export":{"job_id":"string", "profile":"string"}, "get_quality_report":{"job_id":"string"},
})
FIELDS["apply_motion"]["easing"]="string"
WRITES.update({"apply_exit", "set_canvas_fx", "set_scene_transition"})
FIELDS.update({"apply_exit": {"element_id": "string", "exit_id": "string", "duration": "number", "easing": "string"},
               "set_canvas_fx": {"fx": "object"},
               "set_scene_transition": {"scene_id": "string", "transition_id": "string", "duration": "number"}})

for kind in ("text", "video", "image", "audio", "caption", "shape"):
    FIELDS["add_" + kind] = {"trackId":"string", "assetId": "string", "text": "string", "start": "number", "duration": "number", "style": "object",
        "x":"number", "y":"number", "width":"number", "height":"number", "scale":"number", "rotation":"number", "opacity":"number", "motion":None, "exit":None}


READS.update({"get_storytelling_playbook","plan_visual_lesson","get_lesson_status"})
WRITES.update({"replace_clip_asset","add_track","set_project_fps","assemble_visual_lesson","set_learning_brief","set_scene_learning"})
FIELDS.update({
    "replace_clip_asset":{"element_id":"string","asset_id":"string","fit_source":"boolean"},
    "add_track":{"kind":"string","name":"string"},"set_project_fps":{"fps":"integer"},
    "plan_visual_lesson":{"brief":"object","duration":"number"},
    "assemble_visual_lesson":{"brief":"object","scenes":"array","duration":"number","replace":"boolean","paper_style":"boolean"},
    "set_learning_brief":{"brief":"object"},"set_scene_learning":{"scene_id":"string","lesson":"object"},
})

BRAND_TOOLS = {"list_brand_profiles", "get_brand_profile", "save_brand_profile", "delete_brand_profile", "apply_brand_profile", "remove_brand_asset", "upload_brand_asset"}
READS.update({"list_brand_profiles", "get_brand_profile"})
FIELDS.update({
    "get_brand_profile": {"brand_id":"string"},
    "save_brand_profile": {"brand_id":"string", "expected_version":"integer", "profile":"object"},
    "delete_brand_profile": {"brand_id":"string", "expected_version":"integer"},
    "remove_brand_asset": {"brand_id":"string", "expected_version":"integer", "asset_id":"string"},
    "upload_brand_asset": {"brand_id":"string", "expected_version":"integer", "source_file":"string", "role":"string"},
    "apply_brand_profile": {"brand_id":"string", "expected_version":"integer", "restyle":"boolean"},
})

class API:
    def __init__(self, store, jobs):
        self.store, self.jobs = store, jobs
        from .media import MediaEngine
        self.media = MediaEngine(store)

    def call(self, name, args=None, actor="agent"):
        args = dict(args or {})
        pid = args.pop("project_id", None)
        revision = args.pop("expected_revision", None)
        if name in {"get_storytelling_playbook","plan_visual_lesson","get_lesson_status"}:
            from .storytelling import PLAYBOOK,plan,status
            if name=="get_storytelling_playbook":return PLAYBOOK
            if name=="plan_visual_lesson":return plan(args['brief'],args.get('duration',self.store.read(pid)['project']['duration']))
            return status(self.store.read(pid)['project'])
        if name in {"get_media_analysis", "analyze_media"}:
            method = self.media.start if name == "analyze_media" else self.media.status
            return method(pid, args["asset_id"])
        if name in BRAND_TOOLS:
            from .brands import BrandLibrary
            brands = BrandLibrary(self.store)
            if name == "list_brand_profiles": return brands.list()
            if name == "get_brand_profile": return brands.get(args["brand_id"])
            if name == "save_brand_profile": return brands.save(args["profile"], args.get("brand_id"), args.get("expected_version"))
            if name == "delete_brand_profile": return brands.delete(args["brand_id"], args["expected_version"])
            if name == "upload_brand_asset":
                from pathlib import Path
                source = Path(args["source_file"]).resolve()
                import_root = (self.store.root.parent / "imports").resolve()
                if not source.is_relative_to(import_root) or not source.is_file() or source.stat().st_size > 20_000_000:
                    raise EditorError("Umieść obraz do 20 MB w katalogu imports przy katalogu projektów")
                return brands.upload(args["brand_id"], args["expected_version"], source.read_bytes(), source.name, args.get("role", "reference"))
            if name == "remove_brand_asset": return brands.remove_asset(args["brand_id"], args["expected_version"], args["asset_id"])
            return brands.apply(args["brand_id"], args["expected_version"], pid, revision, args.get("restyle",False), actor)
        if name == "list_projects": return {"projects": self.store.list()}
        if name == "list_motion":
            from .motion import exits
            from .production import EASINGS
            return {"components": registry(), "exits": exits(), "easings": sorted(EASINGS)}
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
        if name == "resolve_frame_time":
            from .motion_evidence import resolve_time
            p=self.store.read(pid)["project"]
            return {"time":resolve_time(p,args["spec"]),"revision":p["revision"]}
        if name == "create_motion_strip":
            from .motion_evidence import strip
            return strip(self.store,pid,revision,args.get("start","0s"),args.get("end","end"),args.get("count",12))
        if name == "list_reviews":
            from .motion_evidence import list_reviews
            return list_reviews(self.store,pid)
        if name == "compare_reviews":
            from .motion_evidence import compare
            return compare(self.store,pid,args["baseline_id"],args["review_id"],args.get("threshold",16),args.get("max_diff_ratio",.001))
        if name == "get_motion_playbook":
            from .playbook import PLAYBOOK
            return PLAYBOOK
        if name in {"analyze_export", "get_quality_report"}:
            from .quality import analyze, get_report
            if name == "analyze_export": return analyze(self.store,self.jobs,pid,args["job_id"],args.get("profile","calm"))
            return get_report(self.store,self.jobs,pid,args["job_id"])
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
            from .media_import import import_asset
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
        if name == "get_production_status":
            from .production import status
            return status(self.store.read(pid)["project"], self.store.directory(pid))
        if name == "create_review":
            from .review import create_review
            return create_review(self.store, pid, revision, args.get("times"))
        if name == "get_review":
            from .review import load_review
            report = load_review(self.store.directory(pid), args["review_id"])
            from .production import fingerprint
            p = self.store.read(pid)["project"]
            report["current"] = report["fingerprint"] == fingerprint(p)
            from .production import asset_manifest
            report["current"] = report["current"] and report["assetHashes"] == {a["id"]:a["sha256"] for a in asset_manifest(p,self.store.directory(pid))}
            return report
        if name == "review_verdict":
            from .review import verdict
            return verdict(self.store, pid, revision, args["review_id"], args["verdict"], args.get("checklist"), args.get("notes", ""), actor)
        if name == "create_format_variant": return self.store.create_variant(pid, revision, args["format"])
        if name == "package_delivery":
            from .delivery import package
            return package(self.store, self.jobs, pid, args["job_id"])
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
        names = sorted(READS | WRITES | BRAND_TOOLS | {"analyze_media", "create_project", "add_asset", "plan_storyboard", "render", "export", "generate_image", "generate_video", "generate_audio", "generate_voice", "transcribe", "create_review", "review_verdict", "create_format_variant", "package_delivery", "analyze_export", "create_motion_strip", "compare_reviews"})
        result = []
        for name in names:
            props = {"project_id": {"type": "string"}, "expected_revision": {"type": "integer"}}
            props.update({k: ({"type": v} if v else {}) for k,v in FIELDS.get(name, {}).items()})
            if name in {"render", "export"}: props["quality"] = {"type": "string", "enum": ["final", "draft"]}
            if name == "get_job": props["job_id"] = {"type": "string"}
            if name == "add_asset": props.update(source_file={"type": "string"}, role={"type": "string"})
            if name == "save_brand_profile":
                from .brands import TEXT_FIELDS
                props["profile"] = {"type":"object", "additionalProperties":False, "properties": {
                    **{k:{"type":"string"} for k in TEXT_FIELDS},
                    "businessType":{"type":"string", "enum":["services","products","both"]},
                    "font":{"type":"string", "description":"Font z list_fonts lub Arial/Georgia/Verdana/Times New Roman"},
                    "colors":{"type":"object", "additionalProperties":False, "required":["background","text","accent"],
                        "properties":{k:{"type":"string","pattern":"^#[0-9a-fA-F]{6}$"} for k in ("background","text","accent")}},
                    **{field:{"type":"array", "maxItems":60, "items":{"type":"object", "additionalProperties":False,
                        "required":keys, "properties":{k:{"type":"string"} for k in keys}}}
                       for field,keys in [("products",["name","description","url"]),("sources",["url","note"])]},
                }}
            if name == "create_project": props.update(name={"type": "string"}, format={"type": "string"}, duration={"type": "number"}, brief={"type": "string"}, workflow={"type": "string"})
            if name == "plan_storyboard": props.update(title={"type": "string"}, workflow={"type": "string"}, template_id={"type": "string"})
            if name.startswith("generate_") or name == "transcribe": props.update(provider_id={"type": "string"}, prompt={"type": "string"})
            required = [] if name in {"list_projects", "list_motion", "list_templates", "list_icons", "list_library", "list_fonts", "list_backgrounds", "get_editing_guide", "get_motion_playbook", "get_providers", "create_project", "get_job"} else ["project_id"]
            if name=="get_storytelling_playbook":required=[]
            if name in BRAND_TOOLS - {"apply_brand_profile"}: required = []
            if name in BRAND_TOOLS - {"list_brand_profiles", "save_brand_profile"}: required += ["brand_id", "expected_version"] if name != "get_brand_profile" else ["brand_id"]
            if name == "save_brand_profile": required.append("profile")
            if name == "remove_brand_asset": required.append("asset_id")
            if name == "upload_brand_asset": required.append("source_file")
            if name == "apply_brand_profile": required.append("expected_revision")
            if name in WRITES - {"set_selection", "set_playhead"} or name in {"render", "export", "add_asset", "create_review", "create_motion_strip", "review_verdict", "create_format_variant"}: required.append("expected_revision")
            if name in {"analyze_export", "get_quality_report", "package_delivery"}: required.append("job_id")
            if name == "resolve_frame_time": required.append("spec")
            if name == "compare_reviews": required += ["baseline_id","review_id"]
            required += {"replace_clip_asset":["asset_id"],"add_track":["kind","name"],"set_project_fps":["fps"],
                         "plan_visual_lesson":["brief"],"assemble_visual_lesson":["brief"],"set_learning_brief":["brief"],"set_scene_learning":["scene_id","lesson"]}.get(name,[])
            if name == "analyze_export": props["profile"] = {"type":"string", "enum":["calm","punchy","mute"]}
            if name in {"get_media_analysis", "analyze_media"}: required.append("asset_id")
            required += {"move_clip": ["start"], "move_element": ["x", "y"], "resize_element": ["width", "height"],
                         "set_property": ["property", "value"], "trim_clip": ["duration"], "apply_motion": ["motion_id"], "apply_exit": ["exit_id"], "set_canvas_fx": ["fx"], "set_scene_transition": ["scene_id", "transition_id"],
                         "set_format": ["format"], "set_brand": ["brand"], "style_captions": ["style"],
                         "assemble_storyboard": ["scenes"], "propose_changes": ["commands"],
                         "apply_proposal": ["proposal_id"], "cancel_proposal": ["proposal_id"],
                         "set_playhead": ["time"], "set_selection": ["element_ids"], "get_job": ["job_id"],
                         "add_asset": ["source_file"], "duplicate_scene": ["scene_id"], "add_icon":["icon_id"],
                         "apply_template":["template_id"], "add_library_asset":["asset_id"], "set_background":["background_id"], "set_audio":["audio"], "set_keyframes":["keyframes"], "set_duration":["duration"]}.get(name, [])
            result.append({"name": name, "description": name.replace("_", " ") + ". Wspólny projekt i historia; przed zmianą odczytaj aktualną rewizję.",
                           "inputSchema": {"type": "object", "properties": props, "required": required},
                           "annotations": {"readOnlyHint": name in READS, "destructiveHint": name in {"delete_clip", "assemble_storyboard", "delete_brand_profile", "remove_brand_asset"}}})
        return result
