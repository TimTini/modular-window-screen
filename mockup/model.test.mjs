import assert from 'node:assert/strict';
import test from 'node:test';
import { calculate } from './model.mjs';

test('keeps twelve 42 mm hinge intervals across thirteen alternating axes at each width', () => {
  for (const width of [430, 465, 500]) {
    const model = calculate(width);
    assert.equal(model.width, width);
    assert.equal(model.height, 200);
    assert.equal(model.axes.length, 13);
    assert.equal(model.panelLength, 42);
    assert.equal(model.outsideLeafWidth, 50);
    for (let i = 0; i < model.axes.length - 1; i++) {
      const a = model.axes[i];
      const b = model.axes[i + 1];
      assert.ok(Math.abs(Math.hypot(b.x - a.x, b.z - a.z) - 42) < 1e-9);
      assert.equal(a.z === 0, i % 2 === 0);
    }
  }
});

test('outer hinge axes stay ten millimetres from each edge', () => {
  for (const width of [430, 465, 500]) {
    const { axes } = calculate(width);
    assert.equal(axes[0].x, 10);
    assert.equal(axes.at(-1).x, width - 10);
  }
});

test('thread offset defaults to -0.25 mm on both mating profiles', () => {
  const { rotor } = calculate(500);
  assert.equal(rotor.threadOffset, -0.25);
  assert.equal(rotor.innerBoreRadius, 8.09375);
});

test('rod is a 175 mm stub plus a 230 mm extension, both printable on a 250 mm bed', () => {
  for (const width of [430, 465, 500]) {
    const model = calculate(width);
    assert.equal(model.rod.length, 175);
    assert.equal(model.rod.start, 10);
    assert.equal(model.rod.end, 185);
    assert.equal(model.extension.length, 230);
    assert.equal(model.extension.start, 160);
    assert.equal(model.extension.end, 390);
    assert.equal(model.extension.start + model.extension.socketDepth, model.rod.end);
    assert.equal(model.extension.tipLength, 110);
    assert.equal(model.extension.tipStart, 280);
    assert.ok(model.rod.length < 250);
    assert.ok(model.extension.length < 250);
    assert.equal(model.overlap, 530 - width);
    assert.ok(model.overlap >= 30);
    assert.ok(model.extension.tipStart <= width - 140);
  }
});

test('right end uses a 140 mm captive rotor and a 0.6 mm radial clearance', () => {
  const radiusAt = (profile, x) => {
    const i = profile.findIndex(([position]) => position >= x);
    if (profile[i][0] === x) return profile[i][1];
    const [x0, r0] = profile[i - 1];
    const [x1, r1] = profile[i];
    return r0 + (r1 - r0) * (x - x0) / (x1 - x0);
  };
  for (const width of [430, 465, 500]) {
    const model = calculate(width);
    assert.equal(model.rotorEnd, width);
    assert.equal(model.rotorLength, 140);
    assert.equal(model.rotor.start, width - 140);
    assert.equal(model.rotor.jointAxis, width - 10);
    assert.equal(model.rotor.clearance, 0.6);
    assert.equal(model.rotor.innerBoreRadius, 8.09375);
    assert.equal(model.rotor.threadOffset, -0.25);
    assert.equal(model.rotor.threadLength, 118);
    assert.equal(model.rightRing.axisX, width - 10);
    assert.equal(model.rightRing.axisY, 100);
    assert.equal(model.rightRing.axisZ, -30);
    assert.deepEqual(model.rightRing.cavityProfile, [[-3, 12.6], [0, 12.6], [4, 16.6], [8, 12.6], [10, 12.6]]);
    assert.deepEqual(model.rotor.outerProfile, [[0, 14], [120, 14], [122, 12], [130, 12], [134, 16], [138, 12], [140, 12]]);
    for (const [rotorX, cavityX] of [[127, -3], [130, 0], [134, 4], [138, 8], [140, 10]]) {
      const rotorRadius = radiusAt(model.rotor.outerProfile, rotorX);
      const cavityRadius = radiusAt(model.rightRing.cavityProfile, cavityX);
      assert.ok(Math.abs(cavityRadius - rotorRadius - model.rotor.clearance) < 1e-9);
    }
  }
});

test('turn count is referenced to the 500 mm opening', () => {
  const model = calculate(500);
  assert.equal(model.overlap, 30);
  assert.equal(model.turnsFrom500, 0);
  assert.equal(calculate(465).turnsFrom500, 8.75);
  assert.equal(calculate(430).turnsFrom500, 17.5);
});

test('rejects widths outside the stated 430 to 500 mm range', () => {
  for (const width of [429, 501, NaN, Infinity]) {
    assert.throws(() => calculate(width), RangeError);
  }
});
