const { WEB_STROKE_URL, LOCAL_DEV, LOCAL_API_HOST } = require("../../utils/config");

Page({
  data: {
    url: "",
    loadError: false,
  },

  onLoad() {
    const url = LOCAL_DEV
      ? String(LOCAL_API_HOST).replace(/\/$/, "") + "/web/stroke"
      : WEB_STROKE_URL;
    this.setData({ url });
  },

  onWebError() {
    this.setData({ loadError: true });
    wx.showModal({
      title: "内嵌网页不可用",
      content:
        "未配置业务域名或账号不支持 web-view。\n请返回「网页版」Tab，使用「复制链接到聊天打开」。",
      showCancel: false,
    });
  },
});
