const slamBehavior = require("../../utils/config").slamBehavior;
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
var STYLE_OPTS = ["底线型", "发球上网", "全能型", "防守反击", "力量型"];
var SURFACE_OPTS = ["硬地", "红土", "草地", "室内"];
var NTRP_OPTS = ["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0", "5.0+"];
var SKILL_OPTS = ["入门", "初级", "中级", "进阶", "高级"];
var OLD_LEVEL_TO_NTRP = {
  入门: "1.5",
  初级: "2.0",
  进阶: "2.5",
  中级: "3.0",
  高级: "3.5",
  竞赛: "4.0",
};

function indexOfOr(list, value, fallback) {
  var i = list.indexOf(value);
  if (i >= 0) return i;
  return typeof fallback === "number" ? fallback : 0;
}

function normalizeNtrp(raw) {
  var v = String(raw || "").trim();
  if (!v) return NTRP_OPTS[2]; // 默认 2.0
  if (NTRP_OPTS.indexOf(v) >= 0) return v;
  if (OLD_LEVEL_TO_NTRP[v]) return OLD_LEVEL_TO_NTRP[v];
  var m = v.match(/(\d+(?:\.\d+)?)\+?/);
  if (m) {
    var n = parseFloat(m[1]);
    if (n >= 5) return "5.0+";
    var key = n.toFixed(1);
    if (NTRP_OPTS.indexOf(key) >= 0) return key;
  }
  return NTRP_OPTS[2];
}

function normalizeSkill(raw) {
  var v = String(raw || "").trim();
  if (SKILL_OPTS.indexOf(v) >= 0) return v;
  if (v === "竞赛") return "高级";
  return SKILL_OPTS[0];
}

Page({
  behaviors: [slamBehavior],
  data: {
    fromRegister: false,
    nickHint: "",
    handOpts: HAND_OPTS,
    styleOpts: STYLE_OPTS,
    surfaceOpts: SURFACE_OPTS,
    ntrpOpts: NTRP_OPTS,
    skillOpts: SKILL_OPTS,
    form: {
      nickname: "",
      bio: "",
      tagsText: "",
      avatarUrl: "",
      tennisHand: "",
      tennisLevel: "",
      tennisStyle: "",
      preferredSurface: "",
      tennisServeLevel: "",
      tennisForehandLevel: "",
      tennisBackhandLevel: "",
      handIndex: 0,
      ntrpIndex: 2,
      styleIndex: 0,
      surfaceIndex: 0,
      serveIndex: 0,
      forehandIndex: 0,
      backhandIndex: 0,
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
    var level = normalizeNtrp(
      (serverUser && serverUser.tennis_level) || p.tennisLevel || ""
    );
    var style = (serverUser && serverUser.tennis_style) || p.tennisStyle || "";
    var surface =
      (serverUser && serverUser.preferred_surface) || p.preferredSurface || "";
    var serve = normalizeSkill(
      (serverUser && serverUser.tennis_serve_level) || p.tennisServeLevel || ""
    );
    var forehand = normalizeSkill(
      (serverUser && serverUser.tennis_forehand_level) ||
        p.tennisForehandLevel ||
        ""
    );
    var backhand = normalizeSkill(
      (serverUser && serverUser.tennis_backhand_level) ||
        p.tennisBackhandLevel ||
        ""
    );

    this.setData({
      form: {
        nickname: nick,
        bio: bio,
        tagsText: (tags || []).join(","),
        avatarUrl: avatar,
        tennisHand: hand || HAND_OPTS[0],
        tennisLevel: level,
        tennisStyle: style || STYLE_OPTS[0],
        preferredSurface: surface || SURFACE_OPTS[0],
        tennisServeLevel: serve,
        tennisForehandLevel: forehand,
        tennisBackhandLevel: backhand,
        handIndex: indexOfOr(HAND_OPTS, hand || HAND_OPTS[0], 0),
        ntrpIndex: indexOfOr(NTRP_OPTS, level, 2),
        styleIndex: indexOfOr(STYLE_OPTS, style || STYLE_OPTS[0], 0),
        surfaceIndex: indexOfOr(SURFACE_OPTS, surface || SURFACE_OPTS[0], 0),
        serveIndex: indexOfOr(SKILL_OPTS, serve, 0),
        forehandIndex: indexOfOr(SKILL_OPTS, forehand, 0),
        backhandIndex: indexOfOr(SKILL_OPTS, backhand, 0),
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

  onPickNtrp(e) {
    var i = Number(e.detail.value) || 0;
    this.setData({
      "form.ntrpIndex": i,
      "form.tennisLevel": NTRP_OPTS[i],
    });
  },

  onPickServe(e) {
    var i = Number(e.detail.value) || 0;
    this.setData({
      "form.serveIndex": i,
      "form.tennisServeLevel": SKILL_OPTS[i],
    });
  },

  onPickForehand(e) {
    var i = Number(e.detail.value) || 0;
    this.setData({
      "form.forehandIndex": i,
      "form.tennisForehandLevel": SKILL_OPTS[i],
    });
  },

  onPickBackhand(e) {
    var i = Number(e.detail.value) || 0;
    this.setData({
      "form.backhandIndex": i,
      "form.tennisBackhandLevel": SKILL_OPTS[i],
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
    var level = normalizeNtrp(form.tennisLevel);
    var style = form.tennisStyle || STYLE_OPTS[0];
    var surface = form.preferredSurface || SURFACE_OPTS[0];
    var serve = normalizeSkill(form.tennisServeLevel);
    var forehand = normalizeSkill(form.tennisForehandLevel);
    var backhand = normalizeSkill(form.tennisBackhandLevel);

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
          tennisServeLevel: serve,
          tennisForehandLevel: forehand,
          tennisBackhandLevel: backhand,
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
          tennis_serve_level: serve,
          tennis_forehand_level: forehand,
          tennis_backhand_level: backhand,
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
