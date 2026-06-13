const { WEB_STROKE_URL, WEB_ANALYZE_URL } = require("../../utils/config");

function copyAndHint(url, name) {
  wx.setClipboardData({
    data: url,
    success: function () {
      wx.showModal({
        title: "链接已复制",
        content:
          name +
          " 地址已复制。\n\n请：\n1. 打开任意微信聊天\n2. 粘贴并发送\n3. 点击链接打开（与之前测试 health 相同方式）",
        showCancel: false,
        confirmText: "知道了",
      });
    },
  });
}

Page({
  goStrokeWebView() {
    wx.navigateTo({ url: "/pages/h5-stroke/index" });
  },
  goAnalyzeWebView() {
    wx.navigateTo({ url: "/pages/h5-analyze/index" });
  },
  copyStroke() {
    copyAndHint(WEB_STROKE_URL, "击球片段提取");
  },
  copyAnalyze() {
    copyAndHint(WEB_ANALYZE_URL, "动作分析");
  },
});
