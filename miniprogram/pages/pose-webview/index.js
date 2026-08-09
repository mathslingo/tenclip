const { WEB_POSE_URL } = require("../../utils/config");
const { copyPoseLink } = require("../../utils/web_link");

Page({
  data: {
    url: "",
  },

  onLoad(query) {
    var url = "";
    if (query && query.url) {
      try {
        url = decodeURIComponent(query.url);
      } catch (e) {
        url = query.url;
      }
    }
    if (!url) url = WEB_POSE_URL || "";
    this.setData({ url: url });
  },

  onWebLoad() {
    console.log("[pose-webview] loaded", this.data.url);
  },

  onWebError(e) {
    console.warn("[pose-webview] error", e);
    wx.showModal({
      title: "内嵌页打开失败",
      content:
        "可能未配置业务域名，或本地未勾选「不校验 web-view」。建议改用「复制链接」在微信中打开。",
      confirmText: "复制链接",
      success: (res) => {
        if (res.confirm) copyPoseLink();
      },
    });
  },

  onCopy() {
    copyPoseLink();
  },
});
