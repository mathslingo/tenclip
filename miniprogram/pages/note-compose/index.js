const { publishNote, upsertMe } = require("../../utils/social_api");
const { requirePrivacyIfNeeded } = require("../../utils/api");

Page({
  data: {
    title: "",
    body: "",
    images: [],
    busy: false,
  },

  onTitle(e) {
    this.setData({ title: (e.detail && e.detail.value) || "" });
  },

  onBody(e) {
    this.setData({ body: (e.detail && e.detail.value) || "" });
  },

  onAddImages() {
    var that = this;
    var remain = 9 - (this.data.images || []).length;
    if (remain <= 0) return;

    requirePrivacyIfNeeded()
      .then(function () {
        return new Promise(function (resolve, reject) {
          wx.chooseMedia({
            count: remain,
            mediaType: ["image"],
            sourceType: ["album", "camera"],
            success: resolve,
            fail: reject,
          });
        });
      })
      .then(function (res) {
        var files = (res.tempFiles || []).map(function (f) {
          return f.tempFilePath;
        });
        that.setData({ images: that.data.images.concat(files).slice(0, 9) });
      })
      .catch(function () {});
  },

  onRemoveImage(e) {
    var index = Number(e.currentTarget.dataset.index);
    var images = (this.data.images || []).slice();
    if (index < 0 || index >= images.length) return;
    images.splice(index, 1);
    this.setData({ images: images });
  },

  onPreview(e) {
    var index = Number(e.currentTarget.dataset.index);
    wx.previewImage({
      current: this.data.images[index],
      urls: this.data.images,
    });
  },

  onPublish() {
    var that = this;
    if (this.data.busy) return;
    var body = String(this.data.body || "").trim();
    var images = this.data.images || [];
    if (!body && !images.length) {
      wx.showToast({ title: "请填写正文或添加图片", icon: "none" });
      return;
    }

    this.setData({ busy: true });
    upsertMe()
      .catch(function () {})
      .then(function () {
        return publishNote({
          title: that.data.title,
          body: body,
          imagePaths: images,
        });
      })
      .then(function () {
        try {
          wx.setStorageSync("tenclip_me_open_works", "1");
        } catch (e) {}
        wx.showToast({ title: "已发布", icon: "success" });
        setTimeout(function () {
          wx.switchTab({ url: "/pages/me/index" });
        }, 400);
      })
      .catch(function (err) {
        wx.showToast({
          title: (err && err.message) || "发布失败",
          icon: "none",
        });
        that.setData({ busy: false });
      });
  },
});
