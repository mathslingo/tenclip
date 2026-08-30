/**
 * YOLO11n-pose / YOLOv8n-pose 编解码（与 pose/yolo-pose-web/app.js 对齐）
 * 输出 [1,56,N]：xywh + score + 17×(x,y,conf)
 */

const COCO_EDGES = [
  [5, 6], [5, 7], [7, 9], [6, 8], [8, 10],
  [5, 11], [6, 12], [11, 12], [11, 13], [13, 15],
  [12, 14], [14, 16], [0, 1], [0, 2], [1, 3], [2, 4], [0, 5], [0, 6],
];

function letterboxFromRgba(rgba, srcW, srcH, imgsz, outFloat) {
  const scale = Math.min(imgsz / srcW, imgsz / srcH);
  const nw = Math.round(srcW * scale);
  const nh = Math.round(srcH * scale);
  const padX = Math.floor((imgsz - nw) / 2);
  const padY = Math.floor((imgsz - nh) / 2);

  // 简易最近邻缩放到 letterbox（避免依赖离屏 canvas，真机帧回调更稳）
  const need = 3 * imgsz * imgsz;
  const float = outFloat && outFloat.length === need ? outFloat : new Float32Array(need);
  float.fill(0);
  const plane = imgsz * imgsz;
  const inv255 = 1 / 255;

  for (let y = 0; y < nh; y++) {
    const sy = Math.min(srcH - 1, Math.floor((y + 0.5) / scale));
    for (let x = 0; x < nw; x++) {
      const sx = Math.min(srcW - 1, Math.floor((x + 0.5) / scale));
      const si = (sy * srcW + sx) * 4;
      const dx = x + padX;
      const dy = y + padY;
      const di = dy * imgsz + dx;
      float[di] = rgba[si] * inv255;
      float[di + plane] = rgba[si + 1] * inv255;
      float[di + plane * 2] = rgba[si + 2] * inv255;
    }
  }

  return {
    tensor: float,
    meta: { scale: scale, padX: padX, padY: padY, iw: srcW, ih: srcH },
  };
}

function iou(a, b) {
  const x1 = Math.max(a.x1, b.x1);
  const y1 = Math.max(a.y1, b.y1);
  const x2 = Math.min(a.x2, b.x2);
  const y2 = Math.min(a.y2, b.y2);
  const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  const ua =
    (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter;
  return ua <= 0 ? 0 : inter / ua;
}

function nms(dets, iouThresh, maxDet) {
  dets.sort(function (a, b) {
    return b.score - a.score;
  });
  const keep = [];
  for (var i = 0; i < dets.length; i++) {
    var d = dets[i];
    var ok = true;
    for (var j = 0; j < keep.length; j++) {
      if (iou(d, keep[j]) > iouThresh) {
        ok = false;
        break;
      }
    }
    if (ok) keep.push(d);
    if (keep.length >= maxDet) break;
  }
  return keep;
}

function decodePoseOutput(data, dims, meta, confThresh, iouThresh, maxDet) {
  var num;
  var rows;
  var flat =
    data instanceof Float32Array
      ? data
      : new Float32Array(data.buffer || data);

  if (dims.length === 3 && dims[1] === 56) {
    num = dims[2];
    rows = new Float32Array(num * 56);
    for (var i = 0; i < num; i++) {
      for (var c = 0; c < 56; c++) rows[i * 56 + c] = flat[c * num + i];
    }
  } else if (dims.length === 3 && dims[2] === 56) {
    num = dims[1];
    rows = flat;
  } else {
    throw new Error("意外输出形状: " + dims.join("x"));
  }

  var scale = meta.scale;
  var padX = meta.padX;
  var padY = meta.padY;
  var dets = [];
  for (var i = 0; i < num; i++) {
    var o = i * 56;
    var score = rows[o + 4];
    if (score < confThresh) continue;
    var cx = rows[o];
    var cy = rows[o + 1];
    var w = rows[o + 2];
    var h = rows[o + 3];
    var kpts = [];
    for (var k = 0; k < 17; k++) {
      var base = o + 5 + k * 3;
      kpts.push({
        x: (rows[base] - padX) / scale,
        y: (rows[base + 1] - padY) / scale,
        conf: rows[base + 2],
      });
    }
    dets.push({
      x1: (cx - w / 2 - padX) / scale,
      y1: (cy - h / 2 - padY) / scale,
      x2: (cx + w / 2 - padX) / scale,
      y2: (cy + h / 2 - padY) / scale,
      score: score,
      kpts: kpts,
    });
  }
  return nms(dets, iouThresh, maxDet);
}

/** 把 ArrayBuffer / TypedArray 规范成 Float32Array + dims */
function normalizeOrtOutput(out) {
  if (!out) throw new Error("空输出");
  var data = out.data;
  var dims = out.shape || out.dims;
  if (!dims && data && data.shape) dims = data.shape;
  if (data && data.data) {
    dims = data.shape || dims;
    data = data.data;
  }
  if (data instanceof ArrayBuffer) {
    data = new Float32Array(data);
  } else if (data && data.buffer && !(data instanceof Float32Array)) {
    data = new Float32Array(data.buffer, data.byteOffset || 0, data.byteLength / 4);
  }
  if (!dims) throw new Error("输出无 shape");
  return { data: data, dims: dims };
}

module.exports = {
  COCO_EDGES: COCO_EDGES,
  letterboxFromRgba: letterboxFromRgba,
  decodePoseOutput: decodePoseOutput,
  normalizeOrtOutput: normalizeOrtOutput,
};
