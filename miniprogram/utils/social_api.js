const { API_BASE_URL } = require("./config");
const { getUserId, getLocalProfile } = require("./user_id");

function absUrl(path) {
  var p = String(path || "");
  if (!p) return "";
  if (/^https?:\/\//i.test(p)) return p;
  if (p.indexOf("//") === 0) return "https:" + p;
  var base = String(API_BASE_URL || "").replace(/\/$/, "");
  if (p.charAt(0) !== "/") p = "/" + p;
  return base + p;
}

function request(opts) {
  var data = opts.data;
  var header = opts.header || { "content-type": "application/json" };
  // 明确用 JSON 字符串，避免微信自动编码成 form-urlencoded 导致 FastAPI 422
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

function ensureUserId() {
  var uid = getUserId();
  if (!uid) {
    throw new Error("用户 ID 未初始化，请先到「我的」页面");
  }
  return uid;
}

function upsertMe() {
  var p = getLocalProfile();
  var uid = ensureUserId();
  return request({
    url: API_BASE_URL + "/api/social/users/upsert",
    method: "POST",
    data: {
      user_id: uid,
      nickname: p.nickname || "网球爱好者",
      avatar_url: p.avatar_url || "",
      bio: p.bio || "",
    },
  });
}

function fetchUser(userId, viewerId) {
  var q = viewerId ? "?viewer_id=" + encodeURIComponent(viewerId) : "";
  return request({
    url: API_BASE_URL + "/api/social/users/" + encodeURIComponent(userId) + q,
  });
}

function follow(followeeId) {
  var uid = ensureUserId();
  return request({
    url: API_BASE_URL + "/api/social/follow",
    method: "POST",
    data: { follower_id: uid, followee_id: followeeId },
  });
}

function unfollow(followeeId) {
  var uid = ensureUserId();
  return request({
    url: API_BASE_URL + "/api/social/unfollow",
    method: "POST",
    data: { follower_id: uid, followee_id: followeeId },
  });
}

function fetchFollowList(userId, kind) {
  var path = kind === "followers" ? "/followers" : "/following";
  return request({
    url:
      API_BASE_URL +
      "/api/social/users/" +
      encodeURIComponent(userId) +
      path,
  }).then(function (body) {
    return (body && body.items) || [];
  });
}

function uploadNoteImage(filePath, index, key) {
  return new Promise(function (resolve, reject) {
    wx.uploadFile({
      url: API_BASE_URL + "/api/social/uploads",
      filePath: filePath,
      name: "file",
      formData: { key: key || "", index: String(index || 0) },
      timeout: 60000,
      success: function (res) {
        try {
          var body =
            typeof res.data === "string" ? JSON.parse(res.data) : res.data;
          if (res.statusCode >= 200 && res.statusCode < 300 && body && body.url) {
            resolve(body.url);
            return;
          }
        } catch (e) {}
        reject(new Error("图片上传失败"));
      },
      fail: function (err) {
        reject(new Error((err && err.errMsg) || "图片上传失败"));
      },
    });
  });
}

function publishNote(payload) {
  var uid = ensureUserId();
  var images = payload.imagePaths || [];
  var key = "u" + Date.now().toString(36);
  var chain = Promise.resolve([]);
  images.forEach(function (p, i) {
    chain = chain.then(function (urls) {
      return uploadNoteImage(p, i, key).then(function (url) {
        urls.push(url);
        return urls;
      });
    });
  });
  return chain.then(function (urls) {
    return request({
      url: API_BASE_URL + "/api/social/notes",
      method: "POST",
      data: {
        user_id: uid,
        title: (payload.title || "").trim(),
        body: (payload.body || "").trim(),
        image_urls: urls,
      },
    });
  });
}

function listNotes(userId) {
  var q = userId ? "?user_id=" + encodeURIComponent(userId) : "";
  return request({
    url: API_BASE_URL + "/api/social/notes" + q,
  }).then(function (body) {
    return ((body && body.items) || []).map(normalizeNote);
  });
}

function searchNotes(keyword) {
  return request({
    url:
      API_BASE_URL +
      "/api/social/notes/search?q=" +
      encodeURIComponent((keyword || "").trim()),
  }).then(function (body) {
    return ((body && body.items) || []).map(normalizeNote);
  });
}

function getNote(noteId) {
  return request({
    url: API_BASE_URL + "/api/social/notes/" + encodeURIComponent(noteId),
  }).then(normalizeNote);
}

function deleteNote(noteId) {
  var uid = ensureUserId();
  return request({
    url:
      API_BASE_URL +
      "/api/social/notes/" +
      encodeURIComponent(noteId) +
      "?user_id=" +
      encodeURIComponent(uid),
    method: "DELETE",
  });
}

function normalizeNote(n) {
  if (!n) return n;
  var images = (n.images || []).map(absUrl);
  var cover = absUrl(n.image_url || n.cover || (images[0] || ""));
  return Object.assign({}, n, {
    id: n.id || ("note-" + n.note_id),
    kind: "note",
    cover: cover,
    image_url: cover,
    images: images,
    cover_ratio: 1.25,
    author_name: n.author_name || n.source || "球友",
    author_initial: String(n.author_name || n.source || "球").charAt(0),
    summary: n.body || n.summary || "",
    isLocalNote: false,
  });
}

module.exports = {
  absUrl: absUrl,
  upsertMe: upsertMe,
  fetchUser: fetchUser,
  follow: follow,
  unfollow: unfollow,
  fetchFollowList: fetchFollowList,
  publishNote: publishNote,
  listNotes: listNotes,
  searchNotes: searchNotes,
  getNote: getNote,
  deleteNote: deleteNote,
  normalizeNote: normalizeNote,
};
