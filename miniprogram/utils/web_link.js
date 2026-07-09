/** @deprecated 兼容旧包；新代码请直接用 config.js 或 stroke-extract 内联逻辑 */
var WEB_STROKE_URL = "https://api.uchance.tech/web/stroke";
var WEB_ANALYZE_URL = "https://api.uchance.tech/web";

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
