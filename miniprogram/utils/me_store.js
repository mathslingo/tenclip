/**
 * 个人页本地资料 / 赞过 / 收藏 / 作品笔记（未接服务端前用 storage + USER_DATA_PATH）
 */
var PROFILE_KEY = "tenclip_me_profile";
var LIKES_KEY = "tenclip_me_likes";
var BOOKMARKS_KEY = "tenclip_me_bookmarks";
var NOTES_KEY = "tenclip_me_notes";

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

function listNotes() {
  var list = readJson(NOTES_KEY, []);
  if (!Array.isArray(list)) return [];
  return list.slice().sort(function (a, b) {
    return (b.createdAt || 0) - (a.createdAt || 0);
  });
}

function getNoteById(id) {
  var sid = String(id || "");
  if (!sid) return null;
  var list = listNotes();
  for (var i = 0; i < list.length; i++) {
    if (String(list[i].id) === sid) return list[i];
  }
  return null;
}

function ensureDir(dirPath) {
  return new Promise(function (resolve) {
    var fs = wx.getFileSystemManager();
    try {
      fs.accessSync(dirPath);
      resolve(dirPath);
    } catch (e) {
      try {
        fs.mkdirSync(dirPath, true);
      } catch (e2) {}
      resolve(dirPath);
    }
  });
}

function saveImageToUserData(tempPath, noteId, index) {
  return new Promise(function (resolve) {
    if (!tempPath) {
      resolve("");
      return;
    }
    var root = (wx.env && wx.env.USER_DATA_PATH) || "";
    if (!root) {
      resolve(tempPath);
      return;
    }
    var noteDir = root + "/notes/" + noteId;
    ensureDir(root + "/notes")
      .then(function () {
        return ensureDir(noteDir);
      })
      .then(function () {
        var ext = ".jpg";
        var m = String(tempPath).match(/(\.[a-zA-Z0-9]+)(\?|$)/);
        if (m && m[1]) ext = m[1].toLowerCase();
        if (ext !== ".jpg" && ext !== ".jpeg" && ext !== ".png" && ext !== ".webp") {
          ext = ".jpg";
        }
        var dest = noteDir + "/" + index + ext;
        wx.getFileSystemManager().saveFile({
          tempFilePath: tempPath,
          filePath: dest,
          success: function (res) {
            resolve(res.savedFilePath || dest);
          },
          fail: function () {
            wx.getFileSystemManager().saveFile({
              tempFilePath: tempPath,
              success: function (res2) {
                resolve(res2.savedFilePath || tempPath);
              },
              fail: function () {
                resolve(tempPath);
              },
            });
          },
        });
      });
  });
}

/**
 * @param {{ title?: string, body: string, imagePaths: string[] }} payload
 */
function addNote(payload) {
  var title = String((payload && payload.title) || "").trim();
  var body = String((payload && payload.body) || "").trim();
  var temps = (payload && payload.imagePaths) || [];
  if (!Array.isArray(temps)) temps = [];
  temps = temps.filter(Boolean).slice(0, 9);

  if (!body && !temps.length) {
    return Promise.reject(new Error("请填写正文或添加图片"));
  }

  var id = "n" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  var tasks = temps.map(function (p, i) {
    return saveImageToUserData(p, id, i);
  });

  return Promise.all(tasks).then(function (savedPaths) {
    savedPaths = (savedPaths || []).filter(Boolean);
    var note = {
      id: id,
      title: title || (body ? body.slice(0, 24) : "未命名笔记"),
      body: body,
      images: savedPaths,
      cover: savedPaths[0] || "",
      cover_ratio: 1.25,
      createdAt: Date.now(),
    };
    var list = listNotes();
    list.unshift(note);
    writeJson(NOTES_KEY, list);
    try {
      wx.setStorageSync("tenclip_me_open_works", "1");
    } catch (e) {}
    return note;
  });
}

function deleteNote(id) {
  var sid = String(id || "");
  if (!sid) return false;
  var list = listNotes();
  var next = [];
  var removed = null;
  list.forEach(function (n) {
    if (String(n.id) === sid) removed = n;
    else next.push(n);
  });
  if (!removed) return false;
  writeJson(NOTES_KEY, next);

  var root = (wx.env && wx.env.USER_DATA_PATH) || "";
  if (root) {
    try {
      wx.getFileSystemManager().rmdir({
        dirPath: root + "/notes/" + sid,
        recursive: true,
      });
    } catch (e) {}
  }
  (removed.images || []).forEach(function (p) {
    try {
      wx.getFileSystemManager().unlink({ filePath: p });
    } catch (e2) {}
  });
  return true;
}

function notesAsFeedItems(notes) {
  return (notes || []).map(function (n) {
    return {
      id: n.id,
      title: n.title || "笔记",
      cover: n.cover || (n.images && n.images[0]) || "",
      cover_ratio: n.cover_ratio || 1.25,
      coverFailed: !!(!(n.cover || (n.images && n.images[0]))),
      author_initial: "我",
      author_name: "我",
      like_count: 0,
      isLocalNote: true,
    };
  });
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
  listNotes: listNotes,
  getNoteById: getNoteById,
  addNote: addNote,
  deleteNote: deleteNote,
  notesAsFeedItems: notesAsFeedItems,
};
