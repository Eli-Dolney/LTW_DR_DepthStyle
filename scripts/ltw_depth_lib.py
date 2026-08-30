"""Depth-style edit helpers (no Resolve runtime required).

The look matches the viral After Effects 'depth map' edit: footage starts
normal, then on a hit (goal, punch, bass drop) the image switches to a
high-contrast grayscale depth visualization (subject dark, background light).

These helpers are used by `resolve_scripts/ltw_depth_style.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


MODES = ("overlay", "inplace")
SWITCHES = ("cut", "fade", "whole")
ENGINES = ("auto", "studio", "stylized")

# Rec.601 luma. Keep this short — Fusion Custom expressions have a length cap.
LUMA = "0.299*r1+0.587*g1+0.114*b1"


@dataclass(frozen=True)
class DepthStyleOptions:
    mode: str = "overlay"
    switch: str = "cut"
    invert: bool = True
    engine: str = "stylized"
    zoom: float = 1.08
    fade_frames: int = 6
    contrast: float = 0.45
    blur: float = 2.5

    compare: bool = False

    def normalized(self) -> "DepthStyleOptions":
        mode = self.mode if self.mode in MODES else "overlay"
        switch = self.switch if self.switch in SWITCHES else "cut"
        engine = self.engine if self.engine in ENGINES else "stylized"
        zoom = min(1.5, max(1.0, float(self.zoom)))
        fade = min(48, max(1, int(self.fade_frames)))
        contrast = min(1.0, max(0.0, float(self.contrast)))
        blur = min(20.0, max(0.0, float(self.blur)))
        return DepthStyleOptions(
            mode=mode,
            switch=switch,
            invert=bool(self.invert),
            engine=engine,
            zoom=zoom,
            fade_frames=fade,
            contrast=contrast,
            blur=blur,
            compare=bool(self.compare),
        )


def parse_timecode(tc: str, fps: float) -> int:
    """HH:MM:SS:FF (or ;) to an absolute frame count. Non-drop-frame."""
    if not tc:
        return 0
    cleaned = str(tc).strip().replace(";", ":")
    parts = [int(p) for p in cleaned.split(":") if p != ""]
    if len(parts) == 4:
        hh, mm, ss, ff = parts
    elif len(parts) == 3:
        hh = 0
        mm, ss, ff = parts
    elif len(parts) == 2:
        hh = mm = 0
        ss, ff = parts
    else:
        return 0
    rate = int(round(float(fps) or 24.0))
    return ((hh * 3600) + (mm * 60) + ss) * rate + ff


def timeline_frame(playhead_tc: str, start_tc: str, fps: float) -> int:
    """Playhead as a 0-based timeline frame, accounting for start timecode."""
    return max(0, parse_timecode(playhead_tc, fps) - parse_timecode(start_tc, fps))


@dataclass(frozen=True)
class OverlayPlacement:
    src_in: int
    src_out: int
    record: int
    opacity_full_at: int | None = None


def overlay_source_window(
    clip_start: int,
    duration: int,
    source_start: int,
    playhead: int,
    switch: str,
    fade_frames: int = 6,
    source_end: int | None = None,
) -> OverlayPlacement:
    """Video-only copy of the selected clip.

    `cut` starts the copy at the hit so the original stays visible underneath
    until that frame. `fade` starts `fade_frames` earlier (opacity 0 → 100 at
    the hit). `whole` covers the entire clip.

    `source_end` is inclusive (Resolve GetSourceEndFrame). When given, the
    playhead offset is mapped through the timeline clip onto source frames so
    mixed frame rates (e.g. 23.976 in a 60fps timeline) stay in sync.
    """
    duration = max(1, int(duration))
    clip_start = int(clip_start)
    source_start = int(source_start)
    clip_end = clip_start + duration

    if switch == "whole":
        record = clip_start
        opacity_full_at = None
    else:
        hit = min(max(int(playhead), clip_start), clip_end - 1)
        if switch == "fade":
            record = max(clip_start, hit - max(1, int(fade_frames)))
            opacity_full_at = hit
        else:
            record = hit
            opacity_full_at = None

    offset = record - clip_start
    if source_end is None:
        src_in = source_start + offset
        src_out = source_start + duration - 1
    else:
        source_end = int(source_end)
        src_count = max(1, source_end - source_start + 1)
        src_in = source_start + int(round(offset * src_count / duration))
        src_out = source_end
    if src_out < src_in:
        src_in = src_out
    return OverlayPlacement(src_in, src_out, record, opacity_full_at)


def frames_to_timecode(frames: int, fps: float) -> str:
    rate = max(1, int(round(float(fps) or 24.0)))
    frames = max(0, int(frames))
    ff = frames % rate
    total_s = frames // rate
    hh = total_s // 3600
    mm = (total_s % 3600) // 60
    ss = total_s % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def timeline_timecode(frame: int, start_tc: str, fps: float) -> str:
    return frames_to_timecode(parse_timecode(start_tc, fps) + int(frame), fps)


def fusion_mix_keyframes(
    duration: int,
    hit_offset: int,
    switch: str,
    fade_frames: int,
    global_start: int = 0,
) -> list[tuple[int, float]]:
    """Dissolve Mix keys: 0 = original, 1 = depth look."""
    duration = max(1, int(duration))
    g0 = int(global_start)
    g1 = g0 + duration - 1
    if switch == "whole" or hit_offset <= 0:
        return [(g0, 1.0)]

    hit = min(max(g0 + int(hit_offset), g0), g1)
    if switch == "cut":
        if hit <= g0:
            return [(g0, 1.0)]
        return [(g0, 0.0), (hit - 1, 0.0), (hit, 1.0)]

    fade = max(1, int(fade_frames))
    fade_end = min(hit + fade, g1)
    keys = [(g0, 0.0)]
    if hit > g0:
        keys.append((hit, 0.0))
    keys.append((fade_end, 1.0))
    return keys


def luma_expression(invert: bool) -> str:
    if invert:
        return f"1-({LUMA})"
    return LUMA


def build_stylized_setting(
    invert: bool = True,
    contrast: float = 0.45,
    blur: float = 2.5,
    zoom: float = 1.0,
) -> str:
    """Fusion .setting that turns a clip into the depth-map look.

    MediaIn1 -> Blur -> BrightnessContrast -> Custom (luma +/- invert)
    -> Transform -> MediaOut1
    """
    expr = luma_expression(invert)
    size = max(1.0, float(zoom))
    # Fusion BrightnessContrast Contrast is typically 0 at default.
    contrast = min(1.0, max(0.0, float(contrast)))
    blur = min(20.0, max(0.0, float(blur)))
    return f"""{{
	Tools = ordered() {{
		MediaIn1 = MediaIn {{
			ExtentSet = true,
			CtrlWZoom = false,
			ViewInfo = operatorViewInfo {{ Pos = {{ 0, 0 }} }},
		}},
		Blur1 = Blur {{
			Inputs = {{
				LockXY = Input {{ Value = 1 }},
				XBlurSize = Input {{ Value = {blur:.3f} }},
				Input = Input {{
					SourceOp = "MediaIn1",
					Source = "Output",
				}},
			}},
			ViewInfo = operatorViewInfo {{ Pos = {{ 165, 0 }} }},
		}},
		BrightnessContrast1 = BrightnessContrast {{
			Inputs = {{
				Contrast = Input {{ Value = {contrast:.3f} }},
				Gain = Input {{ Value = 1.05 }},
				Gamma = Input {{ Value = 0.9 }},
				Input = Input {{
					SourceOp = "Blur1",
					Source = "Output",
				}},
			}},
			ViewInfo = operatorViewInfo {{ Pos = {{ 330, 0 }} }},
		}},
		Custom1 = Custom {{
			Inputs = {{
				RedExpression = Input {{ Value = "{expr}" }},
				GreenExpression = Input {{ Value = "{expr}" }},
				BlueExpression = Input {{ Value = "{expr}" }},
				AlphaExpression = Input {{ Value = "a1" }},
				Image1 = Input {{
					SourceOp = "BrightnessContrast1",
					Source = "Output",
				}},
			}},
			ViewInfo = operatorViewInfo {{ Pos = {{ 495, 0 }} }},
		}},
		Transform1 = Transform {{
			Inputs = {{
				Size = Input {{ Value = {size:.4f} }},
				Input = Input {{
					SourceOp = "Custom1",
					Source = "Output",
				}},
			}},
			ViewInfo = operatorViewInfo {{ Pos = {{ 660, 0 }} }},
		}},
		MediaOut1 = MediaOut {{
			Inputs = {{
				Input = Input {{
					SourceOp = "Transform1",
					Source = "Output",
				}},
			}},
			ViewInfo = operatorViewInfo {{ Pos = {{ 825, 0 }} }},
		}}
	}},
	ActiveTool = "Custom1"
}}
"""


def setting_tool_ids(setting: str) -> list[str]:
    """Best-effort list of Fusion tool IDs in a .setting dump."""
    ids: list[str] = []
    for line in setting.splitlines():
        line = line.strip()
        if " = " not in line or not line.endswith("{"):
            continue
        left = line.split(" = ", 1)[0].strip()
        if left in {"Tools", "Inputs", "ViewInfo"}:
            continue
        ids.append(left)
    return ids


def first_empty_track(
    occupied: Iterable[tuple[int, int, int]],
    start: int,
    end: int,
    prefer_above: int,
    existing_tracks: int,
) -> tuple[int, bool]:
    """Pick a video track with no overlap in [start, end).

    `occupied` is (track_index, clip_start, clip_end_exclusive).
    Returns (track_index, needs_new_track).
    """
    start = int(start)
    end = int(end)
    prefer_above = max(1, int(prefer_above))
    existing_tracks = max(existing_tracks, prefer_above)
    by_track: dict[int, list[tuple[int, int]]] = {}
    for track, c0, c1 in occupied:
        by_track.setdefault(int(track), []).append((int(c0), int(c1)))

    def _free(track: int) -> bool:
        for c0, c1 in by_track.get(track, []):
            if c0 < end and c1 > start:
                return False
        return True

    for track in range(prefer_above + 1, existing_tracks + 1):
        if _free(track):
            return track, False
    return existing_tracks + 1, True
