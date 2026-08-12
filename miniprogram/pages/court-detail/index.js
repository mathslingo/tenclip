var courtData = require("../../utils/court_data");

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
    var court = courtData.fetchCourtById(id);

    if (!court) {
      that.setData({ loading: false, errorText: "球场不存在或已下线" });
      return;
    }

    wx.setNavigationBarTitle({
      title: court.name.length > 12 ? court.name.slice(0, 12) : court.name,
    });

    that.setData({ court: court, loading: false });
  },

  // ── 图片 ──

  onSwiperChange: function (e) {
    this.setData({ coverIndex: e.detail.current });
  },

  onPreviewImage: function (e) {
    var url = e.currentTarget.dataset.url;
    var urls = this.data.court ? this.data.court.photos : [url];
    wx.previewImage({ current: url || urls[0], urls: urls });
  },

  // ── 主预定按钮（第一个渠道） ──

  onMainBook: function () {
    var court = this.data.court;
    if (!court || !court.bookingOptions.length) return;
    this._doBooking(court.bookingOptions[0]);
  },

  // ── 更多渠道预定 ──

  onChannelBook: function (e) {
    var index = e.currentTarget.dataset.index;
    var court = this.data.court;
    if (!court || !court.bookingOptions[index]) return;
    this._doBooking(court.bookingOptions[index]);
  },

  // ── 执行预定 ──

  _doBooking: function (channel) {
    if (!channel) return;

    if (channel.type === "phone") {
      var phone = channel.phone || this.data.court.phone;
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

    if (channel.type === "miniprogram") {
      if (!channel.appId) {
        var phoneFallback = (this.data.court && this.data.court.phone) || "";
        if (phoneFallback) {
          wx.showModal({
            title: channel.name,
            content: "在线预约暂未开通，是否拨打 " + phoneFallback + " 电话预约？",
            confirmText: "拨打",
            success: function (res) {
              if (res.confirm) wx.makePhoneCall({ phoneNumber: phoneFallback });
            },
          });
        } else {
          wx.showModal({
            title: channel.name,
            content: "在线预约暂未开通，请使用页面上的电话或导航到店预约。",
            showCancel: false,
            confirmText: "知道了",
          });
        }
        return;
      }
      wx.navigateToMiniProgram({
        appId: channel.appId,
        path: channel.path || "",
        envVersion: "release",
        success: function () {
          console.log("[courts] 已跳转:", channel.name);
        },
        fail: function (err) {
          var msg = String(err.errMsg || "");
          if (msg.indexOf("cancel") !== -1 || msg.indexOf("not found") !== -1) {
            wx.showModal({
              title: "需要安装「" + channel.name + "」",
              content: "请先在微信中搜索并打开「" + channel.name + "」小程序。",
              showCancel: false,
              confirmText: "知道了",
            });
          } else {
            wx.showToast({ title: "跳转失败，请重试", icon: "none" });
          }
        },
      });
      return;
    }

    // web 类型：复制链接或打开网页
    if (channel.type === "web") {
      wx.showToast({ title: "请在「" + channel.name + "」中搜索预约", icon: "none" });
      return;
    }
  },

  // ── 外部评价源（大众点评 / 小红书） ──

  onExtSource: function (e) {
    var index = e.currentTarget.dataset.index;
    var court = this.data.court;
    if (!court || !court.extSources[index]) return;
    var source = court.extSources[index];

    var jump = courtData.getExtSourceJump(source);
    if (!jump || !jump.appId) {
      // 无 AppID 时提示在对应平台搜索
      wx.showModal({
        title: "在「" + source.name + "」中查看",
        content: "请打开「" + source.name + "」，搜索「" + (source.keyword || court.name) + "」查看评价。",
        showCancel: false,
        confirmText: "知道了",
      });
      return;
    }

    wx.navigateToMiniProgram({
      appId: jump.appId,
      path: jump.path || "",
      envVersion: "release",
      success: function () {
        console.log("[courts] 已跳转到:", source.name);
      },
      fail: function () {
        wx.showModal({
          title: "跳转失败",
          content: "请打开「" + source.name + "」搜索「" + (source.keyword || court.name) + "」查看评价。",
          showCancel: false,
          confirmText: "知道了",
        });
      },
    });
  },

  // ── 电话 ──

  onCall: function () {
    var phone = this.data.court && this.data.court.phone;
    if (!phone) {
      wx.showToast({ title: "暂无电话", icon: "none" });
      return;
    }
    wx.makePhoneCall({ phoneNumber: phone });
  },

  // ── 地图 ──

  onOpenLocation: function () {
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

  onNavigate: function () {
    this.onOpenLocation();
  },

  // ── 分享 ──

  onShareAppMessage: function () {
    var court = this.data.court;
    if (!court) return {};
    return {
      title: court.name + " - 来一起打球吧！",
      path: "/pages/court-detail/index?id=" + court.id,
    };
  },
});
