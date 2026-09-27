/* Tooling Job Log — on-device background removal worker.
   Runs @imgly/background-removal (ISNet, quantized ~44 MB model + ~12 MB ONNX Runtime WASM) off the UI thread.
   The photo never leaves the phone: only the model/runtime files are downloaded (once, then served
   from the service worker cache). Cancel = the page terminates this worker. */
var LIB = "https://cdn.jsdelivr.net/npm/@imgly/background-removal@1.7.0/+esm";
var DATA = "https://staticimgly.com/@imgly/background-removal-data/1.7.0/dist/";
var libP = null;
function lib(){ return libP || (libP = import(LIB)); }
function cfg(){
  return { publicPath: DATA, model: "isnet_quint8", device: "cpu", output: { format: "image/x-rgba8" },
    progress: function(key, cur, total){ self.postMessage({ type: "progress", key: key, cur: cur, total: total }); } };
}
self.onmessage = function(e){
  var m = e.data || {};
  if(m.type === "preload"){
    lib().then(function(L){ return L.preload(cfg()); })
      .then(function(){ self.postMessage({ type: "ready" }); })
      .catch(function(err){ self.postMessage({ type: "error", message: String(err && err.message || err) }); });
    return;
  }
  if(m.type === "segment"){
    var t0 = Date.now();
    lib().then(function(L){
      // load/compile the model first (memoized), so the page can tell "downloading" from "finding the part"
      return L.preload(cfg()).then(function(){ self.postMessage({ type: "progress", key: "compute:start", cur: 0, total: 1 }); return L.segmentForeground(m.blob, cfg()); });
    })
      .then(function(out){ return out.arrayBuffer(); })
      .then(function(buf){
        var rgba = new Uint8Array(buf), n = rgba.length >> 2, a = new Uint8Array(n);
        for(var i = 0; i < n; i++) a[i] = rgba[i*4 + 3];
        self.postMessage({ type: "mask", alpha: a, w: m.w, h: m.h, ms: Date.now() - t0 }, [a.buffer]);
      })
      .catch(function(err){ self.postMessage({ type: "error", message: String(err && err.message || err) }); });
  }
};
