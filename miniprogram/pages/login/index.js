const {
  loginWithWechat,
  registerGuest,
  loginGuest,
  checkNickname,
  isLoggedIn,
  clearSession,
  fetchMe,
  enterGuest,
} = require("../../utils/auth_api");

Page({
  data: {
    loading: false,
    from: "",
    mode: "wechat", // wechat | guest_register | guest_login
    guestNick: "",
    guestPwd: "",
    guestPwd2: "",
    nickHint: "",
    nickOk: false,
  },

  onLoad(query) {
    this.setData({ from: (query && query.from) || "" });
    if (isLoggedIn()) {
      var that = this;
      fetchMe()
        .then(function (user) {
          that._afterLogin({ user: user, is_new: !(user && user.profile_completed) });
        })
        .catch(function () {
          clearSession();
        });
    }
  },

  onUnload() {},

  onSwitchMode(e) {
    var mode = (e.currentTarget && e.currentTarget.dataset.mode) || "wechat";
    this.setData({
      mode: mode,
      nickHint: "",
      nickOk: false,
    });
  },

  onInputGuestNick(e) {
    this.setData({
      guestNick: (e.detail && e.detail.value) || "",
      nickHint: "",
      nickOk: false,
    });
  },

  onBlurGuestNick() {
    var that = this;
    var nick = String(this.data.guestNick || "").trim();
    if (!nick || this.data.mode !== "guest_register") return;
    if (nick.length < 2) {
      this.setData({ nickHint: "昵称至少 2 个字符", nickOk: false });
      return;
    }
    checkNickname(nick)
      .then(function (res) {
        if (res && res.available) {
          that.setData({ nickHint: "昵称可用", nickOk: true });
        } else {
          that.setData({
            nickHint: (res && res.reason) || "昵称已被占用",
            nickOk: false,
          });
        }
      })
      .catch(function () {
        that.setData({ nickHint: "", nickOk: false });
      });
  },

  onInputGuestPwd(e) {
    this.setData({ guestPwd: (e.detail && e.detail.value) || "" });
  },

  onInputGuestPwd2(e) {
    this.setData({ guestPwd2: (e.detail && e.detail.value) || "" });
  },

  onWechatLogin() {
    if (this.data.loading) return;
    var that = this;
    this.setData({ loading: true });
    loginWithWechat()
      .then(function (body) {
        that.setData({ loading: false });
        that._afterLogin(body);
      })
      .catch(function (err) {
        that.setData({ loading: false });
        wx.showToast({
          title: (err && err.message) || "登录失败",
          icon: "none",
          duration: 2500,
        });
      });
  },

  onGuestRegister() {
    if (this.data.loading) return;
    var nick = String(this.data.guestNick || "").trim();
    var pwd = String(this.data.guestPwd || "").trim();
    var pwd2 = String(this.data.guestPwd2 || "").trim();
    if (nick.length < 2) {
      wx.showToast({ title: "请填写昵称（至少2字）", icon: "none" });
      return;
    }
    if (!/^\d{6}$/.test(pwd)) {
      wx.showToast({ title: "密码须为6位数字", icon: "none" });
      return;
    }
    if (pwd !== pwd2) {
      wx.showToast({ title: "两次密码不一致", icon: "none" });
      return;
    }
    var that = this;
    this.setData({ loading: true });
    registerGuest(nick, pwd)
      .then(function (body) {
        that.setData({ loading: false });
        that._afterLogin(body);
      })
      .catch(function (err) {
        that.setData({ loading: false });
        wx.showToast({
          title: (err && err.message) || "注册失败",
          icon: "none",
          duration: 2500,
        });
      });
  },

  onGuestLogin() {
    if (this.data.loading) return;
    var nick = String(this.data.guestNick || "").trim();
    var pwd = String(this.data.guestPwd || "").trim();
    if (!nick) {
      wx.showToast({ title: "请填写昵称", icon: "none" });
      return;
    }
    if (!/^\d{6}$/.test(pwd)) {
      wx.showToast({ title: "密码须为6位数字", icon: "none" });
      return;
    }
    var that = this;
    this.setData({ loading: true });
    loginGuest(nick, pwd)
      .then(function (body) {
        that.setData({ loading: false });
        that._afterLogin(body);
      })
      .catch(function (err) {
        that.setData({ loading: false });
        wx.showToast({
          title: (err && err.message) || "登录失败",
          icon: "none",
          duration: 2500,
        });
      });
  },

  /** 匿名浏览：无 user_id，不可写操作 */
  onGuestEnter() {
    enterGuest();
    this._leaveToBrowse();
  },

  onBack() {
    this._leaveToBrowse();
  },

  _leaveToBrowse() {
    var pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack({
        fail: function () {
          wx.switchTab({ url: "/pages/feed/index" });
        },
      });
      return;
    }
    wx.switchTab({ url: "/pages/feed/index" });
  },

  _afterLogin(body) {
    var user = (body && body.user) || {};
    var needProfile = !!(body && body.is_new) || !user.profile_completed;
    // 游客注册已设昵称，仍引导完善网球风格
    if (needProfile || (user.account_type === "guest" && body && body.is_new)) {
      wx.redirectTo({
        url: "/pages/profile-edit/index?from=register",
      });
      return;
    }
    var pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack({
        fail: function () {
          wx.switchTab({ url: "/pages/feed/index" });
        },
      });
      return;
    }
    wx.switchTab({ url: "/pages/feed/index" });
  },
});
