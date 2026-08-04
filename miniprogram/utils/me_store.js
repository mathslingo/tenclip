/**
 * 个人页本地资料 / 赞过 / 收藏（未接微信登录前用 storage）
 */
var PROFILE_KEY = "tenclip_me_profile";
var LIKES_KEY = "tenclip_me_likes";
var BOOKMARKS_KEY = "tenclip_me_bookmarks";

function defaultProfile() {
  return {
    nickname: "网球爱好者",
    uid: "10086",
    bio: "热爱网球，记录每一次击球与进步 🎾",
    location: "上海",
    gender: "♂",
    tags: ["正手", "发球", "资讯"],
    following: 0,
    followers: 0,
    avatarUrl: "",
  };
}

function readJson(key, fallback) {
  try {
    var raw = wx.getStorageSync(key);
    if (raw === "" || raw === undefined || raw === null) return fallback;
    if (typeof raw === "string") {
      try {
        return JSON.parse(raw);
      } catch (e) {
        return fallback;
      }
    }
    return raw;
  } catch (e) {
    return fallback;
  }
}

function writeJson(key, value) {
  try {
    wx.setStorageSync(key, value);
  } catch (e) {}
}

function getProfile() {
  var p = readJson(PROFILE_KEY, null);
  if (!p || typeof p !== "object") return defaultProfile();
  var base = defaultProfile();
  return {
    nickname: p.nickname || base.nickname,
    uid: p.uid || base.uid,
    bio: p.bio != null ? p.bio : base.bio,
    location: p.location || base.location,
    gender: p.gender || base.gender,
    tags: Array.isArray(p.tags) && p.tags.length ? p.tags : base.tags,
    following: Number(p.following) || 0,
    followers: Number(p.followers) || 0,
    avatarUrl: p.avatarUrl || "",
  };
}

function saveProfile(patch) {
  var next = Object.assign({}, getProfile(), patch || {});
  if (next.tags && !Array.isArray(next.tags)) {
    next.tags = String(next.tags)
      .split(/[,，\s]+/)
      .map(function (t) {
        return t.trim();
      })
      .filter(Boolean);
  }
  writeJson(PROFILE_KEY, next);
  return next;
}

function readIdList(key) {
  var list = readJson(key, []);
  if (!Array.isArray(list)) return [];
  return list.map(String).filter(Boolean);
}

function writeIdList(key, ids) {
  var uniq = [];
  var seen = {};
  (ids || []).forEach(function (id) {
    var s = String(id);
    if (!s || seen[s]) return;
    seen[s] = true;
    uniq.push(s);
  });
  writeJson(key, uniq);
  return uniq;
}

function getLikedIds() {
  return readIdList(LIKES_KEY);
}

function getBookmarkedIds() {
  return readIdList(BOOKMARKS_KEY);
}

function isLiked(id) {
  return getLikedIds().indexOf(String(id)) !== -1;
}

function isBookmarked(id) {
  return getBookmarkedIds().indexOf(String(id)) !== -1;
}

function toggleLike(id) {
  var sid = String(id || "");
  if (!sid) return { on: false, ids: getLikedIds() };
  var ids = getLikedIds();
  var idx = ids.indexOf(sid);
  var on;
  if (idx === -1) {
    ids.unshift(sid);
    on = true;
  } else {
    ids.splice(idx, 1);
    on = false;
  }
  writeIdList(LIKES_KEY, ids);
  return { on: on, ids: ids };
}

function toggleBookmark(id) {
  var sid = String(id || "");
  if (!sid) return { on: false, ids: getBookmarkedIds() };
  var ids = getBookmarkedIds();
  var idx = ids.indexOf(sid);
  var on;
  if (idx === -1) {
    ids.unshift(sid);
    on = true;
  } else {
    ids.splice(idx, 1);
    on = false;
  }
  writeIdList(BOOKMARKS_KEY, ids);
  return { on: on, ids: ids };
}

function statsFromLists(profile) {
  var p = profile || getProfile();
  var likes = getLikedIds().length;
  var bookmarks = getBookmarkedIds().length;
  return {
    following: p.following,
    followers: p.followers,
    likedCollect: likes + bookmarks,
  };
}

module.exports = {
  getProfile: getProfile,
  saveProfile: saveProfile,
  defaultProfile: defaultProfile,
  getLikedIds: getLikedIds,
  getBookmarkedIds: getBookmarkedIds,
  isLiked: isLiked,
  isBookmarked: isBookmarked,
  toggleLike: toggleLike,
  toggleBookmark: toggleBookmark,
  statsFromLists: statsFromLists,
};
