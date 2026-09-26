const { WEB_POSE_URL } = require("../../utils/config");
const { copyPoseLink } = require("../../utils/web_link");

Page({
  data: {
    url: WEB_POSE_URL || "",
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
