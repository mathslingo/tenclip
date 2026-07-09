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
    console.log("[TenniTi] API_BASE_URL =", API_BASE_URL, "LOCAL_DEV =", LOCAL_DEV);
    pingHealth()
      .then(function () {
        console.log("[TenniTi] 后端连通正常");
        if (LOCAL_DEV) {
          wx.showToast({
            title: "本地调试 · API 已连通",
            icon: "none",
            duration: 2500,
          });
        }
      })
      .catch(function (err) {
        var msg = (err && err.message) || "无法连接后端";
        console.warn("[TenniTi] 后端探活失败:", msg);
        if (LOCAL_DEV) {
          wx.showModal({
            title: "本地 API 未连通",
            content:
              "当前地址：" +
              API_BASE_URL +
              "\n\n请确认：\n1. WSL 已执行 GRADIO_SERVER_NAME=0.0.0.0 bash run-wsl.sh\n2. config.js 的 LOCAL_API_HOST 正确（模拟器不通可改 WSL IP:7861）\n3. 开发者工具已勾选「不校验合法域名」",
            showCancel: false,
          });
          return;
        }
        if (isDomainListError(err)) {
          wx.showModal({
            title: "网络配置异常",
            content: domainWhitelistHint(),
            showCancel: false,
          });
          return;
        }
        // 正式版不在启动时打扰用户；上传失败时页面会提示
      });
  },
});
