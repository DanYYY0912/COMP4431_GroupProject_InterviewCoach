"""Geometry contracts that do not require the optional avatar toolchain."""

import math
import json
from pathlib import Path

import pytest

from scripts.build_interviewer_faces import (
    ensure_model, restore_boundary_vertices, sha256, validate_geometry,
)


def ring():
    positions = [[.4, .4, 0], [.6, .4, 0], [.6, .6, 0], [.4, .6, 0],
                 [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    triangles = [4, 5, 1, 4, 1, 0, 5, 6, 2, 5, 2, 1,
                 6, 7, 3, 6, 3, 2, 7, 4, 0, 7, 0, 3]
    return positions, triangles, [0, 1, 2, 3], 4


def test_continuous_portrait_with_one_mouth_aperture_is_valid():
    result = validate_geometry(*ring())
    assert result['boundaryEdges'] == 8
    assert result['triangleCount'] == 8
    assert result['coveredArea'] == pytest.approx(.96)


@pytest.mark.parametrize('bad_value', [math.nan, math.inf, -math.inf])
def test_nonfinite_landmark_is_rejected(bad_value):
    positions, triangles, mouth, border = ring()
    positions[0][2] = bad_value
    with pytest.raises(ValueError, match='finite'):
        validate_geometry(positions, triangles, mouth, border)


def test_extra_crack_is_rejected():
    positions, triangles, mouth, border = ring()
    with pytest.raises(ValueError, match='boundar'):
        validate_geometry(positions, triangles[:-3], mouth, border)


def test_filled_mouth_is_rejected():
    positions, triangles, mouth, border = ring()
    with pytest.raises(ValueError, match='boundar'):
        validate_geometry(positions, triangles + [0, 1, 2, 0, 2, 3], mouth, border)


def test_reversed_or_degenerate_triangle_is_rejected():
    positions, triangles, mouth, border = ring()
    triangles[:3] = [4, 1, 5]
    with pytest.raises(ValueError, match='winding'):
        validate_geometry(positions, triangles, mouth, border)


def test_out_of_range_index_is_rejected():
    positions, triangles, mouth, border = ring()
    triangles[0] = len(positions)
    with pytest.raises(ValueError, match='index'):
        validate_geometry(positions, triangles, mouth, border)


def test_existing_wrong_model_fails_closed_without_redownload(tmp_path, monkeypatch):
    model = tmp_path / 'face.task'
    model.write_bytes(b'not the pinned model')
    def unexpected_download(*args, **kwargs):
        pytest.fail('Existing corrupt model must not silently trigger a download')
    monkeypatch.setattr('urllib.request.urlopen', unexpected_download)
    with pytest.raises(ValueError, match='SHA-256'):
        ensure_model(model, allow_download=True)


def test_missing_model_does_not_access_network_without_explicit_flag(tmp_path, monkeypatch):
    def unexpected_download(*args, **kwargs):
        pytest.fail('Offline regeneration must not access the network')
    monkeypatch.setattr('urllib.request.urlopen', unexpected_download)
    with pytest.raises(ValueError, match='Missing model'):
        ensure_model(tmp_path / 'face.task', allow_download=False)


def test_collinear_frame_vertex_is_restored_without_a_gap_or_area_change():
    positions = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [.5, 0, 0]]
    faces = [[0, 1, 2]]
    restore_boundary_vertices(faces, positions, [0, 1, 2, 3])
    assert faces == [[0, 3, 2], [3, 1, 2]]


def test_shipped_jamie_mesh_matches_current_source_and_has_only_one_aperture():
    root = Path(__file__).resolve().parents[2]
    directory = root / 'frontend/public/interviewers'
    mesh = json.loads((directory / 'jamie.mesh.json').read_text())
    assert mesh['landmarkCount'] == 468
    assert mesh['frameVertexCount'] == 64
    assert len(mesh['positions']) == 532
    assert mesh['provenance']['sourceSha256'] == sha256(directory / 'jamie.png')
    assert mesh['provenance']['generatorSha256'] == sha256(root / 'scripts/build_interviewer_faces.py')
    assert mesh['provenance']['runtimeInference'] is False
    result = validate_geometry(mesh['positions'], mesh['triangles'], mesh['mouthLoop'],
                               468, allow_projected_folds=True)
    assert result['boundaryEdges'] == 84
    assert result['triangleCount'] == 980
    assert result['mouthArea'] > 0
