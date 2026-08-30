var courtData = require("../../utils/court_data");
var courtApi = require("../../utils/court_api");

function safeJson(obj) {
  try {
    return JSON.stringify(obj);
  } catch (e) {
    return String(obj);
  }
}

// 辅助函数：确保球场数据包含完整的 bookingOptions
function ensureBookingOptions(court) {
  if (!court) return court;

  if (court.bookingOptions && court.bookingOptions.length > 0) {
    return court;
  }

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
    /** 主预约按钮：供 open-type="navigateToMiniProgram" 使用 */
    mainJump: null,
  },

  onLoad: function (query) {
    var id = (query && query.id) || "";
    if (!id) {
      this.setData({ loading: false, errorText: "缺少球场 ID" });
      return;
    }

    var that = this;

    var preview = courtApi.readPreview(id) || courtData.fetchCourtById(id);
    if (preview) {
      var ready = courtData.normalizeCourt(preview);
      ready.photos = (ready.photos || []).slice(0, 2);
      wx.setNavigationBarTitle({
        title: ready.name.length > 12 ? ready.name.slice(0, 12) : ready.name,
      });
      that.setData({
        court: ready,
        loading: false,
        mainJump: that._buildJump(ready.bookingOptions && ready.bookingOptions[0]),
      });
    }

    courtApi
      .fetchCourtDetail(id)
      .then(function (court) {
        if (!court) {
          if (!that.data.court) {
            that.setData({ loading: false, errorText: "球场不存在或已下线" });
          }
          return;
        }

        court = ensureBookingOptions(court);
        console.log("[book-jump] 详情加载 bookingOptions=", safeJson(court.bookingOptions));

        court.photos = (court.photos || []).slice(0, 2);
        wx.setNavigationBarTitle({
          title: court.name.length > 12 ? court.name.slice(0, 12) : court.name,
        });
        that.setData({
          court: court,
          loading: false,
          errorText: "",
          mainJump: that._buildJump(court.bookingOptions && court.bookingOptions[0]),
        });
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
    console.log("[book-jump] onMainBook", {
      courtId: court && court.id,
      courtName: court && court.name,
      bookingOptions: court && court.bookingOptions,
      mainJump: this.data.mainJump,
    });
    if (!court || !court.bookingOptions || !court.bookingOptions.length) {
      console.warn("[book-jump] 无 bookingOptions，中止");
      return;
    }
    // 小程序渠道优先走 button open-type；此处兜底电话 / 无 open-type 场景
    this._doBooking(court.bookingOptions[0], "main");
  },

  onChannelBook: function (e) {
    var index = e.currentTarget.dataset.index;
    var court = this.data.court;
    console.log("[book-jump] onChannelBook", {
      index: index,
      option: court && court.bookingOptions && court.bookingOptions[index],
    });
    if (!court || !court.bookingOptions || !court.bookingOptions[index]) {
      console.warn("[book-jump] 渠道 index 无效", index);
      return;
    }
    this._doBooking(court.bookingOptions[index], "channel:" + index);
  },

  onMpJumpSuccess: function (e) {
    console.log("[book-jump] open-type success", e && e.detail);
  },

  onMpJumpFail: function (e) {
    var detail = (e && e.detail) || {};
    console.error("[book-jump] open-type fail", detail);
    this._explainJumpFail(detail.errMsg || "", this.data.mainJump && this.data.mainJump.appId);
  },

  /** 组装跳转参数（含按名称补全 appId） */
  _buildJump: function (raw) {
    if (!raw) return null;
    var channel = {
      name: raw.name || "",
      type: raw.type || "",
      phone: raw.phone || "",
      appId: String(
        raw.appId != null ? raw.appId : raw.appid != null ? raw.appid : ""
      ).trim(),
      // path 不能带前导 /，否则真机会跳失败
      path: String(raw.path || "").replace(/^\/+/, ""),
      shortLink: raw.shortLink || "",
    };
    if (channel.type === "miniprogram" && !channel.appId) {
      channel.appId = this._resolveBookingAppId(channel.name);
    }
    if (channel.name.indexOf("勾勾运动") >= 0 && !channel.shortLink) {
      channel.shortLink = "#小程序://勾勾运动/Mn9BgYZb0npey2g";
      if (!channel.path) channel.path = "pages/index/index";
    }
    console.log("[book-jump] _buildJump", safeJson(channel));
    return channel;
  },

  _getPlatform: function () {
    try {
      if (wx.getDeviceInfo) {
        var d = wx.getDeviceInfo() || {};
        if (d.platform) return d.platform;
      }
    } catch (e) {}
    try {
      return (wx.getSystemInfoSync() || {}).platform || "";
    } catch (e) {
      return "";
    }
  },

  _isDevtools: function () {
    return this._getPlatform() === "devtools";
  },

  _explainJumpFail: function (msg, appId) {
    msg = String(msg || "");
    if (this._isDevtools()) {
      wx.showModal({
        title: "模拟器无法跳转",
        content:
          "开发者工具不会真实打开其他小程序，常误报 appid missing。\n\n请用「预览」扫码真机再试。\n目标 AppID：" +
          (appId || "(空)"),
        showCancel: false,
      });
      return;
    }
    if (msg.indexOf("cancel") >= 0) {
      wx.showToast({ title: "已取消跳转", icon: "none" });
      return;
    }
    wx.showModal({
      title: "打开失败",
      content:
        (msg || "未知错误") + "\n\n目标 AppID：" + (appId || "(空)"),
      showCancel: false,
    });
  },

  _resolveBookingAppId: function (name) {
    var n = String(name || "");
    var map = [
      { key: "韵动吧", appId: "wxd0286fb3b0e39384" },
      { key: "勾勾运动", appId: "wxa43e880705719304" },
      { key: "大众点评", appId: "wx734c1ad7b3562129" },
    ];
    for (var i = 0; i < map.length; i++) {
      if (n.indexOf(map[i].key) >= 0) {
        console.log(
          "[book-jump] resolveAppId 命中",
          map[i].key,
          "→",
          map[i].appId,
          "name=",
          n
        );
        return map[i].appId;
      }
    }
    console.warn("[book-jump] resolveAppId 未命中 name=", n);
    return "";
  },

  _doBooking: function (raw, from) {
    var sys = {};
    try {
      var dev = wx.getDeviceInfo ? wx.getDeviceInfo() || {} : {};
      var base = wx.getAppBaseInfo ? wx.getAppBaseInfo() || {} : {};
      sys = {
        platform: dev.platform,
        brand: dev.brand,
        model: dev.model,
        SDKVersion: base.SDKVersion,
      };
    } catch (e) {}

    console.log("[book-jump] —— 开始 ——", {
      from: from || "",
      SDKVersion: sys.SDKVersion,
      platform: sys.platform,
      brand: sys.brand,
      model: sys.model,
      hasAPI: typeof wx.navigateToMiniProgram,
      rawType: typeof raw,
      rawKeys: raw ? Object.keys(raw) : [],
      rawJSON: safeJson(raw),
    });

    if (!raw) {
      console.warn("[book-jump] channel 为空，中止");
      return;
    }

    var channel = {
      name: raw.name || "",
      type: raw.type || "",
      phone: raw.phone || "",
      appId: String(raw.appId != null ? raw.appId : raw.appid != null ? raw.appid : "").trim(),
      path: String(raw.path || "").replace(/^\/+/, ""),
      shortLink: raw.shortLink || "",
    };

    console.log("[book-jump] 拷贝后", {
      name: channel.name,
      type: channel.type,
      appId: channel.appId,
      appIdLen: channel.appId.length,
      path: channel.path,
      shortLink: channel.shortLink,
      rawAppId: raw.appId,
      rawAppid: raw.appid,
      typeofRawAppId: typeof raw.appId,
    });

    if (channel.type === "phone") {
      console.log("[book-jump] 分支=phone");
      var phone = channel.phone || (this.data.court && this.data.court.phone);
      if (!phone) {
        console.warn("[book-jump] 缺少电话");
        wx.showToast({ title: "暂无电话", icon: "none" });
        return;
      }
      wx.showModal({
        title: "电话预约",
        content: "拨打 " + phone + " 预约场地？",
        confirmText: "拨打",
        success: function (res) {
          if (res.confirm) {
            console.log("[book-jump] 拨打", phone);
            wx.makePhoneCall({ phoneNumber: phone });
          }
        },
      });
      return;
    }

    if (channel.type === "miniprogram") {
      console.log("[book-jump] 分支=miniprogram");

      if (!channel.appId) {
        console.log("[book-jump] appId 空 → 按名称解析");
        channel.appId = this._resolveBookingAppId(channel.name);
        console.log("[book-jump] 解析结果 appId=", JSON.stringify(channel.appId));
      } else {
        console.log("[book-jump] 渠道自带 appId=", JSON.stringify(channel.appId));
      }

      if (channel.name.indexOf("勾勾运动") >= 0 && !channel.shortLink) {
        channel.shortLink = "#小程序://勾勾运动/Mn9BgYZb0npey2g";
        if (!channel.path) channel.path = "pages/index/index";
        console.log("[book-jump] 勾勾补丁 shortLink/path", channel.shortLink, channel.path);
      }

      if (!channel.appId && !channel.shortLink && this.data.court) {
        console.log("[book-jump] 仍缺 → Mock 补充 id=", this.data.court.id);
        var mockCourt = courtData.fetchCourtById(this.data.court.id);
        if (mockCourt && mockCourt.bookingOptions) {
          var mockChannel = mockCourt.bookingOptions.find(function (opt) {
            return (
              opt.name === channel.name ||
              (opt.name && channel.name && channel.name.indexOf(opt.name) >= 0)
            );
          });
          console.log("[book-jump] Mock 命中", safeJson(mockChannel));
          if (mockChannel) {
            channel.appId = String(mockChannel.appId || "").trim() || channel.appId;
            channel.path = mockChannel.path || channel.path;
            channel.shortLink = mockChannel.shortLink || channel.shortLink;
          }
        } else {
          console.warn("[book-jump] Mock 无 bookingOptions");
        }
      }

      console.log("[book-jump] 最终 channel=", safeJson(channel));
      console.log("[book-jump] appId 形态", {
        value: channel.appId,
        length: (channel.appId || "").length,
        looksLikeWx: /^wx[0-9a-fA-F]{16}$/.test(channel.appId || ""),
      });

      // 有 shortLink 优先：不依赖目标 AppID 是否准确，实测最稳（勾勾运动之前就是这样跳通的）
      if (channel.shortLink) {
        if (this._isDevtools()) {
          this._explainJumpFail("devtools", channel.appId);
          return;
        }
        var shortLink = channel.shortLink;
        var backupAppId = channel.appId;
        var thatSl = this;
        console.log("[book-jump] >>> 优先 shortLink=", shortLink);
        wx.navigateToMiniProgram({
          shortLink: shortLink,
          envVersion: "release",
          success: function (res) {
            console.log("[book-jump] <<< shortLink success", safeJson(res));
          },
          fail: function (err) {
            console.error("[book-jump] <<< shortLink fail", safeJson(err));
            if (backupAppId) {
              console.log("[book-jump] shortLink 失败，降级 appId=", backupAppId);
              wx.navigateToMiniProgram({
                appId: backupAppId,
                envVersion: "release",
                fail: function (err2) {
                  console.error("[book-jump] <<< appId 兜底 fail", safeJson(err2));
                  thatSl._explainJumpFail((err2 && err2.errMsg) || "", backupAppId);
                },
              });
            } else {
              thatSl._explainJumpFail((err && err.errMsg) || "", "");
            }
          },
        });
        return;
      }

      if (channel.appId) {
        var navAppId = channel.appId;
        var navPath = channel.path || "";
        var navEnv = "release";

        if (this._isDevtools()) {
          console.warn(
            "[book-jump] 当前为开发者工具模拟器，跳转其他小程序会失败/误报 appid missing，请用真机预览"
          );
          this._explainJumpFail("devtools", navAppId);
          return;
        }

        console.log("[book-jump] >>> 调用前字面量检查", {
          navAppId: navAppId,
          navAppIdJSON: JSON.stringify(navAppId),
          navAppIdLen: navAppId.length,
          navPath: navPath,
          navEnv: navEnv,
          willOmitPath: !navPath,
        });

        var that = this;
        var callArgs = {
          appId: navAppId,
          envVersion: navEnv,
          success: function (res) {
            console.log("[book-jump] <<< success", safeJson(res));
          },
          fail: function (err) {
            console.error("[book-jump] <<< fail err=", err);
            console.error("[book-jump] <<< fail errMsg=", err && err.errMsg);
            console.error("[book-jump] <<< fail JSON=", safeJson(err));
            console.error("[book-jump] <<< 失败时 navAppId 仍是", JSON.stringify(navAppId));
            var msg = (err && err.errMsg) || "";
            if (channel.shortLink) {
              console.log("[book-jump] 降级 shortLink=", channel.shortLink);
              wx.navigateToMiniProgram({
                shortLink: channel.shortLink,
                envVersion: "release",
                success: function (r2) {
                  console.log("[book-jump] shortLink success", r2);
                },
                fail: function (err2) {
                  console.error("[book-jump] shortLink fail", err2);
                  that._explainJumpFail(
                    (err2 && err2.errMsg) || msg,
                    navAppId
                  );
                },
              });
            } else {
              that._explainJumpFail(msg, navAppId);
            }
          },
          complete: function (res) {
            console.log("[book-jump] <<< complete", safeJson(res));
          },
        };
        if (navPath) {
          callArgs.path = navPath;
          console.log("[book-jump] 带 path=", navPath);
        } else {
          console.log("[book-jump] 不传 path 字段");
        }

        console.log("[book-jump] >>> wx.navigateToMiniProgram callArgs.keys=", Object.keys(callArgs));
        console.log("[book-jump] >>> callArgs.appId=", callArgs.appId);
        wx.navigateToMiniProgram(callArgs);
        return;
      }

      if (channel.shortLink) {
        console.log("[book-jump] 无 appId，仅 shortLink=", channel.shortLink);
        wx.navigateToMiniProgram({
          shortLink: channel.shortLink,
          envVersion: "release",
          success: function (r) {
            console.log("[book-jump] shortLink-only success", r);
          },
          fail: function (err) {
            console.error("[book-jump] shortLink-only fail", err);
            wx.showToast({
              title: "打开失败，请确保已安装「" + channel.name + "」",
              icon: "none",
            });
          },
        });
        return;
      }

      console.warn("[book-jump] miniprogram 但无 appId/shortLink", channel);
    } else {
      console.warn("[book-jump] 未知 type=", channel.type);
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
    console.log("[book-jump] onExtSource");
    var index = e.currentTarget.dataset.index;
    var court = this.data.court;

    if (!court || !court.extSources || !court.extSources[index]) {
      console.warn("[book-jump] 缺少 extSources");
      return;
    }

    var source = court.extSources[index];
    var jump = courtData.getExtSourceJump(source);
    console.log("[book-jump] ext jump=", safeJson(jump));

    if (!jump) {
      wx.showToast({ title: "暂无法跳转", icon: "none" });
      return;
    }

    if (jump.type === "webpage" && jump.url) {
      wx.setClipboardData({
        data: jump.url,
        success: function () {
          wx.showToast({
            title: "链接已复制，请在浏览器打开",
            icon: "success",
            duration: 2000,
          });
        },
      });
      return;
    }

    if (jump.shortLink) {
      console.log("[book-jump] ext shortLink=", jump.shortLink);
      wx.navigateToMiniProgram({
        shortLink: jump.shortLink,
        envVersion: "release",
        fail: function (err) {
          console.error("[book-jump] ext shortLink fail", err);
          if (jump.appId) {
            wx.navigateToMiniProgram({
              appId: jump.appId,
              path: jump.path || undefined,
              envVersion: "release",
              fail: function (err2) {
                console.error("[book-jump] ext appId fail", err2);
                wx.showToast({
                  title: "打开失败：" + ((err2 && err2.errMsg) || ""),
                  icon: "none",
                });
              },
            });
          } else {
            wx.showToast({ title: "打开失败", icon: "none" });
          }
        },
      });
      return;
    }

    if (jump.appId) {
      console.log("[book-jump] ext appId=", jump.appId, "path=", jump.path);
      wx.navigateToMiniProgram({
        appId: jump.appId,
        path: jump.path || undefined,
        envVersion: "release",
        fail: function (err) {
          console.error("[book-jump] ext 直接 appId fail", err);
          wx.showToast({
            title: "打开失败：" + ((err && err.errMsg) || ""),
            icon: "none",
          });
        },
      });
    }
  },
});
