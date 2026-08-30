#!/usr/bin/env python3
"""LTW Depth Style — viral depth-map hit, on the clip under the playhead.

After Effects tutorial this copies:
  https://www.youtube.com/watch?v=ZbM2ZWPgDBg
  BCC+ Depth Map ML, inverted so the subject is dark and the background is light,
  fading/cutting in on the impact (goal, punch, bass drop).

In Resolve:
  1. Park the playhead on the hit, on the clip you want.
  2. Workspace -> Scripts -> Edit -> ltw_depth_style
  3. Overlay (default) copies the clip to the track above from the playhead
     onward so the original stays normal until the switch. In-place grades the
     original and dissolves to the look at the playhead.

Studio Depth Map is used when the Fusion node exists. Free Resolve falls back
to a stylized luma-contrast invert that reads as the same graphic look.

This file is standalone so Resolve's Python does not need the LTW venv.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


def _load_helpers():
    here = Path(__file__).resolve().parent
    candidates = [
        here / "ltw_depth_lib.py",
        here.parent / "ltw_resolve" / "resolve" / "depth_style.py",
    ]
    helper = next((p for p in candidates if p.exists()), None)
    if helper is None:
        raise RuntimeError(
            "Missing helper module. Keep this script in the LTW repo "
            "(resolve_scripts/ltw_depth_style.py) or copy "
            "ltw_resolve/resolve/depth_style.py next to it as ltw_depth_lib.py."
        )
    spec = importlib.util.spec_from_file_location("ltw_depth_style_helpers", helper)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


H = _load_helpers()


def _get_resolve():
    try:
        import DaVinciResolveScript as dvr
    except ImportError:
        sys.path.insert(
            0,
            "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
        )
        try:
            import DaVinciResolveScript as dvr
        except ImportError as e:
            raise RuntimeError(
                "DaVinciResolveScript not found. Run this from Resolve: "
                "Workspace -> Scripts -> Edit -> ltw_depth_style"
            ) from e
    resolve = dvr.scriptapp("Resolve")
    if not resolve:
        raise RuntimeError("Could not connect to DaVinci Resolve (is it open?)")
    return resolve


def _bmd():
    if "bmd" in globals() and globals()["bmd"] is not None:
        return globals()["bmd"]
    try:
        import BlackmagicFusion as bmd  # type: ignore

        return bmd
    except ImportError:
        return None


def _prompt(resolve, opts: H.DepthStyleOptions) -> H.DepthStyleOptions | None:
    """Fusion UI dialog. Returns None if the user cancels."""
    fusion = resolve.Fusion()
    bmd = _bmd()
    if fusion is None or bmd is None:
        return opts
    ui = fusion.UIManager
    if ui is None:
        return opts
    disp = bmd.UIDispatcher(ui)
    win = disp.AddWindow(
        {
            "ID": "LTWDepthStyle",
            "WindowTitle": "LTW Depth Style",
            "Geometry": [120, 120, 520, 420],
        },
        [
            ui.VGroup(
                {"Spacing": 8, "Weight": 1},
                [
                    ui.Label(
                        {
                            "Text": "Depth-map hit  ·  park playhead on the goal / punch / drop",
                            "Weight": 0,
                        }
                    ),
                    ui.Label(
                        {
                            "Text": "Uses the video clip under the playhead.",
                            "Weight": 0,
                        }
                    ),
                    ui.HGroup(
                        {"Weight": 0},
                        [
                            ui.Label({"Text": "Apply", "Weight": 0.35}),
                            ui.ComboBox({"ID": "mode", "Weight": 0.65}),
                        ],
                    ),
                    ui.HGroup(
                        {"Weight": 0},
                        [
                            ui.Label({"Text": "Switch", "Weight": 0.35}),
                            ui.ComboBox({"ID": "switch", "Weight": 0.65}),
                        ],
                    ),
                    ui.HGroup(
                        {"Weight": 0},
                        [
                            ui.Label({"Text": "Engine", "Weight": 0.35}),
                            ui.ComboBox({"ID": "engine", "Weight": 0.65}),
                        ],
                    ),
                    ui.HGroup(
                        {"Weight": 0},
                        [
                            ui.Label({"Text": "Punch zoom %", "Weight": 0.35}),
                            ui.SpinBox(
                                {
                                    "ID": "zoom",
                                    "Value": int(round((opts.zoom - 1.0) * 100)),
                                    "Minimum": 0,
                                    "Maximum": 40,
                                    "Weight": 0.65,
                                }
                            ),
                        ],
                    ),
                    ui.HGroup(
                        {"Weight": 0},
                        [
                            ui.Label({"Text": "Fade frames", "Weight": 0.35}),
                            ui.SpinBox(
                                {
                                    "ID": "fade",
                                    "Value": opts.fade_frames,
                                    "Minimum": 1,
                                    "Maximum": 48,
                                    "Weight": 0.65,
                                }
                            ),
                        ],
                    ),
                    ui.CheckBox(
                        {
                            "ID": "invert",
                            "Text": "Invert (subject dark, background light)",
                            "Checked": opts.invert,
                            "Weight": 0,
                        }
                    ),
                    ui.CheckBox(
                        {
                            "ID": "compare",
                            "Text": "Compare: Free + Studio copies on two tracks",
                            "Checked": opts.compare,
                            "Weight": 0,
                        }
                    ),
                    ui.Label(
                        {
                            "Text": "Fusion look works in Free Resolve (no Depth Map plugin).\n"
                            "Studio Depth Map is optional and closer to BCC+ Depth Map ML.",
                            "Weight": 1,
                        }
                    ),
                    ui.HGroup(
                        {"Weight": 0},
                        [
                            ui.Button({"ID": "cancel", "Text": "Cancel"}),
                            ui.Button({"ID": "ok", "Text": "Apply"}),
                        ],
                    ),
                ],
            )
        ],
    )
    itm = win.GetItems()
    itm["mode"].AddItem("Copy on track above (keep original until playhead)")
    itm["mode"].AddItem("Change the original clip")
    itm["mode"].CurrentIndex = 0 if opts.mode == "overlay" else 1
    itm["switch"].AddItem("Cut at playhead")
    itm["switch"].AddItem("Fade at playhead")
    itm["switch"].AddItem("Whole clip (no switch)")
    itm["switch"].CurrentIndex = {"cut": 0, "fade": 1, "whole": 2}.get(opts.switch, 0)
    itm["engine"].AddItem("Fusion look — works in Free Resolve")
    itm["engine"].AddItem("Studio Depth Map — Studio only")
    itm["engine"].AddItem("Auto (Studio if available, else Fusion)")
    itm["engine"].CurrentIndex = {"stylized": 0, "studio": 1, "auto": 2}.get(
        opts.engine, 0
    )

    result = {"ok": False}

    def _ok(_ev=None):
        result["ok"] = True
        disp.ExitLoop()

    def _cancel(_ev=None):
        result["ok"] = False
        disp.ExitLoop()

    win.On.ok.Clicked = _ok
    win.On.cancel.Clicked = _cancel
    win.On.LTWDepthStyle.Close = _cancel
    win.Show()
    disp.RunLoop()
    win.Hide()
    if not result["ok"]:
        return None
    mode = "overlay" if itm["mode"].CurrentIndex == 0 else "inplace"
    switch = ("cut", "fade", "whole")[int(itm["switch"].CurrentIndex)]
    engine = ("stylized", "studio", "auto")[int(itm["engine"].CurrentIndex)]
    zoom = 1.0 + (float(itm["zoom"].Value) / 100.0)
    return H.DepthStyleOptions(
        mode=mode,
        switch=switch,
        invert=bool(itm["invert"].Checked),
        engine=engine,
        zoom=zoom,
        fade_frames=int(itm["fade"].Value),
        compare=bool(itm["compare"].Checked),
    ).normalized()


def _fps(timeline) -> float:
    try:
        raw = timeline.GetSetting("timelineFrameRate")
        if raw:
            return float(raw)
    except Exception:
        pass
    return 24.0


def _playhead_frame(timeline) -> int:
    """Absolute timeline frame, same units as TimelineItem.GetStart()."""
    fps = _fps(timeline)
    try:
        play = timeline.GetCurrentTimecode() or "00:00:00:00"
        return H.parse_timecode(play, fps)
    except Exception:
        return 0


def _track_of(timeline, item) -> int:
    try:
        info = item.GetTrackTypeAndIndex()
        if info and len(info) >= 2 and str(info[0]).lower().startswith("video"):
            return int(info[1])
    except Exception:
        pass
    uid = None
    try:
        uid = item.GetUniqueId()
    except Exception:
        pass
    count = int(timeline.GetTrackCount("video") or 0)
    for i in range(1, count + 1):
        for clip in timeline.GetItemListInTrack("video", i) or []:
            try:
                if uid and clip.GetUniqueId() == uid:
                    return i
            except Exception:
                pass
            if clip is item:
                return i
    return 1


def _occupied_ranges(timeline) -> list[tuple[int, int, int]]:
    out = []
    count = int(timeline.GetTrackCount("video") or 0)
    for i in range(1, count + 1):
        for clip in timeline.GetItemListInTrack("video", i) or []:
            start = int(clip.GetStart())
            dur = int(clip.GetDuration())
            out.append((i, start, start + dur))
    return out


def _clip_at_playhead(timeline, frame):
    item = None
    try:
        item = timeline.GetCurrentVideoItem()
    except Exception:
        item = None
    if item is not None:
        return item
    count = int(timeline.GetTrackCount("video") or 0)
    for i in range(1, count + 1):
        for clip in timeline.GetItemListInTrack("video", i) or []:
            start = int(clip.GetStart())
            end = start + int(clip.GetDuration())
            if start <= frame < end:
                return clip
    return None


def _copy_sizing(src, dst, extra_zoom: float) -> None:
    try:
        props = src.GetProperty() or {}
    except Exception:
        props = {}
    for key in (
        "Pan",
        "Tilt",
        "ZoomX",
        "ZoomY",
        "ZoomGang",
        "RotationAngle",
        "AnchorPointX",
        "AnchorPointY",
        "Pitch",
        "Yaw",
        "FlipX",
        "FlipY",
        "CropLeft",
        "CropRight",
        "CropTop",
        "CropBottom",
    ):
        if key in props:
            try:
                dst.SetProperty(key, props[key])
            except Exception:
                pass
    if extra_zoom and extra_zoom != 1.0:
        try:
            zx = float(dst.GetProperty("ZoomX") or 1.0)
            zy = float(dst.GetProperty("ZoomY") or zx)
            dst.SetProperty("ZoomX", zx * extra_zoom)
            dst.SetProperty("ZoomY", zy * extra_zoom)
        except Exception:
            pass


def _find_io(comp):
    media_in = media_out = None
    try:
        tools = comp.GetToolList(False) or {}
    except Exception:
        tools = {}
    values = tools.values() if isinstance(tools, dict) else list(tools)
    for tool in values:
        try:
            attrs = tool.GetAttrs() or {}
        except Exception:
            attrs = {}
        rid = str(attrs.get("TOOLS_RegID") or attrs.get("TOOLB_RegID") or "")
        name = str(attrs.get("TOOLS_Name") or "")
        if rid == "MediaIn" or name.startswith("MediaIn"):
            media_in = tool
        elif rid == "MediaOut" or name.startswith("MediaOut"):
            media_out = tool
    if media_in is None:
        media_in = getattr(comp, "MediaIn1", None) or comp.FindTool("MediaIn1")
    if media_out is None:
        media_out = getattr(comp, "MediaOut1", None) or comp.FindTool("MediaOut1")
    return media_in, media_out


def _add_tool(comp, ids, x, y):
    if isinstance(ids, str):
        ids = [ids]
    for tool_id in ids:
        try:
            tool = comp.AddTool(tool_id, x, y)
            if tool is not None:
                return tool
        except Exception:
            continue
    return None


def _set_input(tool, names, value) -> bool:
    """Set every name. OFX SetInput often succeeds on unknown ids, so the first
    hit is not proof we touched the real control."""
    if tool is None:
        return False
    if isinstance(names, str):
        names = [names]
    any_ok = False
    for name in names:
        try:
            tool.SetInput(name, value)
            any_ok = True
        except Exception:
            pass
        try:
            getattr(tool, name)[0] = value
            any_ok = True
        except Exception:
            pass
        try:
            setattr(tool, name, value)
            any_ok = True
        except Exception:
            pass
    return any_ok


def _connect(dst, src, names=("Input", "Image", "Image1")) -> bool:
    if dst is None or src is None:
        return False
    if isinstance(names, str):
        names = (names,)
    ids = []
    try:
        main = dst.FindMainInput(1)
        if main is not None:
            iid = (main.GetAttrs() or {}).get("INPS_ID")
            if iid:
                ids.append(str(iid))
    except Exception:
        pass
    ids.extend(names)
    seen = set()
    ordered = []
    for name in ids:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    out = getattr(src, "Output", src)
    for name in ordered:
        try:
            dst.ConnectInput(name, src)
            return True
        except Exception:
            pass
        try:
            dst.ConnectInput(name, out)
            return True
        except Exception:
            pass
        if _set_input(dst, name, out):
            return True
    return False


def _key_mix(tool, keys) -> None:
    if tool is None:
        return
    for frame, value in keys:
        ok = False
        try:
            tool.Mix[frame] = value
            ok = True
        except Exception:
            pass
        if ok:
            continue
        try:
            tool.SetInput("Mix", value, frame)
        except Exception:
            _set_input(tool, "Mix", value)


def _enable_depth_preview(dm, invert: bool = True) -> None:
    """Invert is 1.0/0.0 (Python True turns Invert off). Preview off so the map is alpha."""
    if dm is None:
        return
    # Preview ON only changes the Fusion viewer. Deliver still gets the original RGB.
    # Preview OFF puts the map in alpha, which we copy to RGB.
    _set_input(dm, ["DepthMapPreview"], 0.0)
    _set_input(dm, ["Invert", "InvertMap", "InvertDepth"], 1.0 if invert else 0.0)


def _depth_alpha_to_rgb(comp, depth, x: int):
    """Turn Depth Map alpha into a grayscale image so Deliver bakes the look."""
    custom = _add_tool(comp, ["Custom", "CustomTool", "CustomTool2"], x, 0)
    if custom is None:
        return depth
    _set_input(custom, "RedExpression", "a1")
    _set_input(custom, "GreenExpression", "a1")
    _set_input(custom, "BlueExpression", "a1")
    _set_input(custom, "AlphaExpression", "1")
    _connect(custom, depth)
    return custom


def _try_depth_map(comp, media_in, x, y, invert: bool):
    dm = _add_tool(
        comp,
        [
            "DepthMap",
            "ofx.com.blackmagicdesign.resolve.DepthMap",
            "ofx.com.blackmagicdesign.resolve.depthmap",
        ],
        x,
        y,
    )
    if dm is None:
        return None
    _connect(dm, media_in)
    _enable_depth_preview(dm, invert)
    return dm


def _stylized_chain(comp, media_in, opts: H.DepthStyleOptions, x0: int):
    x = x0
    src = media_in
    if opts.blur > 0:
        blur = _add_tool(comp, "Blur", x, 0)
        x += 1
        if blur is not None:
            _set_input(blur, ["LockXY"], True)
            _set_input(blur, ["XBlurSize", "BlurSize"], float(opts.blur))
            _connect(blur, src)
            src = blur
    bc = _add_tool(comp, "BrightnessContrast", x, 0)
    x += 1
    if bc is not None:
        _set_input(bc, "Contrast", float(opts.contrast))
        _set_input(bc, "Gain", 1.05)
        _set_input(bc, "Gamma", 0.9)
        _connect(bc, src)
        src = bc
    custom = _add_tool(comp, ["Custom", "CustomTool", "CustomTool2"], x, 0)
    x += 1
    expr = H.luma_expression(opts.invert)
    if custom is not None:
        _set_input(custom, "RedExpression", expr)
        _set_input(custom, "GreenExpression", expr)
        _set_input(custom, "BlueExpression", expr)
        _set_input(custom, "AlphaExpression", "a1")
        _connect(custom, src)
        src = custom
    return src, x


def _first_item(added):
    if added is None:
        return None
    if isinstance(added, dict):
        return next(iter(added.values()), None)
    if isinstance(added, (list, tuple)):
        return added[0] if added else None
    return added


def _import_stylized_comp(item, opts: H.DepthStyleOptions):
    import tempfile

    setting = H.build_stylized_setting(
        invert=opts.invert,
        contrast=opts.contrast,
        blur=opts.blur,
        zoom=opts.zoom if opts.mode == "inplace" else 1.0,
    )
    handle = tempfile.NamedTemporaryFile(
        prefix="ltw_depth_", suffix=".setting", delete=False, mode="w"
    )
    handle.write(setting)
    handle.close()
    return item.ImportFusionComp(handle.name)


def _apply_fusion(item, opts: H.DepthStyleOptions, hit_offset: int, duration: int) -> str:
    """Build the look on `item`. Returns 'studio', 'stylized', or 'imported'."""

    def _delete_last_comp():
        try:
            names = list(item.GetFusionCompNameList() or [])
            if names:
                item.DeleteFusionCompByName(names[-1])
        except Exception:
            pass

    if opts.engine in ("auto", "studio"):
        comp = None
        try:
            comp = item.AddFusionComp()
        except Exception:
            comp = None
        if comp is not None:
            wired = False
            depth = None
            try:
                try:
                    comp.Lock()
                except Exception:
                    pass
                media_in, media_out = _find_io(comp)
                depth = _try_depth_map(comp, media_in, 2, 0, opts.invert) if media_in else None
                if depth is not None:
                    out = _depth_alpha_to_rgb(comp, depth, 3)
                    if opts.zoom and opts.zoom != 1.0:
                        xf = _add_tool(comp, "Transform", 5, 0)
                        if xf is not None:
                            _set_input(xf, ["Size", "Scale"], float(opts.zoom))
                            _connect(xf, out)
                            out = xf
                    need_dissolve = opts.mode == "inplace" and opts.switch != "whole"
                    if need_dissolve:
                        dissolve = _add_tool(comp, "Dissolve", 6, 1)
                        if dissolve is not None:
                            _connect(dissolve, media_in, ("Background", "Input"))
                            _connect(dissolve, out, ("Foreground", "Fg", "ForegroundInput"))
                            gstart = 0
                            try:
                                gstart = int((comp.GetAttrs() or {}).get("COMPN_GlobalStart") or 0)
                            except Exception:
                                gstart = 0
                            _key_mix(
                                dissolve,
                                H.fusion_mix_keyframes(
                                    duration, hit_offset, opts.switch, opts.fade_frames, gstart
                                ),
                            )
                            _connect(media_out, dissolve)
                        else:
                            _connect(media_out, out)
                    else:
                        _connect(media_out, out)
                    wired = True
            finally:
                try:
                    comp.Unlock()
                except Exception:
                    pass
            if wired:
                # OFX preview often ignores SetInput while the comp is locked.
                _enable_depth_preview(depth, invert=opts.invert)
                return "studio"
            _delete_last_comp()
        if opts.engine == "studio":
            raise RuntimeError(
                "Studio Depth Map node is not available. Use the Fusion look "
                "(works in Free) or run this on DaVinci Resolve Studio."
            )

    imported = _import_stylized_comp(item, opts)
    if imported:
        return "imported"

    # Last resort: build the Fusion look with AddTool
    comp = item.AddFusionComp()
    if comp is None:
        raise RuntimeError("Could not add a Fusion composition to the clip")
    try:
        comp.Lock()
    except Exception:
        pass
    try:
        media_in, media_out = _find_io(comp)
        if media_in is None or media_out is None:
            raise RuntimeError("Fusion clip is missing MediaIn/MediaOut")
        depth, _x = _stylized_chain(comp, media_in, opts, 2)
        if opts.zoom and opts.zoom != 1.0:
            xf = _add_tool(comp, "Transform", 8, 0)
            if xf is not None:
                _set_input(xf, ["Size", "Scale"], float(opts.zoom))
                _connect(xf, depth)
                depth = xf
        _connect(media_out, depth)
    finally:
        try:
            comp.Unlock()
        except Exception:
            pass
    return "stylized"


def _fade_overlay_opacity(resolve, timeline, item, start_frame: int, full_frame: int) -> None:
    """0% at the copy's first frame, 100% at the hit (overlay fade)."""
    prev_tc = None
    try:
        prev_tc = timeline.GetCurrentTimecode()
    except Exception:
        pass
    try:
        resolve.SetKeyframeMode(resolve.KEYFRAME_MODE_ALL)
    except Exception:
        try:
            resolve.SetKeyframeMode(0)
        except Exception:
            pass
    fps = _fps(timeline)
    for frame, opacity in ((start_frame, 0.0), (full_frame, 100.0)):
        try:
            timeline.SetCurrentTimecode(H.frames_to_timecode(frame, fps))
        except Exception:
            pass
        try:
            item.SetProperty("Opacity", opacity)
        except Exception:
            pass
    if prev_tc:
        try:
            timeline.SetCurrentTimecode(prev_tc)
        except Exception:
            pass


def _duplicate_overlay(
    resolve,
    project,
    timeline,
    item,
    opts: H.DepthStyleOptions,
    playhead: int,
    label: str | None = None,
    color: str = "Pink",
    track_name: str | None = None,
):
    mpi = item.GetMediaPoolItem()
    if mpi is None:
        raise RuntimeError("Clip has no media pool item (titles/generators can't be copied this way)")
    start = int(item.GetStart())
    duration = int(item.GetDuration())
    src_start = int(item.GetSourceStartFrame())
    src_end = int(item.GetSourceEndFrame())
    place = H.overlay_source_window(
        start,
        duration,
        src_start,
        playhead,
        opts.switch,
        opts.fade_frames,
        source_end=src_end,
    )
    src_in, src_out, record = place.src_in, place.src_out, place.record
    track = _track_of(timeline, item)
    dest, need_new = H.first_empty_track(
        _occupied_ranges(timeline),
        record,
        start + duration,
        track,
        int(timeline.GetTrackCount("video") or 1),
    )
    if need_new:
        if not timeline.AddTrack("video"):
            raise RuntimeError("Could not add a video track for the depth copy")
        dest = int(timeline.GetTrackCount("video"))
        try:
            timeline.SetTrackName("video", dest, track_name or "LTW Depth")
        except Exception:
            pass
    elif track_name:
        try:
            timeline.SetTrackName("video", dest, track_name)
        except Exception:
            pass

    media_pool = project.GetMediaPool()
    added = media_pool.AppendToTimeline(
        [
            {
                "mediaPoolItem": mpi,
                "startFrame": src_in,
                "endFrame": src_out,
                "recordFrame": record,
                "trackIndex": dest,
                "mediaType": 1,
            }
        ]
    )
    if not added:
        raise RuntimeError("AppendToTimeline failed — could not copy the clip")
    copy = _first_item(added)
    if copy is None:
        raise RuntimeError("AppendToTimeline returned no clip")
    try:
        copy.SetName(label or f"DEPTH {item.GetName()}")
    except Exception:
        pass
    try:
        copy.SetClipColor(color)
    except Exception:
        pass
    _copy_sizing(item, copy, extra_zoom=1.0)
    if place.opacity_full_at is not None:
        _fade_overlay_opacity(resolve, timeline, copy, record, place.opacity_full_at)
    return copy, 0, int(copy.GetDuration())


def apply(
    resolve,
    opts: H.DepthStyleOptions,
    source_item=None,
    playhead: int | None = None,
    label: str | None = None,
    color: str = "Pink",
    track_name: str | None = None,
    restore_page: bool = True,
) -> str:
    opts = opts.normalized()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if not project:
        raise RuntimeError("No project is open")
    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise RuntimeError("No timeline is open")

    if playhead is None:
        playhead = _playhead_frame(timeline)
    item = source_item or _clip_at_playhead(timeline, playhead)
    if item is None:
        raise RuntimeError("No video clip under the playhead")

    start = int(item.GetStart())
    duration = int(item.GetDuration())
    hit_offset = min(max(playhead - start, 0), duration - 1)

    prev_page = None
    try:
        prev_page = resolve.GetCurrentPage()
    except Exception:
        pass
    if opts.engine in ("auto", "studio"):
        try:
            resolve.OpenPage("fusion")
        except Exception:
            pass

    target = item
    apply_offset = hit_offset
    apply_duration = duration
    if opts.mode == "overlay":
        target, apply_offset, apply_duration = _duplicate_overlay(
            resolve,
            project,
            timeline,
            item,
            opts,
            playhead,
            label=label,
            color=color,
            track_name=track_name,
        )

    used = _apply_fusion(target, opts, apply_offset, apply_duration)
    try:
        target.SetFusionOutputCache("auto")
    except Exception:
        try:
            target.SetFusionOutputCache(True)
        except Exception:
            pass

    if restore_page:
        if prev_page:
            try:
                resolve.OpenPage(prev_page)
            except Exception:
                resolve.OpenPage("edit")
        else:
            try:
                resolve.OpenPage("edit")
            except Exception:
                pass

    where = "copy on the track above" if opts.mode == "overlay" else "the original clip"
    engine = "Studio Depth Map" if used == "studio" else "Fusion look (Free)"
    return f"Applied {engine} to {where} ({opts.switch})."


def _seek_seconds(timeline, seconds: float) -> int:
    fps = _fps(timeline)
    start_tc = "00:00:00:00"
    try:
        start_tc = timeline.GetStartTimecode() or start_tc
    except Exception:
        pass
    frame = H.parse_timecode(start_tc, fps) + int(round(float(seconds) * fps))
    try:
        timeline.SetCurrentTimecode(H.frames_to_timecode(frame, fps))
    except Exception:
        pass
    return frame


def _lowest_clip_at(timeline, frame):
    count = int(timeline.GetTrackCount("video") or 0)
    for i in range(1, count + 1):
        for clip in timeline.GetItemListInTrack("video", i) or []:
            start = int(clip.GetStart())
            end = start + int(clip.GetDuration())
            if start <= frame < end:
                return clip
    return _clip_at_playhead(timeline, frame)


def apply_compare(resolve, opts: H.DepthStyleOptions, at_seconds: float | None = None) -> str:
    """Two overlay copies of the same hit: Free on V2, Studio Depth Map on V3."""
    opts = opts.normalized()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if not project:
        raise RuntimeError("No project is open")
    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise RuntimeError("No timeline is open")

    if at_seconds is not None:
        playhead = _seek_seconds(timeline, at_seconds)
    else:
        playhead = _playhead_frame(timeline)

    source = _lowest_clip_at(timeline, playhead)
    if source is None:
        raise RuntimeError("No video clip at that time")

    prev_page = None
    try:
        prev_page = resolve.GetCurrentPage()
    except Exception:
        pass

    free_opts = H.DepthStyleOptions(
        mode="overlay",
        switch=opts.switch,
        invert=opts.invert,
        engine="stylized",
        zoom=opts.zoom,
        fade_frames=opts.fade_frames,
        contrast=opts.contrast,
        blur=opts.blur,
    ).normalized()
    studio_opts = H.DepthStyleOptions(
        mode="overlay",
        switch=opts.switch,
        invert=opts.invert,
        engine="studio",
        zoom=opts.zoom,
        fade_frames=opts.fade_frames,
        contrast=opts.contrast,
        blur=opts.blur,
    ).normalized()

    free_msg = apply(
        resolve,
        free_opts,
        source_item=source,
        playhead=playhead,
        label="DEPTH Free",
        color="Pink",
        track_name="DEPTH Free",
        restore_page=False,
    )
    try:
        studio_msg = apply(
            resolve,
            studio_opts,
            source_item=source,
            playhead=playhead,
            label="DEPTH Studio",
            color="Violet",
            track_name="DEPTH Studio",
            restore_page=False,
        )
    except Exception as exc:
        studio_msg = f"Studio Depth Map failed ({exc}). Free copy is on the track above."

    try:
        resolve.OpenPage(prev_page or "edit")
    except Exception:
        resolve.OpenPage("edit")
    try:
        timeline.SetCurrentTimecode(H.frames_to_timecode(playhead, _fps(timeline)))
    except Exception:
        pass

    return f"Compare at playhead: {free_msg} | {studio_msg}"


def _depth_clips_on_timeline(timeline):
    found = []
    count = int(timeline.GetTrackCount("video") or 0)
    for t in range(1, count + 1):
        tname = str(timeline.GetTrackName("video", t) or "")
        for c in timeline.GetItemListInTrack("video", t) or []:
            cname = str(c.GetName() or "")
            if tname.startswith("DEPTH") or cname.startswith("DEPTH"):
                found.append(c)
    return found


def _force_depthmap_preview(item, invert: bool = True) -> None:
    try:
        if item.GetFusionCompCount() < 1:
            return
        comp = item.GetFusionCompByIndex(1)
        tools = comp.GetToolList(False) or {}
    except Exception:
        return
    values = tools.values() if isinstance(tools, dict) else list(tools)
    for tool in values:
        try:
            attrs = tool.GetAttrs() or {}
        except Exception:
            continue
        rid = str(attrs.get("TOOLS_RegID") or "")
        name = str(attrs.get("TOOLS_Name") or "")
        blob = f"{rid} {name}".lower()
        if "depthmap" not in blob and "depth map" not in blob:
            continue
        _enable_depth_preview(tool, invert)


def _uid(item) -> str:
    try:
        return str(item.GetUniqueId() or "")
    except Exception:
        return ""


def _find_depth_overlay(timeline, source, playhead: int):
    """The Studio/Free copy we just laid, not the original clip."""
    src_uid = _uid(source)
    count = int(timeline.GetTrackCount("video") or 0)
    hits = []
    for t in range(1, count + 1):
        tname = str(timeline.GetTrackName("video", t) or "")
        for c in timeline.GetItemListInTrack("video", t) or []:
            if src_uid and _uid(c) == src_uid:
                continue
            cname = str(c.GetName() or "")
            start = int(c.GetStart())
            named = tname.startswith("DEPTH") or cname.startswith("DEPTH")
            at_hit = abs(start - int(playhead)) <= 2
            if named or at_hit:
                hits.append((named, t, c))
    if not hits:
        return None, None
    hits.sort(key=lambda row: (not row[0], -row[1]))
    named, track, clip = hits[0]
    return clip, track


def _wait_for_render(project, job=None, timeout_s: float = 3600) -> str:
    import time

    t0 = time.time()
    last_print = -30
    time.sleep(0.5)
    while project.IsRenderingInProgress():
        elapsed = time.time() - t0
        if elapsed > timeout_s:
            print(f"[LTW] Render still running after {int(elapsed)}s — leaving it going.")
            return "timeout"
        if elapsed - last_print >= 15:
            last_print = elapsed
            extra = ""
            if job:
                try:
                    status = project.GetRenderJobStatus(job) or {}
                    pct = status.get("CompletionPercentage")
                    if pct is not None:
                        extra = f" ({pct}%)"
                except Exception:
                    extra = ""
            print(f"[LTW] Baking Depth Map… {int(elapsed)}s{extra}")
        time.sleep(1.0)
    if job:
        try:
            status = project.GetRenderJobStatus(job) or {}
            return str(status.get("JobStatus") or "Complete")
        except Exception:
            return "Complete"
    return "Complete"


def bake_studio(resolve, at_seconds: float = 8.0, out_dir: Path | None = None) -> str:
    """Render Studio Depth Map to a file and put that clip on the timeline.

    Original stays visible until `at_seconds`, then the baked plate covers it.
    Live Neural Engine clips are turned off so playback is just a video file.
    """
    import time

    opts = H.DepthStyleOptions(
        mode="overlay",
        switch="cut",
        invert=True,
        engine="studio",
        zoom=1.08,
    ).normalized()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    if not project:
        raise RuntimeError("No project is open")
    timeline = project.GetCurrentTimeline()
    if not timeline:
        raise RuntimeError("No timeline is open")

    fps = _fps(timeline)
    existing = _depth_clips_on_timeline(timeline)
    if existing:
        print(f"[LTW] Removing {len(existing)} old depth clip(s)…")
        try:
            timeline.DeleteClips(existing, False)
        except Exception as e:
            print(f"[LTW] Could not remove old depth clips: {e}")

    playhead = _seek_seconds(timeline, at_seconds)
    source = _lowest_clip_at(timeline, playhead)
    if source is None:
        raise RuntimeError("No video clip at that time")

    print(f"[LTW] Building Studio Depth Map overlay at {at_seconds:.0f}s…")
    apply(
        resolve,
        opts,
        source_item=source,
        playhead=playhead,
        label="DEPTH Studio (live)",
        color="Violet",
        track_name="DEPTH Studio",
        restore_page=False,
    )
    live, live_track = _find_depth_overlay(timeline, source, playhead)
    if live is None:
        raise RuntimeError("Studio overlay was not created")
    _force_depthmap_preview(live, invert=True)
    try:
        timeline.SetTrackEnable("video", live_track, True)
    except Exception:
        pass

    mark_in = int(live.GetStart())
    mark_out = mark_in + int(live.GetDuration()) - 1
    if out_dir is None:
        out_dir = Path(__file__).resolve().parent.parent / "FUSION" / "effects" / "baked"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    name = f"ltw_depth_studio_{stamp}"

    resolve.OpenPage("deliver")
    loaded = False
    presets = ["ProRes 422 HQ", "H.264 Master"]
    try:
        listed = list(project.GetRenderPresetList() or [])
        for want in ("ProRes 422 HQ", "Apple ProRes 422 HQ", "H.264 Master"):
            if want in listed and want not in presets:
                presets.insert(0, want)
    except Exception:
        listed = []
    for preset in presets:
        try:
            if project.LoadRenderPreset(preset):
                print(f"[LTW] Render preset: {preset}")
                loaded = True
                break
        except Exception:
            continue
    if not loaded:
        print("[LTW] Using current Deliver settings")

    project.SetRenderSettings(
        {
            "SelectAllFrames": False,
            "MarkIn": mark_in,
            "MarkOut": mark_out,
            "TargetDir": str(out_dir),
            "CustomName": name,
            "ExportVideo": True,
            "ExportAudio": False,
        }
    )
    job = project.AddRenderJob()
    if not job:
        raise RuntimeError("AddRenderJob failed — check the Deliver page")
    n_frames = mark_out - mark_in + 1
    print(
        f"[LTW] Rendering {n_frames} frames of Depth Map "
        "(one-time bake, then it plays like a normal clip)…"
    )
    started = project.StartRendering(job)
    if not started:
        try:
            started = project.StartRendering([job])
        except Exception:
            started = False
    if not started:
        raise RuntimeError("StartRendering failed — check the Deliver page")
    result = _wait_for_render(project, job=job)
    if result == "timeout":
        resolve.OpenPage("edit")
        return (
            "Bake is still rendering in Resolve’s Deliver page. "
            "When it finishes, tell me and I’ll drop the file on the timeline."
        )
    if result.lower() not in ("complete", "completed", ""):
        resolve.OpenPage("edit")
        raise RuntimeError(f"Bake render did not finish cleanly ({result})")

    movie = None
    for ext in (".mov", ".mp4", ".mxf"):
        hits = sorted(out_dir.glob(f"{name}*{ext}"))
        if hits:
            movie = hits[-1]
            break
    if movie is None or not movie.exists():
        resolve.OpenPage("edit")
        raise RuntimeError(f"Render finished but no file named {name} in {out_dir}")

    media_pool = project.GetMediaPool()
    imported = media_pool.ImportMedia([str(movie)]) or []
    mpi = _first_item(imported)
    if mpi is None:
        raise RuntimeError(f"Imported render but got no media pool item: {movie}")

    dest, need_new = H.first_empty_track(
        _occupied_ranges(timeline),
        mark_in,
        mark_out + 1,
        live_track,
        int(timeline.GetTrackCount("video") or 1),
    )
    if need_new:
        timeline.AddTrack("video")
        dest = int(timeline.GetTrackCount("video"))
    try:
        timeline.SetTrackName("video", dest, "DEPTH Baked")
    except Exception:
        pass

    src_end = 0
    try:
        src_end = int(float(mpi.GetClipProperty("Frames") or 0))
    except Exception:
        src_end = 0
    if src_end <= 1:
        src_end = int(live.GetDuration())
    added = media_pool.AppendToTimeline(
        [
            {
                "mediaPoolItem": mpi,
                "startFrame": 0,
                "endFrame": max(0, src_end - 1),
                "recordFrame": mark_in,
                "trackIndex": dest,
                "mediaType": 1,
            }
        ]
    )
    baked = _first_item(added)
    if baked is None:
        raise RuntimeError("Could not place the baked clip on the timeline")
    try:
        baked.SetClipColor("Cyan")
    except Exception:
        pass

    try:
        timeline.SetTrackEnable("video", live_track, False)
    except Exception:
        try:
            live.SetClipEnabled(False)
        except Exception:
            pass

    preroll = max(int(source.GetStart()), mark_in - int(round(fps)))
    try:
        timeline.SetCurrentTimecode(H.frames_to_timecode(preroll, fps))
    except Exception:
        pass
    resolve.OpenPage("edit")
    return (
        f"Baked Studio Depth Map from {at_seconds:.0f}s: {movie.name}. "
        "First seconds are the original; from the hit it’s a normal video file (live Depth Map is muted)."
    )


def _parse_args(argv: list[str]):
    p = argparse.ArgumentParser(description="Apply LTW depth-style look to the clip under the playhead")
    p.add_argument("--mode", choices=H.MODES, default="overlay")
    p.add_argument("--switch", choices=H.SWITCHES, default="cut")
    p.add_argument("--engine", choices=H.ENGINES, default="stylized")
    p.add_argument("--zoom", type=float, default=1.08)
    p.add_argument("--fade-frames", type=int, default=6)
    p.add_argument("--no-invert", action="store_true")
    p.add_argument("--no-ui", action="store_true", help="Skip the dialog and use flags/defaults")
    p.add_argument(
        "--compare",
        action="store_true",
        help="Lay Free (V2) and Studio Depth Map (V3) copies of the same hit",
    )
    p.add_argument(
        "--bake",
        action="store_true",
        help="Render Studio Depth Map to a video file and put that on the timeline",
    )
    p.add_argument(
        "--at-seconds",
        type=float,
        default=None,
        help="Hit time from the start of the timeline (e.g. 8). Uses playhead if omitted.",
    )
    args, _unknown = p.parse_known_args(argv)
    opts = H.DepthStyleOptions(
        mode=args.mode,
        switch=args.switch,
        invert=not args.no_invert,
        engine=args.engine,
        zoom=args.zoom,
        fade_frames=args.fade_frames,
        compare=bool(args.compare),
    ).normalized()
    return opts, (not args.no_ui), args.at_seconds, bool(args.bake)


def main(argv: list[str] | None = None) -> None:
    opts, want_ui, at_seconds, do_bake = _parse_args(
        argv if argv is not None else sys.argv[1:]
    )
    resolve = _get_resolve()
    if do_bake:
        seconds = 8.0 if at_seconds is None else at_seconds
        msg = bake_studio(resolve, at_seconds=seconds)
        print(f"[LTW] {msg}")
        return
    if want_ui:
        picked = _prompt(resolve, opts)
        if picked is None:
            print("[LTW] Cancelled.")
            return
        opts = picked
    timeline = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
    if at_seconds is not None:
        _seek_seconds(timeline, at_seconds)
    if opts.compare:
        msg = apply_compare(resolve, opts, at_seconds=at_seconds)
    else:
        msg = apply(resolve, opts)
    print(f"[LTW] {msg}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[LTW] Depth style failed: {exc}")
        raise SystemExit(1)
