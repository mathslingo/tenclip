const {
  isApiConfigValid,
  apiConfigHint,
  API_BASE_URL,
  LOCAL_DEV,
  domainWhitelistHint,
  isDomainListError,
} = require("./utils/config");
const { pingHealth } = require("./utils/api");

App({
  onLaunch() {
    if (typeof wx.onNeedPrivacyAuthorization === "function") {
      wx.onNeedPrivacyAuthorization(function (resolve) {
        wx.showModal({
          title: "隐私提示",
          content:
            "选择网球视频需要访问相册或相机。请阅读并同意《用户隐私保护指引》后继续。",
          confirmText: "同意",
          cancelText: "拒绝",
          success: function (res) {
            if (res.confirm) {
              resolve({ buttonId: "agree", event: "agree" });
            } else {
              resolve({ event: "disagree" });
            }
          },
          fail: function () {
            resolve({ event: "disagree" });
          },
        });
      });
    }
    if (!isApiConfigValid()) {
      console.error("[TenniTi] API 未配置:", API_BASE_URL);
      wx.showModal({
        title: "API 地址未配置",
        content: apiConfigHint(),
        showCancel: false,
      });
      return;
    }
    console.log("[TenniTi] API_BASE_URL =", API_BASE_URL);
    pingHealth()
      .then(function () {
        console.log("[TenniTi] 后端连通正常");
      })
      .catch(function (err) {
        var msg = (err && err.message) || "无法连接后端";
        console.warn("[TenniTi] 后端探活失败:", msg);
        if (LOCAL_DEV) {
          return;
        }
        var extra = isDomainListError(err)
          ? domainWhitelistHint()
          : "请检查 PROD_API_BASE_URL 与服务器 HTTPS。";
        wx.showModal({
          title: "后端未连通",
          content: msg + "\n\n" + extra,
          showCancel: false,
        });
      });
  },
});
