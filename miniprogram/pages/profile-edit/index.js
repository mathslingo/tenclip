const { getProfile, saveProfile } = require("../../utils/me_store");
const {
  upsertMe,
  uploadNoteImage,
  needsAvatarUpload,
  usableAvatarUrl,
} = require("../../utils/social_api");
const {
  isLoggedIn,
  updateAuthProfile,
  requireLogin,
  checkNickname,
  fetchMe,
} = require("../../utils/auth_api");

var HAND_OPTS = ["右手", "左手", "双手"];
var LEVEL_OPTS = ["入门", "进阶", "中级", "高级", "竞赛"];
var STYLE_OPTS = ["底线型", "发球上网", "全能型", "防守反击", "力量型"];
var SURFACE_OPTS = ["硬地", "红土", "草地", "室内"];

function indexOfOr(list, value) {
  var i = list.indexOf(value);
  return i >= 0 ? i : 0;
}

Page({
  data: {
    fromRegister: false,
    nickHint: "",
    handOpts: HAND_OPTS,
    levelOpts: LEVEL_OPTS,
    styleOpts: STYLE_OPTS,
    surfaceOpts: SURFACE_OPTS,
    form: {
      nickname: "",
      bio: "",
      tagsText: "",
      avatarUrl: "",
      tennisHand: "",
      tennisLevel: "",
      tennisStyle: "",
      preferredSurface: "",
      handIndex: 0,
      levelIndex: 0,
      styleIndex: 0,
      surfaceIndex: 0,
    },
  },

  onLoad(query) {
    if (!isLoggedIn()) {
      requireLogin("profile-edit");
      return;
    }
    var fromRegister = !!(query && query.from === "register");
    var that = this;
    this.setData({ fromRegister: fromRegister });
    if (fromRegister) {
      wx.setNavigationBarTitle({ title: "完善资料" });
    }

    fetchMe()
      .then(function (u) {
        that._applyForm(u);
      })
      .catch(function () {
        that._applyForm(null);
      });
  },

  _applyForm(serverUser) {
    var p = getProfile();
    var nick = (serverUser && serverUser.nickname) || p.nickname || "";
    var bio = serverUser && serverUser.bio != null ? serverUser.bio : p.bio || "";
    var tags = (serverUser && serverUser.tags) || p.tags || [];
    var avatar = usableAvatarUrl(
      (serverUser && serverUser.avatar_url) || p.avatarUrl || ""
    );
    var hand = (serverUser && serverUser.tennis_hand) || p.tennisHand || "";
    var level = (serverUser && serverUser.tennis_level) || p.tennisLevel || "";
    var style = (serverUser && serverUser.tennis_style) || p.tennisStyle || "";
    var surface =
      (serverUser && serverUser.preferred_surface) || p.preferredSurface || "";

    this.setData({
      form: {
        nickname: nick,
        bio: bio,
        tagsText: (tags || []).join(","),
        avatarUrl: avatar,
        tennisHand: hand || HAND_OPTS[0],
        tennisLevel: level || LEVEL_OPTS[0],
        tennisStyle: style || STYLE_OPTS[0],
        preferredSurface: surface || SURFACE_OPTS[0],
        handIndex: indexOfOr(HAND_OPTS, hand || HAND_OPTS[0]),
        levelIndex: indexOfOr(LEVEL_OPTS, level || LEVEL_OPTS[0]),
        styleIndex: indexOfOr(STYLE_OPTS, style || STYLE_OPTS[0]),
        surfaceIndex: indexOfOr(SURFACE_OPTS, surface || SURFACE_OPTS[0]),
      },
    });
  },

  onChooseAvatar(e) {
    var url = (e.detail && e.detail.avatarUrl) || "";
    if (url) this.setData({ "form.avatarUrl": url });
  },

  onInputNick(e) {
    this.setData({
      "form.nickname": (e.detail && e.detail.value) || "",
      nickHint: "",
    });
  },

  onBlurNick() {
    var that = this;
    var nick = String(this.data.form.nickname || "").trim();
    if (nick.length < 2) {
      this.setData({ nickHint: "昵称至少 2 个字符" });
      return;
    }
    checkNickname(nick)
      .then(function (res) {
        if (res && res.available) {
          that.setData({ nickHint: "昵称可用" });
        } else {
          that.setData({ nickHint: (res && res.reason) || "昵称已被占用" });
        }
      })
      .catch(function () {});
  },

  onInputBio(e) {
    this.setData({ "form.bio": (e.detail && e.detail.value) || "" });
  },

  onInputTags(e) {
    this.setData({ "form.tagsText": (e.detail && e.detail.value) || "" });
  },

  onPickHand(e) {
    var i = Number(e.detail.value) || 0;
    this.setData({
      "form.handIndex": i,
      "form.tennisHand": HAND_OPTS[i],
    });
  },

  onPickLevel(e) {
    var i = Number(e.detail.value) || 0;
    this.setData({
      "form.levelIndex": i,
      "form.tennisLevel": LEVEL_OPTS[i],
    });
  },

  onPickStyle(e) {
    var i = Number(e.detail.value) || 0;
    this.setData({
      "form.styleIndex": i,
      "form.tennisStyle": STYLE_OPTS[i],
    });
  },

  onPickSurface(e) {
    var i = Number(e.detail.value) || 0;
    this.setData({
      "form.surfaceIndex": i,
      "form.preferredSurface": SURFACE_OPTS[i],
    });
  },

  onSave() {
    var that = this;
    var form = this.data.form;
    var nick = String(form.nickname || "").trim();
    if (nick.length < 2) {
      wx.showToast({ title: "请填写有效昵称", icon: "none" });
      return;
    }
    var bio = String(form.bio || "").trim();
    var avatarLocal = String(form.avatarUrl || "").trim();
    var tags = String(form.tagsText || "")
      .split(/[,，\s]+/)
      .map(function (t) {
        return t.trim();
      })
      .filter(Boolean)
      .slice(0, 6);

    var hand = form.tennisHand || HAND_OPTS[0];
    var level = form.tennisLevel || LEVEL_OPTS[0];
    var style = form.tennisStyle || STYLE_OPTS[0];
    var surface = form.preferredSurface || SURFACE_OPTS[0];

    wx.showLoading({ title: "保存中", mask: true });

    var uploadPromise;
    if (!avatarLocal) {
      uploadPromise = Promise.resolve("");
    } else if (needsAvatarUpload(avatarLocal)) {
      uploadPromise = uploadNoteImage(
        avatarLocal,
        0,
        "avatar" + Date.now().toString(36)
      ).then(function (url) {
        var ok = usableAvatarUrl(url) || "";
        if (!ok) {
          return Promise.reject(new Error("头像上传失败，请重新选择头像"));
        }
        return ok;
      });
    } else {
      var ready = usableAvatarUrl(avatarLocal) || "";
      uploadPromise = ready
        ? Promise.resolve(ready)
        : Promise.reject(new Error("头像无效，请重新选择头像"));
    }

    uploadPromise
      .then(function (avatar) {
        saveProfile({
          nickname: nick,
          bio: bio,
          tags: tags,
          avatarUrl: avatar,
          tennisHand: hand,
          tennisLevel: level,
          tennisStyle: style,
          preferredSurface: surface,
        });
        that.setData({ "form.avatarUrl": avatar });
        return updateAuthProfile({
          nickname: nick,
          bio: bio,
          avatar_url: avatar,
          tags: tags,
          tennis_hand: hand,
          tennis_level: level,
          tennis_style: style,
          preferred_surface: surface,
        }).catch(function (err) {
          var msg = (err && err.message) || "";
          if (msg.indexOf("昵称") >= 0) {
            return Promise.reject(err);
          }
          return upsertMe();
        });
      })
      .then(function () {
        wx.hideLoading();
        wx.showToast({ title: "已保存", icon: "success" });
        setTimeout(function () {
          if (that.data.fromRegister) {
            wx.reLaunch({ url: "/pages/feed/index" });
          } else {
            wx.navigateBack({
              fail: function () {
                wx.switchTab({ url: "/pages/profile/index" });
              },
            });
          }
        }, 400);
      })
      .catch(function (err) {
        wx.hideLoading();
        wx.showToast({
          title: (err && err.message) || "保存失败",
          icon: "none",
        });
      });
  },

  onCancel() {
    if (this.data.fromRegister) {
      wx.reLaunch({ url: "/pages/feed/index" });
      return;
    }
    wx.navigateBack({
      fail: function () {
        wx.switchTab({ url: "/pages/profile/index" });
      },
    });
  },
});
