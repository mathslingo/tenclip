/**
 * YOLO pose + tennis detect engine (main thread or Worker).
 * Tennis: COCO sports ball (cls 32) with optional ROI crop.
 */
(function (root) {
  var SPORTS_BALL_CLS = 32;

  function clamp(v, lo, hi) {
    return Math.min(hi, Math.max(lo, v));
  }

  function computeRoiRect(srcW, srcH, hint, roiMin, roiMax) {
    if (!hint || hint.cx == null || !isFinite(hint.cx)) return null;
    var boxSpan = Math.max(hint.boxW || 0, hint.boxH || 0);
    var side = Math.max(roiMin, Math.min(roiMax, boxSpan * 4 || roiMin));
    side = Math.round(Math.min(side, srcW, srcH));
    if (side < 64) return null;
    var x = Math.round(hint.cx - side / 2);
    var y = Math.round(hint.cy - side / 2);
    x = clamp(x, 0, srcW - side);
    y = clamp(y, 0, srcH - side);
    return { x: x, y: y, w: side, h: side };
  }

  function createYoloEngine(ort, cfg, opts) {
    opts = opts || {};
    cfg = cfg || {};
    var imgsz = cfg.imgsz || 640;
    var tennisRoiImgsz = cfg.tennisRoiImgsz || 320;
    var tennisFullImgsz = cfg.tennisFullImgsz || imgsz;
    var tennisRoiSession = null;
    var roiMin = cfg.tennisRoiMin || 256;
    var roiMax = cfg.tennisRoiMax || 384;
    var roiMissMax = cfg.tennisRoiMissMax != null ? cfg.tennisRoiMissMax : 2;
    var roiEnabled = cfg.tennisRoi !== false;
    var confThresh = cfg.confThresh != null ? cfg.confThresh : 0.25;
    var tennisConf = cfg.tennisConf != null ? cfg.tennisConf : 0.2;
    var iouThresh = cfg.iouThresh != null ? cfg.iouThresh : 0.45;
    var maxDet = cfg.maxDet || 20;
    var maxTennis = cfg.maxTennis || 3;
    var inWorker = !!opts.inWorker;
    var wasmPaths = opts.wasmPaths || "";

    var session = null;
    var tennisSession = null;
    var poseInputName = "images";
    var tennisInputName = "images";
    var tennisMode = "off";
    var backendPref = "cpu";
    var backendName = "wasm";
    var gpuNote = "";
    var gpuProbe = null;
    var inputBufs = {};
    var letterboxCanvas = null;
    var letterboxCtx = null;
    var hsvCanvas = null;
    var hsvCtx = null;

    function ensureOrtEnv() {
      if (!ort) throw new Error("onnxruntime-web 未加载");
      ort.env.wasm = ort.env.wasm || {};
      if (wasmPaths) ort.env.wasm.wasmPaths = wasmPaths;
      var isolated = typeof self !== "undefined" && !!self.crossOriginIsolated;
      // Worker 内开 pthread 会再 spwan Worker，Safari / COEP 下经常直接失败
      ort.env.wasm.numThreads =
        inWorker || !isolated
          ? 1
          : Math.max(1, Math.min(4, (navigator && navigator.hardwareConcurrency) || 1));
      ort.env.wasm.simd = true;
      // WebGPU 与 Worker 内不要开 wasm.proxy（嵌套 Worker 不稳定）
      ort.env.wasm.proxy = false;
    }

    function makeCanvas(w, h) {
      if (typeof OffscreenCanvas !== "undefined") {
        return new OffscreenCanvas(w, h);
      }
      var c = document.createElement("canvas");
      c.width = w;
      c.height = h;
      return c;
    }

    function get2d(size) {
      if (
        !letterboxCanvas ||
        letterboxCanvas.width !== size ||
        letterboxCanvas.height !== size
      ) {
        letterboxCanvas = makeCanvas(size, size);
        letterboxCtx = letterboxCanvas.getContext("2d", {
          willReadFrequently: true,
        });
      }
      return letterboxCtx;
    }

    function srcSize(source) {
      return {
        w: source.width || source.videoWidth || source.naturalWidth,
        h: source.height || source.videoHeight || source.naturalHeight,
      };
    }

    function letterbox(source, size, crop) {
      var dim = srcSize(source);
      var sx = crop ? crop.x : 0;
      var sy = crop ? crop.y : 0;
      var iw = crop ? crop.w : dim.w;
      var ih = crop ? crop.h : dim.h;
      var scale = Math.min(size / iw, size / ih);
      var nw = Math.round(iw * scale);
      var nh = Math.round(ih * scale);
      var left = Math.floor((size - nw) / 2);
      var top = Math.floor((size - nh) / 2);

      var ctx = get2d(size);
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, size, size);
      ctx.drawImage(source, sx, sy, iw, ih, left, top, nw, nh);

      var data = ctx.getImageData(0, 0, size, size).data;
      var plane = size * size;
      var key = String(3 * plane);
      if (!inputBufs[key] || inputBufs[key].length !== 3 * plane) {
        inputBufs[key] = new Float32Array(3 * plane);
      }
      var float = inputBufs[key];
      for (var i = 0, p = 0; i < data.length; i += 4, p++) {
        float[p] = data[i] / 255;
        float[p + plane] = data[i + 1] / 255;
        float[p + plane * 2] = data[i + 2] / 255;
      }
      return {
        tensor: float,
        size: size,
        meta: {
          scale: scale,
          padX: left,
          padY: top,
          cropX: sx,
          cropY: sy,
        },
      };
    }

    function mapBox(cx, cy, w, h, meta) {
      return {
        x1: (cx - w / 2 - meta.padX) / meta.scale + (meta.cropX || 0),
        y1: (cy - h / 2 - meta.padY) / meta.scale + (meta.cropY || 0),
        x2: (cx + w / 2 - meta.padX) / meta.scale + (meta.cropX || 0),
        y2: (cy + h / 2 - meta.padY) / meta.scale + (meta.cropY || 0),
      };
    }

    function iou(a, b) {
      var x1 = Math.max(a.x1, b.x1);
      var y1 = Math.max(a.y1, b.y1);
      var x2 = Math.min(a.x2, b.x2);
      var y2 = Math.min(a.y2, b.y2);
      var inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
      var ua =
        (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter;
      return ua <= 0 ? 0 : inter / ua;
    }

    function nms(dets, maxKeep) {
      dets.sort(function (a, b) {
        return b.score - a.score;
      });
      var keep = [];
      var limit = maxKeep != null ? maxKeep : maxDet;
      for (var i = 0; i < dets.length; i++) {
        var d = dets[i];
        var ok = true;
        for (var k = 0; k < keep.length; k++) {
          if (iou(d, keep[k]) > iouThresh) {
            ok = false;
            break;
          }
        }
        if (ok) keep.push(d);
        if (keep.length >= limit) break;
      }
      return keep;
    }

    function decodePose(out, meta) {
      var dims = out.dims;
      var data = out.data;
      var num;
      var rows;
      if (dims.length === 3 && dims[1] === 56) {
        num = dims[2];
        rows = new Float32Array(num * 56);
        for (var i = 0; i < num; i++) {
          for (var c = 0; c < 56; c++) rows[i * 56 + c] = data[c * num + i];
        }
      } else if (dims.length === 3 && dims[2] === 56) {
        num = dims[1];
        rows = data instanceof Float32Array ? data : new Float32Array(data);
      } else {
        throw new Error("意外 pose 输出形状: " + dims.join("x"));
      }
      var dets = [];
      for (var j = 0; j < num; j++) {
        var o = j * 56;
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
            x: (rows[base] - meta.padX) / meta.scale + (meta.cropX || 0),
            y: (rows[base + 1] - meta.padY) / meta.scale + (meta.cropY || 0),
            conf: rows[base + 2],
          });
        }
        var box = mapBox(cx, cy, w, h, meta);
        box.score = score;
        box.kpts = kpts;
        dets.push(box);
      }
      return nms(dets);
    }

    function decodeDetectSportsBall(out, meta) {
      var dims = out.dims;
      var data = out.data;
      var num;
      var channels;
      var get;
      if (dims.length === 3 && dims[1] >= 84 && dims[1] <= 144) {
        channels = dims[1];
        num = dims[2];
        get = function (c, i) {
          return data[c * num + i];
        };
      } else if (dims.length === 3 && dims[2] >= 84 && dims[2] <= 144) {
        num = dims[1];
        channels = dims[2];
        get = function (c, i) {
          return data[i * channels + c];
        };
      } else {
        throw new Error("意外 detect 输出形状: " + dims.join("x"));
      }
      var clsCount = channels - 4;
      if (SPORTS_BALL_CLS >= clsCount) {
        throw new Error("输出类别数不足，无法取 sports ball");
      }
      var dets = [];
      for (var i = 0; i < num; i++) {
        var score = get(4 + SPORTS_BALL_CLS, i);
        if (score < tennisConf) continue;
        var box = mapBox(get(0, i), get(1, i), get(2, i), get(3, i), meta);
        box.score = score;
        dets.push(box);
      }
      return nms(dets, maxTennis);
    }

    function detectTennisHsv(source, crop) {
      var dim = srcSize(source);
      var sx = crop ? crop.x : 0;
      var sy = crop ? crop.y : 0;
      var w = crop ? crop.w : dim.w;
      var h = crop ? crop.h : dim.h;
      if (!hsvCanvas || hsvCanvas.width !== w || hsvCanvas.height !== h) {
        hsvCanvas = makeCanvas(w, h);
        hsvCtx = hsvCanvas.getContext("2d", { willReadFrequently: true });
      }
      hsvCtx.drawImage(source, sx, sy, w, h, 0, 0, w, h);
      var img = hsvCtx.getImageData(0, 0, w, h);
      var d = img.data;
      var mask = new Uint8Array(w * h);
      var count = 0;
      for (var i = 0, p = 0; i < d.length; i += 4, p++) {
        var r = d[i] / 255;
        var g = d[i + 1] / 255;
        var b = d[i + 2] / 255;
        var max = Math.max(r, g, b);
        var min = Math.min(r, g, b);
        var v = max;
        var s = max === 0 ? 0 : (max - min) / max;
        var hue = 0;
        if (max !== min) {
          if (max === r) hue = ((g - b) / (max - min)) * 60;
          else if (max === g) hue = (2 + (b - r) / (max - min)) * 60;
          else hue = (4 + (r - g) / (max - min)) * 60;
          if (hue < 0) hue += 360;
        }
        if (hue >= 35 && hue <= 95 && s >= 0.35 && v >= 0.35) {
          mask[p] = 1;
          count++;
        }
      }
      if (count < 8) return [];
      var visited = new Uint8Array(w * h);
      var blobs = [];
      var stack = [];
      for (var y = 0; y < h; y++) {
        for (var x = 0; x < w; x++) {
          var start = y * w + x;
          if (!mask[start] || visited[start]) continue;
          var minX = x;
          var maxX = x;
          var minY = y;
          var maxY = y;
          var area = 0;
          stack.length = 0;
          stack.push(start);
          visited[start] = 1;
          while (stack.length) {
            var idx = stack.pop();
            var cx = idx % w;
            var cy = (idx / w) | 0;
            area++;
            if (cx < minX) minX = cx;
            if (cx > maxX) maxX = cx;
            if (cy < minY) minY = cy;
            if (cy > maxY) maxY = cy;
            var neigh = [idx - 1, idx + 1, idx - w, idx + w];
            for (var n = 0; n < neigh.length; n++) {
              var ni = neigh[n];
              if (ni < 0 || ni >= mask.length) continue;
              if (!mask[ni] || visited[ni]) continue;
              visited[ni] = 1;
              stack.push(ni);
            }
          }
          var bw = maxX - minX + 1;
          var bh = maxY - minY + 1;
          if (area < 12 || bw < 4 || bh < 4) continue;
          if (bw > w * 0.35 || bh > h * 0.35) continue;
          var aspect = bw / bh;
          if (aspect < 0.45 || aspect > 2.2) continue;
          blobs.push({
            x1: minX + sx,
            y1: minY + sy,
            x2: maxX + 1 + sx,
            y2: maxY + 1 + sy,
            score: Math.min(0.95, 0.4 + area / 800),
            area: area,
          });
        }
      }
      blobs.sort(function (a, b) {
        return b.area - a.area;
      });
      return blobs.slice(0, maxTennis).map(function (b) {
        return { x1: b.x1, y1: b.y1, x2: b.x2, y2: b.y2, score: b.score };
      });
    }

    async function probeWebGpu() {
      if (gpuProbe) return gpuProbe;
      if (!navigator.gpu) {
        gpuProbe = {
          ok: false,
          reason: "浏览器无 WebGPU（Safari 需 18+ / macOS Sequoia）",
        };
        return gpuProbe;
      }
      try {
        var adapter = await navigator.gpu.requestAdapter();
        gpuProbe = adapter
          ? { ok: true, reason: "" }
          : { ok: false, reason: "无可用 GPU 适配器" };
      } catch (e) {
        gpuProbe = {
          ok: false,
          reason: "requestAdapter 失败：" + (e.message || e),
        };
      }
      return gpuProbe;
    }

    async function warmup(sess, size) {
      var feeds = {};
      feeds[sess.inputNames[0] || "images"] = new ort.Tensor(
        "float32",
        new Float32Array(3 * size * size),
        [1, 3, size, size]
      );
      await sess.run(feeds);
    }

    async function createSession(buf, size) {
      ensureOrtEnv();
      var tryGpu = backendPref === "gpu";
      // Safari Worker 里 WebGPU 常能 requestAdapter 却跑不了会话
      if (inWorker && tryGpu) {
        tryGpu = false;
        gpuNote = "Worker 使用 WASM（主线程可开 WebGPU）";
      }
      if (tryGpu) {
        var probe = await probeWebGpu();
        if (probe.ok) {
          try {
            var sGpu = await ort.InferenceSession.create(buf, {
              executionProviders: ["webgpu"],
              graphOptimizationLevel: "all",
            });
            await warmup(sGpu, size);
            backendName = "webgpu";
            gpuNote = "";
            ort.env.wasm.proxy = false;
            return sGpu;
          } catch (e) {
            console.warn("WebGPU 会话不可用，回退 CPU", e);
            gpuNote = "WebGPU 失败：" + (e.message || e);
          }
        } else {
          gpuNote = probe.reason;
        }
      } else {
        gpuNote = "";
      }
      var sCpu = await ort.InferenceSession.create(buf, {
        executionProviders: ["wasm"],
        graphOptimizationLevel: "all",
      });
      var n = ort.env.wasm.numThreads || 1;
      backendName = n > 1 ? "wasm x" + n : "wasm";
      await warmup(sCpu, size);
      return sCpu;
    }

    function releaseSession(s) {
      if (s && typeof s.release === "function") {
        try {
          s.release();
        } catch (_) {}
      }
    }

    async function loadPose(buf, pref) {
      if (pref) backendPref = pref;
      gpuProbe = null;
      releaseSession(session);
      session = await createSession(buf, imgsz);
      poseInputName = session.inputNames[0] || "images";
    }

    async function loadTennis(buf, roiBuf) {
      releaseSession(tennisRoiSession);
      tennisRoiSession = null;
      if (!buf) {
        tennisSession = null;
        tennisMode = "hsv";
        return false;
      }
      try {
        releaseSession(tennisSession);
        tennisSession = await createSession(buf, tennisFullImgsz);
        tennisInputName = tennisSession.inputNames[0] || "images";
        if (roiBuf) {
          try {
            tennisRoiSession = await createSession(roiBuf, tennisRoiImgsz);
          } catch (e2) {
            console.warn("tennis ROI onnx skipped", e2);
            tennisRoiSession = null;
          }
        }
        tennisMode = "onnx";
        return true;
      } catch (e) {
        console.warn("tennis onnx unavailable, HSV fallback", e);
        tennisSession = null;
        tennisRoiSession = null;
        tennisMode = "hsv";
        return false;
      }
    }

    function dropTennis() {
      releaseSession(tennisSession);
      releaseSession(tennisRoiSession);
      tennisSession = null;
      tennisRoiSession = null;
      tennisMode = "off";
    }

    async function rebuild(pref, poseBuf, tennisBuf, tennisRoiBuf) {
      backendPref = pref || backendPref;
      gpuProbe = null;
      var needTennis = tennisSession != null || tennisMode === "onnx";
      releaseSession(session);
      releaseSession(tennisSession);
      releaseSession(tennisRoiSession);
      session = null;
      tennisSession = null;
      tennisRoiSession = null;
      await loadPose(poseBuf, backendPref);
      if (needTennis && tennisBuf) await loadTennis(tennisBuf, tennisRoiBuf);
    }

    function makeFeed(name, tensor, size) {
      var feeds = {};
      feeds[name] = new ort.Tensor("float32", tensor, [1, 3, size, size]);
      return feeds;
    }

    async function runFrame(source, tennisEnabled, roiHint) {
      if (!session) throw new Error("姿态模型未就绪");
      var tAll = performance.now();
      var poseLb = letterbox(source, imgsz, null);
      var poseP = session.run(makeFeed(poseInputName, poseLb.tensor, imgsz));

      var tennisP = null;
      var tennisMeta = null;
      var usedRoi = false;
      var tennisSize = tennisFullImgsz;
      var roiRect = null;
      var miss = roiHint && roiHint.miss != null ? roiHint.miss : 99;

      if (tennisEnabled && tennisMode === "onnx" && tennisSession) {
        if (roiEnabled && miss < roiMissMax) {
          roiRect = computeRoiRect(
            srcSize(source).w,
            srcSize(source).h,
            roiHint,
            roiMin,
            roiMax
          );
        }
        if (roiRect) {
          var roiSize = tennisRoiSession ? tennisRoiImgsz : tennisFullImgsz;
          var roiSess = tennisRoiSession || tennisSession;
          var roiLb = letterbox(source, roiSize, roiRect);
          tennisMeta = roiLb.meta;
          tennisSize = roiSize;
          usedRoi = true;
          tennisP = roiSess.run(
            makeFeed(roiSess.inputNames[0] || tennisInputName, roiLb.tensor, roiSize)
          );
        } else if (tennisFullImgsz === imgsz) {
          tennisMeta = poseLb.meta;
          tennisP = tennisSession.run(
            makeFeed(tennisInputName, poseLb.tensor, imgsz)
          );
        } else {
          var fullLb = letterbox(source, tennisFullImgsz, null);
          tennisMeta = fullLb.meta;
          tennisSize = tennisFullImgsz;
          tennisP = tennisSession.run(
            makeFeed(tennisInputName, fullLb.tensor, tennisFullImgsz)
          );
        }
      } else if (tennisEnabled && tennisMode === "hsv") {
        if (roiEnabled && miss < roiMissMax) {
          roiRect = computeRoiRect(
            srcSize(source).w,
            srcSize(source).h,
            roiHint,
            roiMin,
            roiMax
          );
        }
        tennisP = Promise.resolve(detectTennisHsv(source, roiRect));
        usedRoi = !!roiRect;
      }

      var t0 = performance.now();
      var poseOut;
      var tennisOut;
      if (tennisP) {
        var both = await Promise.all([poseP, tennisP]);
        poseOut = both[0];
        tennisOut = both[1];
      } else {
        poseOut = await poseP;
        tennisOut = null;
      }
      var wallMs = performance.now() - t0;

      var persons = decodePose(poseOut[session.outputNames[0]], poseLb.meta);
      var balls = [];
      if (tennisEnabled && tennisMode === "onnx" && tennisOut) {
        var detSess = usedRoi && tennisRoiSession ? tennisRoiSession : tennisSession;
        balls = decodeDetectSportsBall(
          tennisOut[detSess.outputNames[0]],
          tennisMeta
        );
      } else if (tennisEnabled && tennisMode === "hsv" && tennisOut) {
        balls = tennisOut;
      }

      return {
        persons: persons,
        balls: balls,
        poseMs: wallMs,
        tennisMs: tennisEnabled ? wallMs : 0,
        totalMs: performance.now() - tAll,
        tennisMode: tennisEnabled ? tennisMode : null,
        usedRoi: usedRoi,
        tennisSize: tennisEnabled ? tennisSize : null,
        backendName: backendName,
        gpuNote: gpuNote,
      };
    }

    function release() {
      releaseSession(session);
      releaseSession(tennisSession);
      releaseSession(tennisRoiSession);
      session = null;
      tennisSession = null;
      tennisRoiSession = null;
    }

    return {
      get backendName() {
        return backendName;
      },
      get gpuNote() {
        return gpuNote;
      },
      get tennisMode() {
        return tennisMode;
      },
      loadPose: loadPose,
      loadTennis: loadTennis,
      dropTennis: dropTennis,
      rebuild: rebuild,
      runFrame: runFrame,
      release: release,
    };
  }

  root.createYoloEngine = createYoloEngine;
  root.YOLO_SPORTS_BALL_CLS = SPORTS_BALL_CLS;
})(typeof self !== "undefined" ? self : window);
