/**
 * 登录会话：微信 / 游客昵称密码；token 存本地，写操作带 Authorization。
 */
const { API_BASE_URL } = require("./config");

var TOKEN_KEY = "tenclip_auth_token";
var AUTH_KEY = "tenclip_auth_done";
var UID_KEY = "tenclip_user_id";
var USER_KEY = "tenclip_user_profile";
var ME_PROFILE_KEY = "tenclip_me_profile";
var EXPIRES_KEY = "tenclip_auth_expires_at";
var GUEST_KEY = "tenclip_guest_mode";

function getToken() {
  try {
    return String(wx.getStorageSync(TOKEN_KEY) || "");
  } catch (e) {
    return "";
  }
}

function isLoggedIn() {
  var token = getToken();
  if (!token) return false;
  try {
    var exp = Number(wx.getStorageSync(EXPIRES_KEY) || 0);
    if (exp && exp * 1000 < Date.now()) {
      clearSession();
      return false;
    }
  } catch (e) {}
  return true;
}

/** 仅浏览、无账号会话（非游客账号登录） */
function isGuest() {
  if (isLoggedIn()) return false;
  try {
    return wx.getStorageSync(GUEST_KEY) === "1" || wx.getStorageSync(GUEST_KEY) === true;
  } catch (e) {
    return false;
  }
}

function enterGuest() {
  clearSession();
  try {
    wx.removeStorageSync(UID_KEY);
    wx.setStorageSync(GUEST_KEY, "1");
  } catch (e) {}
}

function clearSession() {
  try {
    wx.removeStorageSync(TOKEN_KEY);
    wx.removeStorageSync(AUTH_KEY);
    wx.removeStorageSync(EXPIRES_KEY);
  } catch (e) {}
}

function applyUserToLocal(user) {
  if (!user) return;
  try {
    var prev = {};
    var raw = wx.getStorageSync(USER_KEY);
    if (raw) {
      prev = typeof raw === "string" ? JSON.parse(raw) : raw;
    }
    wx.setStorageSync(
      USER_KEY,
      JSON.stringify(
        Object.assign({}, prev, {
          userId: user.user_id || prev.userId,
          nickName: user.nickname || prev.nickName || "网球爱好者",
          avatarUrl: user.avatar_url || prev.avatarUrl || "",
        })
      )
    );
  } catch (e) {}
  try {
    var me = {};
    var meRaw = wx.getStorageSync(ME_PROFILE_KEY);
    if (meRaw) {
      me = typeof meRaw === "string" ? JSON.parse(meRaw) : meRaw;
    }
    wx.setStorageSync(
      ME_PROFILE_KEY,
      Object.assign({}, me, {
        uid: user.user_id || me.uid,
        nickname: user.nickname || me.nickname || "网球爱好者",
        avatarUrl: user.avatar_url || me.avatarUrl || "",
        bio: user.bio != null ? user.bio : me.bio || "",
        tags: Array.isArray(user.tags) ? user.tags : me.tags,
        tennisHand: user.tennis_hand != null ? user.tennis_hand : me.tennisHand || "",
        tennisLevel: user.tennis_level != null ? user.tennis_level : me.tennisLevel || "",
        tennisStyle: user.tennis_style != null ? user.tennis_style : me.tennisStyle || "",
        preferredSurface:
          user.preferred_surface != null ? user.preferred_surface : me.preferredSurface || "",
        accountType: user.account_type || me.accountType || "",
      })
    );
  } catch (e2) {}
}

function saveSession(body) {
  var token = body && body.token;
  var user = (body && body.user) || {};
  if (!token) throw new Error("登录失败：无 token");
  try {
    wx.removeStorageSync(GUEST_KEY);
  } catch (e0) {}
  wx.setStorageSync(TOKEN_KEY, token);
  wx.setStorageSync(AUTH_KEY, true);
  if (body.expires_at) {
    wx.setStorageSync(EXPIRES_KEY, body.expires_at);
  }
  if (user.user_id) {
    wx.setStorageSync(UID_KEY, user.user_id);
  }
  applyUserToLocal(user);
  return body;
}

function authHeaders(extra) {
  var h = Object.assign({ "content-type": "application/json" }, extra || {});
  var token = getToken();
  if (token) h.Authorization = "Bearer " + token;
  return h;
}

function request(opts) {
  var data = opts.data;
  var header = opts.header || authHeaders();
  if (data && typeof data === "object" && String(header["content-type"] || "") === "application/json") {
    data = JSON.stringify(data);
  }
  return new Promise(function (resolve, reject) {
    wx.request({
      url: opts.url,
      method: opts.method || "GET",
      data: data,
      header: header,
      timeout: opts.timeout || 20000,
      success: function (res) {
        if (res.statusCode === 401) {
          clearSession();
          reject(new Error("请先登录"));
          return;
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        var detail =
          (res.data && (res.data.detail || res.data.error)) ||
          "请求失败 " + res.statusCode;
        reject(new Error(typeof detail === "string" ? detail : "请求失败"));
      },
      fail: function (err) {
        reject(new Error((err && err.errMsg) || "网络错误"));
      },
    });
  });
}

function wxLoginCode() {
  return new Promise(function (resolve, reject) {
    wx.login({
      success: function (res) {
        if (res && res.code) {
          resolve(res.code);
          return;
        }
        reject(new Error("wx.login 未返回 code"));
      },
      fail: function (err) {
        reject(new Error((err && err.errMsg) || "wx.login 失败"));
      },
    });
  });
}

function loginWithWechat() {
  return wxLoginCode().then(function (code) {
    return request({
      url: API_BASE_URL + "/api/auth/wechat/login",
      method: "POST",
      header: { "content-type": "application/json" },
      data: { code: code, device_hint: "miniprogram" },
    }).then(saveSession);
  });
}

function registerGuest(nickname, password) {
  return request({
    url: API_BASE_URL + "/api/auth/guest/register",
    method: "POST",
    header: { "content-type": "application/json" },
    data: {
      nickname: String(nickname || "").trim(),
      password: String(password || "").trim(),
      device_hint: "miniprogram",
    },
  }).then(saveSession);
}

function loginGuest(nickname, password) {
  return request({
    url: API_BASE_URL + "/api/auth/guest/login",
    method: "POST",
    header: { "content-type": "application/json" },
    data: {
      nickname: String(nickname || "").trim(),
      password: String(password || "").trim(),
      device_hint: "miniprogram",
    },
  }).then(saveSession);
}

function checkNickname(nickname) {
  var nick = encodeURIComponent(String(nickname || "").trim());
  return request({
    url: API_BASE_URL + "/api/auth/nickname/check?nickname=" + nick,
    method: "GET",
    header: authHeaders(),
  });
}

function fetchMe() {
  return request({
    url: API_BASE_URL + "/api/auth/me",
    method: "GET",
    header: authHeaders(),
  }).then(function (user) {
    applyUserToLocal(user);
    return user;
  });
}

function logout() {
  var token = getToken();
  var p = Promise.resolve();
  if (token) {
    p = request({
      url: API_BASE_URL + "/api/auth/logout",
      method: "POST",
      header: authHeaders(),
    }).catch(function () {});
  }
  return p.then(function () {
    clearSession();
  });
}

function updateAuthProfile(payload) {
  return request({
    url: API_BASE_URL + "/api/auth/profile",
    method: "POST",
    header: authHeaders(),
    data: {
      nickname: (payload && payload.nickname) || "",
      avatar_url: (payload && payload.avatar_url) || "",
      bio: (payload && payload.bio) || "",
      tags: (payload && payload.tags) || [],
      location: (payload && payload.location) || "",
      tennis_hand: (payload && payload.tennis_hand) || "",
      tennis_level: (payload && payload.tennis_level) || "",
      tennis_style: (payload && payload.tennis_style) || "",
      preferred_surface: (payload && payload.preferred_surface) || "",
    },
  }).then(function (user) {
    saveSession({
      token: getToken(),
      expires_at: wx.getStorageSync(EXPIRES_KEY),
      user: user,
    });
    return user;
  });
}

function requireLogin(redirectQuery) {
  if (isLoggedIn()) return true;
  var q = redirectQuery ? "?from=" + encodeURIComponent(redirectQuery) : "";
  // 用 navigateTo 保留页面栈，支持返回键 / 左滑返回
  wx.navigateTo({
    url: "/pages/login/index" + q,
    fail: function () {
      wx.redirectTo({ url: "/pages/login/index" + q });
    },
  });
  return false;
}

module.exports = {
  TOKEN_KEY: TOKEN_KEY,
  getToken: getToken,
  isLoggedIn: isLoggedIn,
  isGuest: isGuest,
  enterGuest: enterGuest,
  clearSession: clearSession,
  authHeaders: authHeaders,
  request: request,
  loginWithWechat: loginWithWechat,
  registerGuest: registerGuest,
  loginGuest: loginGuest,
  checkNickname: checkNickname,
  fetchMe: fetchMe,
  logout: logout,
  updateAuthProfile: updateAuthProfile,
  requireLogin: requireLogin,
};
