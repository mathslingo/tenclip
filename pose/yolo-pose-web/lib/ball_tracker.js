/**
 * Tennis ball multi-frame tracker + planar distance / speed estimate.
 * Scale: ball diameter ≈ 6.7 cm → meters-per-pixel from bbox size.
 */
(function (global) {
  var BALL_DIAMETER_M = 0.067;

  function createBallTracker(opts) {
    opts = opts || {};
    var maxMiss = opts.maxMiss != null ? opts.maxMiss : 12;
    var matchPx = opts.matchPx != null ? opts.matchPx : 80;
    var smooth = opts.smooth != null ? opts.smooth : 0.55;
    var maxTrail = opts.maxTrail != null ? opts.maxTrail : 60;

    var track = null;

    function reset() {
      track = null;
    }

    function metersPerPixel(box) {
      var d = Math.max(4, (box.w + box.h) / 2);
      return BALL_DIAMETER_M / d;
    }

    /**
     * @param {{x1,y1,x2,y2,score}|null} box  image-space box
     * @param {number} nowMs  performance.now() or video time * 1000
     */
    function update(box, nowMs) {
      nowMs = nowMs != null ? nowMs : performance.now();

      if (!box) {
        if (track) {
          track.miss += 1;
          if (track.miss > maxMiss) track = null;
        }
        return snapshot();
      }

      var cx = (box.x1 + box.x2) / 2;
      var cy = (box.y1 + box.y2) / 2;
      var w = box.x2 - box.x1;
      var h = box.y2 - box.y1;
      var mpp = metersPerPixel({ w: w, h: h });

      if (!track) {
        track = {
          id: 1,
          cx: cx,
          cy: cy,
          miss: 0,
          trail: [{ x: cx, y: cy, t: nowMs }],
          distM: 0,
          speedMps: 0,
          speedKmh: 0,
          mpp: mpp,
        };
        return snapshot();
      }

      var dx = cx - track.cx;
      var dy = cy - track.cy;
      var distPx = Math.sqrt(dx * dx + dy * dy);
      var thresh = Math.max(matchPx, 2.5 * (track.speedMps / Math.max(track.mpp, 1e-6)) * 0.033);
      if (distPx > thresh && track.miss === 0 && distPx > matchPx * 1.8) {
        // likely a new ball / hit reset
        track = {
          id: track.id + 1,
          cx: cx,
          cy: cy,
          miss: 0,
          trail: [{ x: cx, y: cy, t: nowMs }],
          distM: 0,
          speedMps: 0,
          speedKmh: 0,
          mpp: mpp,
        };
        return snapshot();
      }

      var last = track.trail[track.trail.length - 1];
      var dt = Math.max(1e-3, (nowMs - last.t) / 1000);
      var stepM = distPx * mpp;
      var inst = stepM / dt;

      track.cx = smooth * cx + (1 - smooth) * track.cx;
      track.cy = smooth * cy + (1 - smooth) * track.cy;
      track.mpp = smooth * mpp + (1 - smooth) * track.mpp;
      track.miss = 0;
      track.distM += stepM;
      track.speedMps = smooth * inst + (1 - smooth) * track.speedMps;
      track.speedKmh = track.speedMps * 3.6;
      track.trail.push({ x: track.cx, y: track.cy, t: nowMs });
      if (track.trail.length > maxTrail) track.trail.shift();

      return snapshot();
    }

    function snapshot() {
      if (!track) {
        return {
          active: false,
          trail: [],
          distM: 0,
          speedKmh: 0,
          speedMps: 0,
          cx: 0,
          cy: 0,
        };
      }
      return {
        active: true,
        id: track.id,
        trail: track.trail.slice(),
        distM: track.distM,
        speedKmh: track.speedKmh,
        speedMps: track.speedMps,
        cx: track.cx,
        cy: track.cy,
        mpp: track.mpp,
      };
    }

    return { update: update, reset: reset, snapshot: snapshot };
  }

  global.createBallTracker = createBallTracker;
  global.TENNIS_BALL_DIAMETER_M = BALL_DIAMETER_M;
})(typeof window !== "undefined" ? window : globalThis);
