const { API_BASE_URL } = require("../../utils/config");

Page({
  onOpenWeb() {
    var url = API_BASE_URL + "/legal/privacy";
    wx.setClipboardData({
      data: url,
      success: function () {
        wx.showModal({
          title: "链接已复制",
          content: "完整隐私政策地址已复制，可粘贴到浏览器打开：\n" + url,
          showCancel: false,
        });
      },
    });
  },
});
