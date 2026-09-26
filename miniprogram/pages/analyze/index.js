const { WEB_POSE_URL } = require("../../utils/config");
const { copyPoseLink } = require("../../utils/web_link");

function embedUrl() {
  var base = WEB_POSE_URL || "";
  if (!base) return "";
  return base + (base.indexOf("?") >= 0 ? "&" : "?") + "mp=1";
}

Page({
  data: {
    url: embedUrl(),
  },

  onShow() {
    var tabBar = this.getTabBar && this.getTabBar();
    if (tabBar && tabBar.updateSelected) tabBar.updateSelected();
  },

  onWebError() {
    wx.showModal({
      title: "内嵌页打开失败",
      content: "可能未配置业务域名，或本地未勾选「不校验 web-view」。可以复制链接到浏览器打开。",
      confirmText: "复制链接",
      success: function (res) {
        if (res.confirm) copyPoseLink();
      },
    });
  },
});
