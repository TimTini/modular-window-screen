export function calculate(width) {
  if (!Number.isFinite(width) || width < 430 || width > 500) {
    throw new RangeError('Chiều rộng phải nằm trong khoảng 430–500 mm.');
  }

  const hingePitch = 42;
  const hingeBarrelRadius = 4;
  const leafCount = 12;
  const dx = (width - 20) / leafCount;
  const dz = Math.sqrt(hingePitch ** 2 - dx ** 2);
  const axes = Array.from({ length: leafCount + 1 }, (_, i) => ({
    x: 10 + dx * i,
    z: i % 2 ? dz : 0,
  }));
  const overlap = 530 - width;
  const rotorLength = 140;
  const rotorEnd = width;
  const rotorStart = rotorEnd - rotorLength;
  const jointAxis = width - 10;

  return {
    width,
    height: 200,
    axes,
    foldDepth: dz,
    hingePitch,
    hingeBarrelRadius,
    panelLength: hingePitch,
    outsideLeafWidth: hingePitch + 2 * hingeBarrelRadius,
    leafCount,
    rod: { start: 10, end: 185, length: 175, z: -30 },
    extension: {
      start: 160, end: 390, length: 230, socketDepth: 25, shoulder: 5,
      tipStart: 280, tipLength: 110, radius: 16,
    },
    rotorEnd,
    rotorLength,
    rotor: {
      start: rotorStart, end: rotorEnd, jointAxis, clearance: 0.6,
      innerBoreRadius: 16.1875 / 2, threadLength: 118, threadOffset: -0.25,
      outerProfile: [[0, 14], [120, 14], [122, 12], [130, 12], [134, 16], [138, 12], [140, 12]],
    },
    rightRing: {
      axisX: jointAxis, axisY: 100, axisZ: -30, outerRadius: 20, start: -3, end: 10,
      cavityProfile: [[-3, 12.6], [0, 12.6], [4, 16.6], [8, 12.6], [10, 12.6]],
    },
    overlap,
    turnsFrom500: (overlap - 30) / 4,
  };
}
