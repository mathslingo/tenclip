/** @deprecated 兼容旧包；新代码请用 config.js 的 WEB_*_URL */
var cfg = require("./config.js");
var WEB_STROKE_URL = cfg.WEB_STROKE_URL;
var WEB_ANALYZE_URL = cfg.WEB_ANALYZE_URL;
var WEB_POSE_URL = cfg.WEB_POSE_URL;

function copyAndHint(url, name, tip) {
  wx.setClipboardData({
    data: url,
    success: function () {
      wx.showModal({
        title: "链接已复制",
        content:
          tip ||
          name +
            " 地址已复制。\n\n请：\n1. 打开任意微信聊天\n2. 粘贴并发送\n3. 点击链接打开",
        showCancel: false,
        confirmText: "知道了",
      });
    },
  });
}

function copyStrokeLink() {
  copyAndHint(
    WEB_STROKE_URL,
    "击球片段提取",
    "网页版击球剪辑地址已复制。\n\n大视频请用系统浏览器打开（iPhone 推荐 Safari / Chrome），支持分片断点续传：\n1. 打开聊天粘贴发送，点击链接\n2. 或粘贴到浏览器地址栏\n\n上传期间请勿切出浏览器。"
  );
}

function copyAnalyzeLink() {
  copyAndHint(WEB_ANALYZE_URL, "动作分析");
}

function copyPoseLink() {
  copyAndHint(
    WEB_POSE_URL,
    "实时关键点检测",
    "实时关键点地址已复制。\n\n请用 Safari / 系统浏览器打开（比微信内嵌效果更好，才能正常开摄像头）：\n1. 打开聊天粘贴发送\n2. 点开链接\n或粘贴到 Safari 地址栏"
  );
}

module.exports = {
  copyAndHint: copyAndHint,
  copyStrokeLink: copyStrokeLink,
  copyAnalyzeLink: copyAnalyzeLink,
  copyPoseLink: copyPoseLink,
  WEB_STROKE_URL: WEB_STROKE_URL,
  WEB_ANALYZE_URL: WEB_ANALYZE_URL,
  WEB_POSE_URL: WEB_POSE_URL,
};
