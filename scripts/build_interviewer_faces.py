#!/usr/bin/env python3
"""Precompute portrait relief meshes; never edits the source PNGs.

Setup (the optional environment/model remain in ignored artifacts/):
  python3.12 -m venv artifacts/avatar-tools
  artifacts/avatar-tools/bin/pip install -r scripts/requirements-avatar.txt
  artifacts/avatar-tools/bin/python scripts/build_interviewer_faces.py --download-model

After that first verified download, omit --download-model to regenerate offline.
Jamie is the only included portrait. Explicit --portraits alex/sam also works if
new source assets with those names are deliberately supplied in --input-dir.

Geometry is a front-view approximation, not a scan or a complete human head.
The first 468 vertices preserve MediaPipe indices. Sixty-four additional vertices
form the portrait frame. x/y are normalized image coordinates (right/down), z is
MediaPipe's relative depth in image-width units (negative towards the camera).
Frame z=0. UVs are (x, 1-y), NOT canonical face-atlas UVs. Renderers converting
y to an upward axis must reverse triangle winding or use a double-sided material.
Depth should be flattened towards the face oval by the renderer; raw z is retained
here to avoid disguising an artistic adjustment as measured geometry.

References:
https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker
https://chuoling.github.io/mediapipe/solutions/face_mesh.html#face-geometry-module
https://github.com/skogler/mapbox_earcut_python
Canonical MediaPipe facial topology is joined to an Earcut-triangulated portrait
frame, sharing the face-oval vertices. See MEDIAPIPE-LICENSE.txt beside the meshes.
The mouth indices use MediaPipe's landmark convention. The MediaPipe SDK
(Apache-2.0) and official downloadable inference model are preprocessing tools,
not browser dependencies.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
MODEL_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
MOUTH_LOOP = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415,
              308, 324, 318, 402, 317, 14, 87, 178, 88, 95]
LANDMARK_COUNT = 468
FRAME_EDGE_STEPS = 16
TOPOLOGY_PATH = ROOT / "scripts/avatar/canonical_face_model.obj"
TOPOLOGY_SHA256 = "8bac80443397e113f41a8b565ea72c59390bc031d9defab289dba7bc0c54e618"
TOPOLOGY_URL = ("https://raw.githubusercontent.com/google-ai-edge/mediapipe/"
                "a908d668c730da128dfa8d9f6bd25d519d006692/"
                "mediapipe/modules/face_geometry/data/canonical_face_model.obj")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_model(path: Path, allow_download: bool) -> None:
    """Only the versioned official URL is allowed, with a required known digest."""
    if not path.exists():
        if not allow_download:
            raise ValueError(f"Missing model {path}; run once with --download-model")
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(MODEL_URL, timeout=90) as response:
            data = response.read(8_000_001)
        if len(data) > 8_000_000 or hashlib.sha256(data).hexdigest() != MODEL_SHA256:
            raise ValueError("Downloaded Face Landmarker model failed SHA-256 verification")
        temporary = path.with_suffix(".download")
        temporary.write_bytes(data)
        temporary.replace(path)
    if sha256(path) != MODEL_SHA256:
        raise ValueError("Local Face Landmarker model failed SHA-256 verification")


def polygon_area(points: list[list[float]]) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1]
                   for a, b in zip(points, points[1:] + points[:1]))) / 2


def loop_edges(indices: list[int]) -> set[tuple[int, int]]:
    return {tuple(sorted((a, b))) for a, b in zip(indices, indices[1:] + indices[:1])}


def validate_geometry(positions: list[list[float]], triangles: list[int],
                      mouth_loop: list[int], border_start: int,
                      *, allow_projected_folds: bool = False) -> dict:
    """Reject cracks, a filled mouth, dropped vertices and bad numbers.

    Canonical facial topology may fold in XY projection; allow that explicitly
    for measured 3D faces, while still checking signed coverage and all edges.
    """
    for point in positions:
        if len(point) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in point):
            raise ValueError("Each position must contain three finite numbers")
        if not (0 <= point[0] <= 1 and 0 <= point[1] <= 1 and abs(point[2]) <= 1):
            raise ValueError("Position outside normalized portrait coordinate bounds")
    if len(triangles) % 3 or not triangles:
        raise ValueError("Triangle indices must be a nonempty multiple of three")
    if any(type(i) is not int or not 0 <= i < len(positions) for i in triangles + mouth_loop):
        raise ValueError("Triangle/mouth index outside vertex range")
    if len(set(mouth_loop)) != len(mouth_loop) or len(mouth_loop) < 3:
        raise ValueError("Mouth loop must contain distinct indices")
    if not 0 < border_start < len(positions):
        raise ValueError("Invalid frame boundary start")
    edges: Counter[tuple[int, int]] = Counter()
    total_area = 0.0
    folded = 0
    for start in range(0, len(triangles), 3):
        a, b, c = triangles[start:start + 3]
        pa, pb, pc = positions[a], positions[b], positions[c]
        area = ((pb[0] - pa[0]) * (pc[1] - pa[1]) -
                (pb[1] - pa[1]) * (pc[0] - pa[0])) / 2
        if abs(area) <= 1e-12 or (area < 0 and not allow_projected_folds):
            raise ValueError("Triangle winding must be positive with nonzero area")
        folded += area < 0
        total_area += area
        edges.update((tuple(sorted(pair)) for pair in ((a, b), (b, c), (c, a))))
    actual_boundary = {edge for edge, count in edges.items() if count == 1}
    expected_boundary = loop_edges(mouth_loop) | loop_edges(list(range(border_start, len(positions))))
    if actual_boundary != expected_boundary or any(count > 2 for count in edges.values()):
        raise ValueError("Mesh boundaries must be exactly the portrait frame and mouth aperture; "
                         f"missing={sorted(expected_boundary - actual_boundary)}, "
                         f"extra={sorted(actual_boundary - expected_boundary)}")
    if set(triangles) != set(range(len(positions))):
        raise ValueError("Mesh dropped one or more landmarks/frame vertices")
    expected_area = 1 - polygon_area([positions[i] for i in mouth_loop])
    if not math.isclose(total_area, expected_area, rel_tol=0, abs_tol=1e-8):
        raise ValueError("Mesh area does not cover exactly the portrait minus mouth")
    return {"vertexCount": len(positions), "triangleCount": len(triangles) // 3,
            "boundaryEdges": len(actual_boundary), "coveredArea": round(total_area, 10),
            "mouthArea": round(1 - expected_area, 10), "projectedFoldTriangles": folded}


def canonical_faces() -> tuple[list[list[int]], list[int]]:
    if sha256(TOPOLOGY_PATH) != TOPOLOGY_SHA256:
        raise ValueError("Vendored canonical topology failed SHA-256 verification")
    faces = [[int(token.split("/")[0]) - 1 for token in line.split()[1:]]
             for line in TOPOLOGY_PATH.read_text().splitlines() if line.startswith("f ")]
    edges = Counter(tuple(sorted(edge)) for a, b, c in faces
                    for edge in ((a, b), (b, c), (c, a)))
    boundary: dict[int, list[int]] = defaultdict(list)
    for (a, b), count in edges.items():
        if count == 1:
            boundary[a].append(b)
            boundary[b].append(a)
    if len(boundary) != 36 or any(len(neighbors) != 2 for neighbors in boundary.values()):
        raise ValueError("Canonical topology has unexpected outer boundary")
    oval = [min(boundary)]
    while True:
        neighbor = next(i for i in boundary[oval[-1]] if len(oval) < 2 or i != oval[-2])
        if neighbor == oval[0]:
            break
        oval.append(neighbor)
    # Canonical OBJ is oriented for y-up; normalized image coordinates are y-down.
    return [[a, c, b] for a, b, c in faces], oval


def restore_boundary_vertices(faces: list[list[int]], positions: list[list[float]],
                              required: list[int]) -> None:
    """Earcut may omit collinear frame points; split their boundary edges exactly."""
    used = {i for face in faces for i in face}
    for index in required:
        if index in used:
            continue
        point = positions[index]
        found = False
        for face_index, face in enumerate(faces):
            for offset in range(3):
                a, b, c = face[offset:] + face[:offset]
                pa, pb = positions[a], positions[b]
                dx, dy = pb[0] - pa[0], pb[1] - pa[1]
                cross = dx * (point[1] - pa[1]) - dy * (point[0] - pa[0])
                dot = (point[0] - pa[0]) * dx + (point[1] - pa[1]) * dy
                if abs(cross) < 1e-12 and 0 < dot < dx * dx + dy * dy:
                    faces[face_index] = [a, index, c]
                    faces.append([index, b, c])
                    used.add(index)
                    found = True
                    break
            if found:
                break
        if not found:
            raise ValueError(f"Cannot restore omitted contour vertex {index}")


def make_geometry(landmarks: list[list[float]]) -> tuple[list[list[float]], list[int], dict]:
    import numpy as np
    import mapbox_earcut as earcut

    if len(landmarks) != LANDMARK_COUNT:
        raise ValueError(f"Expected {LANDMARK_COUNT} face landmarks")
    positions = [[round(float(v), 9) for v in point] for point in landmarks]
    # Clockwise in image coordinates, each corner occurs exactly once.
    for edge in range(4):
        for i in range(FRAME_EDGE_STEPS):
            t = i / FRAME_EDGE_STEPS
            x, y = [(t, 0), (1, t), (1 - t, 1), (0, 1 - t)][edge]
            positions.append([x, y, 0.0])
    canonical, oval = canonical_faces()
    mouth_set = set(MOUTH_LOOP)
    facial = [face for face in canonical if not set(face).issubset(mouth_set)]
    removed = len(canonical) - len(facial)
    mapping = list(range(LANDMARK_COUNT, len(positions))) + oval
    xy = np.asarray([[positions[i][0], positions[i][1]] for i in mapping], dtype=np.float64)
    rings = np.asarray([FRAME_EDGE_STEPS * 4, len(mapping)], dtype=np.uint32)
    result = earcut.triangulate_float64(xy, rings)
    outside = [[mapping[int(i)] for i in result[start:start + 3]]
               for start in range(0, len(result), 3)]
    restore_boundary_vertices(outside, positions, mapping)
    faces = []
    for face in facial + outside:
        # Canonicalize order for stable files while preserving positive XY winding.
        indices = [int(i) for i in face]
        offset = indices.index(min(indices))
        faces.append(indices[offset:] + indices[:offset])
    triangles = [i for face in sorted(faces) for i in face]
    # The measured face has a few XY folds (cheeks/lip edges). These are legitimate
    # 3D surface folds, not missing triangles; preserve them and report their count.
    diagnostics = validate_geometry(positions, triangles, MOUTH_LOOP, LANDMARK_COUNT,
                                    allow_projected_folds=True)
    diagnostics["removedMouthTriangles"] = removed
    return positions, triangles, diagnostics


def build_portrait(image_path: Path, model_path: Path) -> dict:
    import mediapipe as mp
    from PIL import Image

    with Image.open(image_path) as image:
        width, height = image.size
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_faces=2, min_face_detection_confidence=0.5,
        output_face_blendshapes=False, output_facial_transformation_matrixes=False,
    )
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as landmarker:
        result = landmarker.detect(mp.Image.create_from_file(str(image_path)))
    if len(result.face_landmarks) != 1:
        raise ValueError(f"{image_path.name}: expected exactly one detected face")
    landmarks = [[p.x, p.y, p.z] for p in result.face_landmarks[0][:LANDMARK_COUNT]]
    positions, triangles, diagnostics = make_geometry(landmarks)
    return {
        "schemaVersion": 1, "id": image_path.stem,
        "dimensions": {"width": width, "height": height},
        "landmarkCount": LANDMARK_COUNT, "frameVertexCount": FRAME_EDGE_STEPS * 4,
        "positions": positions, "triangles": triangles, "mouthLoop": MOUTH_LOOP,
        "coordinates": {"x": "image-right / image-width", "y": "image-down / image-height",
                        "z": "relative depth / image-width; negative towards camera; frame=0",
                        "uv": "[x, 1-y]", "winding": "topologically positive in image XY; measured face can fold in projection"},
        "provenance": {
            "sourceImage": image_path.name, "sourceSha256": sha256(image_path),
            "modelUrl": MODEL_URL, "modelSha256": MODEL_SHA256,
            "generator": "scripts/build_interviewer_faces.py",
            "generatorSha256": sha256(Path(__file__)),
            "packages": {name: version(name) for name in ("mediapipe", "numpy", "Pillow", "mapbox-earcut")},
            "topologyUrl": TOPOLOGY_URL, "topologySha256": TOPOLOGY_SHA256,
            "topologyLicense": "Apache-2.0; see MEDIAPIPE-LICENSE.txt",
            "method": "MediaPipe IMAGE landmarks; first 468; canonical facial triangles with "
                      "inner-mouth cap removed; Earcut portrait frame with 36-vertex face-oval hole; "
                      "restore all 64 frame vertices by collinear edge subdivision",
            "limitations": "Single-view textured relief, not a full head scan or a trained facial rig. "
                           "Depth is estimated; unseen surfaces, teeth and mouth interior are not reconstructed.",
            "runtimeInference": False,
        },
        "validation": diagnostics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--portraits", nargs="+", default=["jamie"],
                        help="Jamie is the included portrait; additional allowlisted PNGs may be supplied explicitly")
    parser.add_argument("--input-dir", type=Path, default=ROOT / "frontend/public/interviewers")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "frontend/public/interviewers")
    parser.add_argument("--model", type=Path, default=ROOT / "artifacts/avatar-tools/face_landmarker.task")
    parser.add_argument("--download-model", action="store_true", help="Fetch the pinned verified official model if absent")
    args = parser.parse_args()
    ensure_model(args.model, args.download_model)
    sources = []
    for name in args.portraits:
        if name not in {"alex", "jamie", "sam"}:
            parser.error("Portrait must be alex, jamie or sam")
        source = args.input_dir / f"{name}.png"
        if not source.is_file():
            parser.error(f"Missing source portrait: {source}")
        sources.append(source)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for source in sources:
        payload = build_portrait(source, args.model)
        destination = args.output_dir / f"{source.stem}.mesh.json"
        destination.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n")
        print(json.dumps({"portrait": source.stem, "output": str(destination), **payload["validation"]}))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"Avatar preprocessing failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
