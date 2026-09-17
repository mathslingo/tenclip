/* eslint-disable no-undef */
importScripts("./ort/ort.webgpu.min.js");
self.ort.env.wasm = self.ort.env.wasm || {};
self.ort.env.wasm.wasmPaths = new URL("./ort/", self.location).href;
importScripts("./yolo_infer.js?v=20260918c");

var wasmPaths = new URL("./ort/", self.location).href;
var engine = null;
var poseBuf = null;
var tennisBuf = null;
var tennisRoiBuf = null;
var handleChain = Promise.resolve();

function snapshotMeta() {
  return {
    backendName: engine ? engine.backendName : "wasm",
    gpuNote: engine ? engine.gpuNote : "",
    tennisMode: engine ? engine.tennisMode : "off",
  };
}

function reply(msg, extra) {
  extra = extra || {};
  extra.id = msg && msg.id;
  extra.type = extra.type || "ok";
  self.postMessage(Object.assign(extra, snapshotMeta()));
}

self.onmessage = function (ev) {
  var msg = ev.data || {};
  handleChain = handleChain.then(function () {
    return handle(msg);
  }).catch(function (e) {
    self.postMessage({
      type: "error",
      id: msg.id,
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
    reply(msg, { type: "ready" });
    return;
  }

  if (!engine) throw new Error("engine 未 init");

  if (msg.type === "load-tennis") {
    tennisBuf = msg.tennisBuf || null;
    tennisRoiBuf = msg.tennisRoiBuf || null;
    var ok = await engine.loadTennis(tennisBuf, tennisRoiBuf);
    reply(msg, { type: "tennis-ready", onnx: ok });
    return;
  }

  if (msg.type === "drop-tennis") {
    engine.dropTennis();
    tennisBuf = null;
    tennisRoiBuf = null;
    reply(msg, { type: "tennis-dropped" });
    return;
  }

  if (msg.type === "rebuild") {
    if (msg.poseBuf) poseBuf = msg.poseBuf;
    if (msg.tennisBuf) tennisBuf = msg.tennisBuf;
    if (msg.tennisRoiBuf) tennisRoiBuf = msg.tennisRoiBuf;
    await engine.rebuild(msg.backendPref, poseBuf, tennisBuf, tennisRoiBuf);
    reply(msg, { type: "ready" });
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
    reply(msg, { type: "result", result: result });
    return;
  }

  throw new Error("未知消息 " + msg.type);
}
