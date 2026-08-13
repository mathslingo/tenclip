/**
 * 本机用户 ID（v1 未接 wx.login 会话，用 storage 持久化）
 */
var USER_KEY = "tenclip_user_profile";
var ME_PROFILE_KEY = "tenclip_me_profile";
var UID_KEY = "tenclip_user_id";

function _readJson(key) {
  try {
    var raw = wx.getStorageSync(key);
    if (!raw) return null;
    if (typeof raw === "string") {
      try {
        return JSON.parse(raw);
      } catch (e) {
        return null;
      }
    }
    return raw;
  } catch (e) {
    return null;
  }
}

function getUserId() {
  try {
    var stored = wx.getStorageSync(UID_KEY);
    if (stored) return String(stored);
  } catch (e) {}
  var p = _readJson(USER_KEY) || {};
  if (p.userId) {
    try {
      wx.setStorageSync(UID_KEY, p.userId);
    } catch (e2) {}
    return String(p.userId);
  }
  var me = _readJson(ME_PROFILE_KEY) || {};
  if (me.uid && me.uid !== "10086") {
    try {
      wx.setStorageSync(UID_KEY, me.uid);
    } catch (e3) {}
    return String(me.uid);
  }
  var id = "UC" + Date.now().toString(36).toUpperCase();
  try {
    wx.setStorageSync(UID_KEY, id);
  } catch (e4) {}
  return id;
}

function getLocalProfile() {
  var me = _readJson(ME_PROFILE_KEY) || {};
  var user = _readJson(USER_KEY) || {};
  return {
    user_id: getUserId(),
    nickname: me.nickname || user.nickName || "网球爱好者",
    avatar_url: me.avatarUrl || user.avatarUrl || "",
    bio: me.bio || "",
  };
}

module.exports = {
  getUserId: getUserId,
  getLocalProfile: getLocalProfile,
};
