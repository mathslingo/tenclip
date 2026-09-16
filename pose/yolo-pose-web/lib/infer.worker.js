/* eslint-disable no-undef */
importScripts("./ort/ort.webgpu.min.js");
self.ort.env.wasm = self.ort.env.wasm || {};
self.ort.env.wasm.wasmPaths = new URL("./ort/", self.location).href;
importScripts("./yolo_infer.js");

var wasmPaths = new URL("./ort/", self.location).href;
var engine = null;
var poseBuf = null;
var tennisBuf = null;
var tennisRoiBuf = null;

function snapshotMeta() {
  return {
    backendName: engine ? engine.backendName : "wasm",
    gpuNote: engine ? engine.gpuNote : "",
    tennisMode: engine ? engine.tennisMode : "off",
  };
}

self.onmessage = function (ev) {
  var msg = ev.data || {};
  handle(msg).catch(function (e) {
    self.postMessage({
      type: "error",
      op: msg.type,
      message: String((e && e.message) || e),
    });
  });
};

async function handle(msg) {
  if (msg.type === "init") {
    poseBuf = msg.poseBuf;
    engine = self.createYoloEngine(self.ort, msg.cfg, {
      wasmPaths: wasmPaths,
      inWorker: true,
    });
    await engine.loadPose(poseBuf, msg.backendPref);
    self.postMessage(Object.assign({ type: "ready" }, snapshotMeta()));
    return;
  }

  if (!engine) throw new Error("engine 未 init");

  if (msg.type === "load-tennis") {
    tennisBuf = msg.tennisBuf || null;
    tennisRoiBuf = msg.tennisRoiBuf || null;
    var ok = await engine.loadTennis(tennisBuf, tennisRoiBuf);
    self.postMessage(
      Object.assign({ type: "tennis-ready", onnx: ok }, snapshotMeta())
    );
    return;
  }

  if (msg.type === "drop-tennis") {
    engine.dropTennis();
    tennisBuf = null;
    tennisRoiBuf = null;
    self.postMessage(Object.assign({ type: "tennis-dropped" }, snapshotMeta()));
    return;
  }

  if (msg.type === "rebuild") {
    if (msg.poseBuf) poseBuf = msg.poseBuf;
    if (msg.tennisBuf) tennisBuf = msg.tennisBuf;
    if (msg.tennisRoiBuf) tennisRoiBuf = msg.tennisRoiBuf;
    await engine.rebuild(msg.backendPref, poseBuf, tennisBuf, tennisRoiBuf);
    self.postMessage(Object.assign({ type: "ready" }, snapshotMeta()));
    return;
  }

  if (msg.type === "frame") {
    var src = msg.bitmap;
    var result = await engine.runFrame(src, !!msg.tennisEnabled, msg.roiHint);
    if (src && typeof src.close === "function") {
      try {
        src.close();
      } catch (_) {}
    }
    self.postMessage({ type: "result", result: result });
    return;
  }

  throw new Error("未知消息 " + msg.type);
}
