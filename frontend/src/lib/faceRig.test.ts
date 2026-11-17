import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { FaceRig, blinkAt, speechOpening, validateFaceMesh } from './faceRig';

function data() {
  return validateFaceMesh(JSON.parse(readFileSync('public/interviewers/jamie.mesh.json', 'utf8')));
}

describe('portrait face rig', () => {
  it('opens the real lip aperture while anchoring the portrait perimeter, then fully resets', () => {
    const rig = new FaceRig(data());
    const rest = rig.positions.slice();
    const gap = rest[13 * 3 + 1] - rest[14 * 3 + 1];
    rig.pose(0.8, 0);
    expect(rig.positions[13 * 3 + 1] - rig.positions[14 * 3 + 1]).toBeGreaterThan(gap + 0.01);
    expect(Array.from(rig.positions.slice(468 * 3))).toEqual(Array.from(rest.slice(468 * 3)));
    expect(Array.from(rig.positions).every(Number.isFinite)).toBe(true);
    rig.pose(0, 0);
    expect(rig.positions).toEqual(rest);
  });
  it('closes eyelids and keeps a non-flat facial surface', () => {
    const rig = new FaceRig(data());
    const gap = Math.abs(rig.positions[159 * 3 + 1] - rig.positions[145 * 3 + 1]);
    rig.pose(0, 1);
    expect(Math.abs(rig.positions[159 * 3 + 1] - rig.positions[145 * 3 + 1])).toBeLessThan(
      gap * 0.1,
    );
    const depth = Array.from(rig.rest).filter((_, index) => index % 3 === 2);
    expect(Math.max(...depth) - Math.min(...depth)).toBeGreaterThan(0.1);
  });
  it('rejects invalid geometry before allocating a renderer', () => {
    const mesh = data();
    expect(() => validateFaceMesh({ ...mesh, triangles: [0, 1, 99999] })).toThrow();
    mesh.positions[308][0] = mesh.positions[78][0];
    expect(() => validateFaceMesh(mesh)).toThrow();
  });
  it('bounds expression cues and returns finite geometry for invalid animation inputs', () => {
    const rig = new FaceRig(data());
    rig.pose(Number.NaN, Infinity);
    expect(rig.positions).toEqual(rig.rest);
    for (let time = 0; time < 10; time += 0.01) {
      expect(speechOpening(time, 1)).toBeGreaterThanOrEqual(0);
      expect(speechOpening(time, 1)).toBeLessThanOrEqual(1);
      expect(blinkAt(time)).toBeGreaterThanOrEqual(0);
      expect(blinkAt(time)).toBeLessThanOrEqual(1);
    }
  });
});
