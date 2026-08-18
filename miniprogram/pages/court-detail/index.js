var courtData = require("../../utils/court_data");
var courtApi = require("../../utils/court_api");

// 辅助函数：确保球场数据包含完整的 bookingOptions
function ensureBookingOptions(court) {
  if (!court) return court;
  
  // 如果已有 bookingOptions 且不为空，直接返回
  if (court.bookingOptions && court.bookingOptions.length > 0) {
    return court;
  }
  
  // 否则尝试从 Mock 数据中补充
  var mockCourt = courtData.fetchCourtById(court.id);
  if (mockCourt && mockCourt.bookingOptions && mockCourt.bookingOptions.length > 0) {
    court.bookingOptions = mockCourt.bookingOptions;
  }
  
  return court;
}

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
        
        // 确保 bookingOptions 完整
        court = ensureBookingOptions(court);
        
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
    console.log("[court-detail] _doBooking 点击, 渠道:", channel);
    
    if (!channel) {
      console.warn("[court-detail] channel 为空");
      return;
    }

    if (channel.type === "phone") {
      console.log("[court-detail] 电话预约");
      var phone = channel.phone || (this.data.court && this.data.court.phone);
      if (!phone) {
        console.warn("[court-detail] 缺少电话号码");
        wx.showToast({ title: "暂无电话", icon: "none" });
        return;
      }
      wx.showModal({
        title: "电话预约",
        content: "拨打 " + phone + " 预约场地？",
        confirmText: "拨打",
        success: function (res) {
          if (res.confirm) {
            console.log("[court-detail] 拨打电话:", phone);
            wx.makePhoneCall({ phoneNumber: phone });
          }
        },
      });
      return;
    }

    if (channel.type === "miniprogram") {
      console.log("[court-detail] 小程序预约, 原始配置:", JSON.stringify(channel));
      
      // 紧急补丁：直接补充已知小程序的配置
      if (channel.name === "勾勾运动" && !channel.appId) {
        console.log("[court-detail] 应用勾勾运动补丁");
        channel.appId = "wxa43e880705719304";
        channel.shortLink = "#小程序://勾勾运动/Mn9BgYZb0npey2g";
        channel.path = "/pages/index/index";
      }
      if (channel.name === "大众点评" && !channel.appId) {
        console.log("[court-detail] 应用大众点评补丁");
        channel.appId = "wx734c1ad7b3562129";
      }
      
      // 如果缺失 appId 或 shortLink，尝试从 Mock 数据补充
      if ((!channel.appId && !channel.shortLink) && this.data.court) {
        console.log("[court-detail] 尝试从 Mock 数据补充");
        var mockCourt = require("../../utils/court_data").fetchCourtById(this.data.court.id);
        if (mockCourt && mockCourt.bookingOptions) {
          var mockChannel = mockCourt.bookingOptions.find(function (opt) {
            return opt.name === channel.name;
          });
          if (mockChannel) {
            console.log("[court-detail] 找到 Mock 配置:", mockChannel);
            channel = mockChannel;
          }
        }
      }
      
      console.log("[court-detail] 最终跳转配置:", JSON.stringify(channel));
      
      // 优先尝试使用 AppID（更稳定，不受基础库版本限制）
      if (channel.appId) {
        console.log("使用 AppID 方式跳转:", channel.appId);
        wx.navigateToMiniProgram({
          appId: channel.appId,
          path: channel.path || "",
          envVersion: "release",
          success: function () {
            console.log("AppID 跳转成功");
          },
          fail: function (err) {
            console.log("AppID 跳转失败:", err);
            // AppID 失败时，如果有 shortLink 则尝试 shortLink
            if (channel.shortLink) {
              console.log("降级使用 shortLink 方式:", channel.shortLink);
              wx.navigateToMiniProgram({
                shortLink: channel.shortLink,
                envVersion: "release",
                fail: function (err2) {
                  console.log("shortLink 也失败:", err2);
                  wx.showToast({ title: "打开失败，请检查是否安装了「" + channel.name + "」小程序", icon: "none" });
                },
              });
            } else {
              wx.showToast({ title: "打开失败，请检查是否安装了「" + channel.name + "」小程序", icon: "none" });
            }
          },
        });
        return;
      }
      
      // 没有 AppID，尝试 shortLink
      if (channel.shortLink) {
        console.log("使用 shortLink 方式跳转:", channel.shortLink);
        wx.navigateToMiniProgram({
          shortLink: channel.shortLink,
          envVersion: "release",
          fail: function (err) {
            console.log("shortLink 跳转失败:", err);
            wx.showToast({ title: "打开失败，请确保已安装「" + channel.name + "」小程序", icon: "none" });
          },
        });
        return;
      }
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
    console.log("[court-detail] onExtSource 点击");
    var index = e.currentTarget.dataset.index;
    var court = this.data.court;
    console.log("[court-detail] 球场:", court && court.name, "extSources:", court && court.extSources);
    
    if (!court || !court.extSources || !court.extSources[index]) {
      console.warn("[court-detail] 缺少 extSources 数据");
      return;
    }
    
    var source = court.extSources[index];
    console.log("[court-detail] 选中的源:", source);
    
    var jump = courtData.getExtSourceJump(source);
    console.log("[court-detail] 获取的跳转配置:", jump);
    
    if (!jump) {
      console.warn("[court-detail] 无法获取跳转配置");
      wx.showToast({ title: "暂无法跳转", icon: "none" });
      return;
    }
    
    // 网页链接处理（如小红书）
    if (jump.type === "webpage" && jump.url) {
      console.log("[court-detail] 打开网页链接:", jump.url);
      // 微信小程序中，复制链接到剪贴板，提示用户在浏览器打开
      wx.setClipboardData({
        data: jump.url,
        success: function () {
          console.log("[court-detail] 链接已复制到剪贴板");
          wx.showToast({ 
            title: "链接已复制，请在浏览器打开", 
            icon: "success",
            duration: 2000
          });
        },
        fail: function (err) {
          console.error("[court-detail] 复制链接失败:", err);
          wx.showToast({ title: "无法打开，请手动搜索", icon: "none" });
        },
      });
      return;
    }
    
    // 使用 shortLink（微信内部链接）打开，不需要 AppID
    if (jump.shortLink) {
      console.log("[court-detail] 尝试用 shortLink 打开小程序:", jump.shortLink);
      wx.navigateToMiniProgram({
        shortLink: jump.shortLink,
        envVersion: "release",
        success: function () {
          console.log("[court-detail] shortLink 跳转成功");
        },
        fail: function (err) {
          console.warn("[court-detail] shortLink 跳转失败，尝试 AppID 方式:", err);
          // shortLink 失败时，如果有 AppID 则尝试 AppID 方式
          if (jump.appId && jump.path != null) {
            console.log("[court-detail] 使用 AppID 方式:", jump.appId, jump.path);
            wx.navigateToMiniProgram({
              appId: jump.appId,
              path: jump.path,
              envVersion: "release",
              success: function () {
                console.log("[court-detail] AppID 跳转成功");
              },
              fail: function (err2) {
                console.error("[court-detail] AppID 跳转也失败:", err2);
                wx.showToast({ title: "打开失败，请检查是否安装了「" + source.name + "」小程序", icon: "none" });
              },
            });
          } else {
            console.error("[court-detail] 没有 AppID 备选");
            wx.showToast({ title: "打开失败，请检查是否安装了「" + source.name + "」小程序", icon: "none" });
          }
        },
      });
      return;
    }
    
    // 没有 shortLink 但有 AppID，直接用 AppID
    if (jump.appId && jump.path != null) {
      console.log("[court-detail] 直接用 AppID 打开小程序:", jump.appId, jump.path);
      wx.navigateToMiniProgram({
        appId: jump.appId,
        path: jump.path,
        envVersion: "release",
        success: function () {
          console.log("[court-detail] AppID 跳转成功");
        },
        fail: function (err) {
          console.error("[court-detail] AppID 跳转失败:", err);
          wx.showToast({ title: "打开失败，请检查是否安装该小程序", icon: "none" });
        },
      });
    }
  },
});
