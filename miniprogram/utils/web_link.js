/** @deprecated 兼容旧包；新代码请用 config.js 的 WEB_STROKE_URL / WEB_ANALYZE_URL */
var cfg = require("./config.js");
var WEB_STROKE_URL = cfg.WEB_STROKE_URL;
var WEB_ANALYZE_URL = cfg.WEB_ANALYZE_URL;

function copyAndHint(url, name) {
  wx.setClipboardData({
    data: url,
    success: function () {
      wx.showModal({
        title: "链接已复制",
        content:
          name +
          " 地址已复制。\n\n请：\n1. 打开任意微信聊天\n2. 粘贴并发送\n3. 点击链接打开",
        showCancel: false,
        confirmText: "知道了",
      });
    },
  });
}

function copyStrokeLink() {
  copyAndHint(WEB_STROKE_URL, "击球片段提取");
}

function copyAnalyzeLink() {
  copyAndHint(WEB_ANALYZE_URL, "动作分析");
}

module.exports = {
  copyAndHint: copyAndHint,
  copyStrokeLink: copyStrokeLink,
  copyAnalyzeLink: copyAnalyzeLink,
  WEB_STROKE_URL: WEB_STROKE_URL,
  WEB_ANALYZE_URL: WEB_ANALYZE_URL,
};
