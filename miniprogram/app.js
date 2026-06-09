const { isApiConfigValid, apiConfigHint, API_BASE_URL } = require("./utils/config");
const { pingHealth } = require("./utils/api");

App({
  onLaunch() {
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
        wx.showModal({
          title: "后端未连通",
          content:
            (err && err.message) +
            "\n\n请确认：\n1. WSL 已执行 GRADIO_SERVER_NAME=0.0.0.0 bash run-wsl.sh\n2. config.js 的 LOCAL_API_HOST 可访问\n3. 开发者工具已勾选「不校验合法域名」",
          showCancel: false,
        });
      });
  },
});
