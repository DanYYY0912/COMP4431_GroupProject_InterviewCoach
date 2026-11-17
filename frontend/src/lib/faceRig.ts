export type FaceMeshData = {
  dimensions: { width: number; height: number };
  landmarkCount: number;
  positions: number[][];
  triangles: number[];
  mouthLoop: number[];
};

const eyelids = [
  {
    upper: [33, 246, 161, 160, 159, 158, 157, 173, 133],
    lower: [33, 7, 163, 144, 145, 153, 154, 155, 133],
  },
  {
    upper: [263, 466, 388, 387, 386, 385, 384, 398, 362],
    lower: [263, 249, 390, 373, 374, 380, 381, 382, 362],
  },
];
const oval = [
  10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148,
  176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
];
const clamp = (value: number, min = 0, max = 1) => Math.max(min, Math.min(max, value));

export function validateFaceMesh(value: unknown): FaceMeshData {
  const mesh = value as FaceMeshData;
  if (
    !mesh ||
    mesh.landmarkCount !== 468 ||
    !Array.isArray(mesh.positions) ||
    mesh.positions.length < 468 ||
    mesh.positions.length > 2048 ||
    !mesh.dimensions ||
    !Number.isFinite(mesh.dimensions.width) ||
    !Number.isFinite(mesh.dimensions.height) ||
    mesh.dimensions.width <= 0 ||
    mesh.dimensions.height <= 0 ||
    !mesh.positions.every(
      (p) =>
        Array.isArray(p) &&
        p.length === 3 &&
        p.every(Number.isFinite) &&
        p[0] >= 0 &&
        p[0] <= 1 &&
        p[1] >= 0 &&
        p[1] <= 1 &&
        Math.abs(p[2]) < 2,
    ) ||
    !Array.isArray(mesh.triangles) ||
    !mesh.triangles.length ||
    mesh.triangles.length > 20000 ||
    mesh.triangles.length % 3 !== 0 ||
    !mesh.triangles.every((i) => Number.isInteger(i) && i >= 0 && i < mesh.positions.length) ||
    !Array.isArray(mesh.mouthLoop) ||
    mesh.mouthLoop.length < 12 ||
    !mesh.mouthLoop.every((i) => Number.isInteger(i) && i >= 0 && i < 468) ||
    Math.abs(mesh.positions[308][0] - mesh.positions[78][0]) < 0.01 ||
    Math.abs(mesh.positions[133][0] - mesh.positions[33][0]) < 0.01 ||
    Math.abs(mesh.positions[362][0] - mesh.positions[263][0]) < 0.01
  ) {
    throw new Error('The interviewer face mesh is invalid.');
  }
  return mesh;
}

/** A shallow, portrait-textured facial surface. It is designed for a frontal camera. */
export class FaceRig {
  readonly positions: Float32Array;
  readonly rest: Float32Array;
  readonly uv: Float32Array;
  readonly mouth: Float32Array;
  readonly ratio: number;
  private readonly mouthX: number;
  private readonly mouthY: number;
  private readonly mouthWidth: number;
  private readonly depthBase: number;

  constructor(readonly data: FaceMeshData) {
    this.ratio = data.dimensions.height / data.dimensions.width;
    this.mouthX = (data.positions[78][0] + data.positions[308][0]) / 2;
    this.mouthY = (data.positions[13][1] + data.positions[14][1]) / 2;
    this.mouthWidth = Math.abs(data.positions[308][0] - data.positions[78][0]);
    this.depthBase = oval.reduce((sum, i) => sum + data.positions[i][2], 0) / oval.length;
    this.rest = new Float32Array(data.positions.length * 3);
    this.uv = new Float32Array(data.positions.length * 2);
    const edge = new Set(oval);
    data.positions.forEach(([x, y, z], i) => {
      this.rest.set(
        [
          (x - 0.5) * 2,
          (0.5 - y) * this.ratio * 2,
          i < 468 && !edge.has(i) ? (this.depthBase - z) * 1.5 : 0,
        ],
        i * 3,
      );
      this.uv.set([x, 1 - y], i * 2);
    });
    this.positions = this.rest.slice();
    this.mouth = new Float32Array((data.mouthLoop.length + 1) * 3);
    this.pose(0, 0);
  }

  pose(opening: number, blink: number) {
    const open = clamp(Number.isFinite(opening) ? opening : 0);
    const lid = clamp(Number.isFinite(blink) ? blink : 0);
    this.positions.set(this.rest);
    const lowerLip = this.data.positions[14][1];
    const upperLip = this.data.positions[13][1];
    const jawTravel = this.mouthWidth * 0.16 * open;
    for (let i = 0; i < this.data.landmarkCount; i++) {
      const [x, y] = this.data.positions[i];
      const horizontal = Math.exp(-Math.pow((x - this.mouthX) / (this.mouthWidth * 0.66), 4) * 1.5);
      let movement = 0;
      if (y >= lowerLip) {
        movement =
          jawTravel * horizontal * Math.exp(-Math.pow((y - lowerLip) / (this.mouthWidth * 0.8), 2));
      } else if (y <= upperLip) {
        movement =
          -jawTravel *
          0.16 *
          horizontal *
          Math.exp(-Math.pow((y - upperLip) / (this.mouthWidth * 0.24), 2));
      } else {
        movement =
          jawTravel * horizontal * ((y - this.mouthY) / Math.max(0.002, lowerLip - upperLip));
      }
      this.positions[i * 3 + 1] -= movement * this.ratio * 2;
    }
    // Closed-lip detections can overlap by a fraction of a pixel. Semantic lip
    // indices keep upper and lower boundaries separated even in that case.
    this.data.mouthLoop.forEach((index, i) => {
      const x = this.data.positions[index][0];
      const centerWeight = Math.sqrt(
        Math.max(0, 1 - Math.pow((x - this.mouthX) / (this.mouthWidth / 2), 2)),
      );
      const movement = jawTravel * centerWeight * (i <= 10 ? -0.16 : 1);
      this.positions[index * 3 + 1] = this.rest[index * 3 + 1] - movement * this.ratio * 2;
    });
    for (const eye of eyelids) {
      const a = eye.upper[0],
        b = eye.upper[eye.upper.length - 1];
      for (const index of new Set([...eye.upper, ...eye.lower])) {
        const t = clamp(
          (this.rest[index * 3] - this.rest[a * 3]) / (this.rest[b * 3] - this.rest[a * 3]),
        );
        const closedY = this.rest[a * 3 + 1] * (1 - t) + this.rest[b * 3 + 1] * t;
        this.positions[index * 3 + 1] += (closedY - this.positions[index * 3 + 1]) * lid * 0.98;
      }
    }
    // The aperture has its own interior surface, so opening does not stretch a photographed mouth cap.
    const center = [0, 0, 0];
    this.data.mouthLoop.forEach((index, i) => {
      const point = this.positions.subarray(index * 3, index * 3 + 3);
      this.mouth.set([point[0], point[1], point[2] - 0.007], (i + 1) * 3);
      for (let d = 0; d < 3; d++) center[d] += point[d] / this.data.mouthLoop.length;
    });
    this.mouth.set([center[0], center[1], center[2] - 0.018], 0);
    return this.positions;
  }
}

export function speechOpening(seconds: number, cue: number) {
  const syllable = Math.sin(seconds * 16.5) * 0.28 + Math.sin(seconds * 26.1 + 0.7) * 0.12;
  return clamp((0.46 + syllable) * clamp(cue, 0.18, 1), 0.06, 0.85);
}

export function blinkAt(seconds: number) {
  const phase = seconds % 4.7;
  return phase < 0.19 ? Math.sin((phase / 0.19) * Math.PI) : 0;
}
