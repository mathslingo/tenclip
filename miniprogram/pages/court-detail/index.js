var courtData = require("../../utils/court_data");
var courtApi = require("../../utils/court_api");

Page({
  data: {
    court: null,
    coverIndex: 0,
    loading: true,
    errorText: "",
  },

  onLoad: function (query) {
    var id = (query && query.id) || "";
    if (!id) {
      this.setData({ loading: false, errorText: "缺少球场 ID" });
      return;
    }

    var that = this;

    // 1) 先用列表带来的预览秒开
    var preview = courtApi.readPreview(id) || courtData.fetchCourtById(id);
    if (preview) {
      var ready = courtData.normalizeCourt(preview);
      // 列表轻量数据可能无图：先空图，避免详情卡在坏图
      ready.photos = (ready.photos || []).slice(0, 2);
      wx.setNavigationBarTitle({
        title: ready.name.length > 12 ? ready.name.slice(0, 12) : ready.name,
      });
      that.setData({ court: ready, loading: false });
    }

    // 2) 再拉完整详情（失败则保留预览）
    courtApi
      .fetchCourtDetail(id)
      .then(function (court) {
        if (!court) {
          if (!that.data.court) {
            that.setData({ loading: false, errorText: "球场不存在或已下线" });
          }
          return;
        }
        court.photos = (court.photos || []).slice(0, 2);
        wx.setNavigationBarTitle({
          title: court.name.length > 12 ? court.name.slice(0, 12) : court.name,
        });
        that.setData({ court: court, loading: false, errorText: "" });
      })
      .catch(function () {
        if (!that.data.court) {
          that.setData({ loading: false, errorText: "加载超时，请返回重试" });
        }
      });
  },

  onSwiperChange: function (e) {
    this.setData({ coverIndex: e.detail.current });
  },

  onPreviewImage: function (e) {
    var url = e.currentTarget.dataset.url;
    var urls = this.data.court ? this.data.court.photos : [url];
    urls = (urls || []).filter(Boolean);
    if (!urls.length) return;
    wx.previewImage({ current: url || urls[0], urls: urls });
  },

  onPhotoError: function (e) {
    var idx = Number(e.currentTarget.dataset.index);
    var court = this.data.court;
    if (!court || !court.photos || isNaN(idx)) return;
    var photos = court.photos.slice();
    photos.splice(idx, 1);
    this.setData({
      "court.photos": photos,
      coverIndex: Math.min(this.data.coverIndex, Math.max(0, photos.length - 1)),
    });
  },

  onMainBook: function () {
    var court = this.data.court;
    if (!court || !court.bookingOptions || !court.bookingOptions.length) return;
    this._doBooking(court.bookingOptions[0]);
  },

  onChannelBook: function (e) {
    var index = e.currentTarget.dataset.index;
    var court = this.data.court;
    if (!court || !court.bookingOptions || !court.bookingOptions[index]) return;
    this._doBooking(court.bookingOptions[index]);
  },

  _doBooking: function (channel) {
    if (!channel) return;

    if (channel.type === "phone") {
      var phone = channel.phone || (this.data.court && this.data.court.phone);
      if (!phone) {
        wx.showToast({ title: "暂无电话", icon: "none" });
        return;
      }
      wx.showModal({
        title: "电话预约",
        content: "拨打 " + phone + " 预约场地？",
        confirmText: "拨打",
        success: function (res) {
          if (res.confirm) wx.makePhoneCall({ phoneNumber: phone });
        },
      });
      return;
    }

    if (channel.type === "miniprogram" && channel.appId) {
      wx.navigateToMiniProgram({
        appId: channel.appId,
        path: channel.path || "",
        envVersion: "release",
        fail: function () {
          wx.showToast({ title: "请先在后台配置跳转白名单", icon: "none" });
        },
      });
      return;
    }

    wx.showToast({
      title: channel.name ? "请打开「" + channel.name + "」预约" : "暂无跳转",
      icon: "none",
    });
  },

  onCall: function () {
    var phone = this.data.court && this.data.court.phone;
    if (!phone) {
      wx.showToast({ title: "暂无电话", icon: "none" });
      return;
    }
    wx.makePhoneCall({ phoneNumber: phone });
  },

  onNavigate: function () {
    var court = this.data.court;
    if (!court) return;
    wx.openLocation({
      latitude: court.lat,
      longitude: court.lng,
      name: court.name,
      address: court.address,
      scale: 16,
    });
  },

  onOpenLocation: function () {
    this.onNavigate();
  },

  onExtSource: function (e) {
    var index = e.currentTarget.dataset.index;
    var court = this.data.court;
    if (!court || !court.extSources || !court.extSources[index]) return;
    var source = court.extSources[index];
    var jump = courtData.getExtSourceJump(source);
    if (!jump || !jump.appId) {
      wx.showToast({ title: "暂无法跳转", icon: "none" });
      return;
    }
    wx.navigateToMiniProgram({
      appId: jump.appId,
      path: jump.path || "",
      envVersion: "release",
      fail: function () {
        wx.showToast({ title: "请先配置跳转白名单", icon: "none" });
      },
    });
  },
});
