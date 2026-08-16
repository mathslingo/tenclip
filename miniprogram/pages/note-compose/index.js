const { publishNote, upsertMe } = require("../../utils/social_api");
const { requirePrivacyIfNeeded } = require("../../utils/api");
const { isLoggedIn, requireLogin } = require("../../utils/auth_api");

function pad2(n) {
  return ("0" + n).slice(-2);
}

function daysInMonth(year, month) {
  return new Date(year, month, 0).getDate();
}

function buildPickerRange(year, month) {
  var now = new Date();
  var y0 = now.getFullYear() - 1;
  var years = [];
  for (var i = 0; i < 4; i++) years.push(String(y0 + i));
  var months = [];
  for (var m = 1; m <= 12; m++) months.push(pad2(m));
  var dim = daysInMonth(year, month);
  var days = [];
  for (var d = 1; d <= dim; d++) days.push(pad2(d));
  var hours = [];
  for (var h = 0; h < 24; h++) hours.push(pad2(h) + "时");
  return [years, months, days, hours];
}

function defaultPickerValue() {
  var now = new Date();
  var y0 = now.getFullYear() - 1;
  return [
    now.getFullYear() - y0,
    now.getMonth(),
    now.getDate() - 1,
    now.getHours(),
  ];
}

function formatFromPicker(range, value) {
  var y = range[0][value[0]];
  var m = range[1][value[1]];
  var d = range[2][value[2]];
  var h = String(range[3][value[3]] || "").replace("时", "");
  return y + "-" + m + "-" + d + " " + h + ":00";
}

function eventAtFromPicker(range, value) {
  var y = Number(range[0][value[0]]);
  var m = Number(range[1][value[1]]) - 1;
  var d = Number(range[2][value[2]]);
  var h = Number(String(range[3][value[3]] || "").replace("时", ""));
  var dt = new Date(y, m, d, h, 0, 0, 0);
  return Math.floor(dt.getTime() / 1000);
}

Page({
  data: {
    title: "",
    body: "",
    images: [],
    busy: false,
    locationEnabled: false,
    locationName: "",
    locationAddress: "",
    latitude: null,
    longitude: null,
    timeEnabled: false,
    dtRange: [[], [], [], []],
    dtValue: [1, 0, 0, 0],
    eventTimeText: "",
  },

  onLoad() {
    var value = defaultPickerValue();
    var now = new Date();
    var range = buildPickerRange(now.getFullYear(), now.getMonth() + 1);
    // clamp day index if needed
    if (value[2] >= range[2].length) value[2] = range[2].length - 1;
    this.setData({
      dtRange: range,
      dtValue: value,
      eventTimeText: formatFromPicker(range, value),
    });
  },

  onShow() {
    if (!isLoggedIn()) {
      requireLogin("note-compose");
    }
  },

  onTitle(e) {
    this.setData({ title: (e.detail && e.detail.value) || "" });
  },

  onBody(e) {
    this.setData({ body: (e.detail && e.detail.value) || "" });
  },

  onToggleLocation(e) {
    var on = !!(e.detail && e.detail.value);
    if (!on) {
      this.setData({
        locationEnabled: false,
        locationName: "",
        locationAddress: "",
        latitude: null,
        longitude: null,
      });
      return;
    }
    this.setData({ locationEnabled: true });
    if (!this.data.locationName && !this.data.locationAddress) {
      this.onPickLocation();
    }
  },

  onPickLocation() {
    var that = this;
    requirePrivacyIfNeeded()
      .then(function () {
        return new Promise(function (resolve, reject) {
          wx.chooseLocation({
            success: resolve,
            fail: reject,
          });
        });
      })
      .then(function (res) {
        that.setData({
          locationEnabled: true,
          locationName: res.name || res.address || "已选位置",
          locationAddress: res.address || "",
          latitude: res.latitude,
          longitude: res.longitude,
        });
      })
      .catch(function (err) {
        var msg = (err && err.errMsg) || "";
        if (/cancel|取消/i.test(msg)) return;
        wx.showToast({
          title: /auth deny|authorize|隐私|permission/i.test(msg)
            ? "请允许位置权限后重试"
            : "选点失败",
          icon: "none",
        });
      });
  },

  onClearLocation() {
    this.setData({
      locationName: "",
      locationAddress: "",
      latitude: null,
      longitude: null,
    });
  },

  onToggleTime(e) {
    var on = !!(e.detail && e.detail.value);
    if (!on) {
      this.setData({ timeEnabled: false });
      return;
    }
    var value = this.data.dtValue || defaultPickerValue();
    var y = Number(this.data.dtRange[0][value[0]] || new Date().getFullYear());
    var m = Number(this.data.dtRange[1][value[1]] || 1);
    var range = buildPickerRange(y, m);
    if (value[2] >= range[2].length) value[2] = range[2].length - 1;
    this.setData({
      timeEnabled: true,
      dtRange: range,
      dtValue: value,
      eventTimeText: formatFromPicker(range, value),
    });
  },

  onDtColumnChange(e) {
    var col = e.detail.column;
    var idx = e.detail.value;
    var value = (this.data.dtValue || []).slice();
    value[col] = idx;
    var range = this.data.dtRange;
    var y = Number(range[0][value[0]]);
    var m = Number(range[1][value[1]]);
    if (col === 0 || col === 1) {
      range = buildPickerRange(y, m);
      if (value[2] >= range[2].length) value[2] = range[2].length - 1;
    }
    this.setData({
      dtRange: range,
      dtValue: value,
      eventTimeText: formatFromPicker(range, value),
    });
  },

  onDtChange(e) {
    var value = e.detail.value;
    var range = this.data.dtRange;
    var y = Number(range[0][value[0]]);
    var m = Number(range[1][value[1]]);
    range = buildPickerRange(y, m);
    if (value[2] >= range[2].length) value[2] = range[2].length - 1;
    this.setData({
      dtRange: range,
      dtValue: value,
      eventTimeText: formatFromPicker(range, value),
    });
  },

  onAddImages() {
    var that = this;
    var remain = 9 - (this.data.images || []).length;
    if (remain <= 0) return;

    requirePrivacyIfNeeded()
      .then(function () {
        return new Promise(function (resolve, reject) {
          wx.chooseMedia({
            count: remain,
            mediaType: ["image"],
            sourceType: ["album", "camera"],
            success: resolve,
            fail: reject,
          });
        });
      })
      .then(function (res) {
        var files = (res.tempFiles || []).map(function (f) {
          return f.tempFilePath;
        });
        that.setData({ images: that.data.images.concat(files).slice(0, 9) });
      })
      .catch(function () {});
  },

  onRemoveImage(e) {
    var index = Number(e.currentTarget.dataset.index);
    var images = (this.data.images || []).slice();
    if (index < 0 || index >= images.length) return;
    images.splice(index, 1);
    this.setData({ images: images });
  },

  onPreview(e) {
    var index = Number(e.currentTarget.dataset.index);
    wx.previewImage({
      current: this.data.images[index],
      urls: this.data.images,
    });
  },

  onPublish() {
    var that = this;
    if (this.data.busy) return;
    if (!isLoggedIn()) {
      requireLogin("note-compose");
      return;
    }
    var body = String(this.data.body || "").trim();
    var images = this.data.images || [];
    if (!body && !images.length) {
      wx.showToast({ title: "请填写正文或添加图片", icon: "none" });
      return;
    }
    if (this.data.locationEnabled && !this.data.locationName && !this.data.locationAddress) {
      wx.showToast({ title: "请选择地图位置，或关闭地点", icon: "none" });
      return;
    }

    var payload = {
      title: that.data.title,
      body: body,
      imagePaths: images,
    };
    if (this.data.locationEnabled && (this.data.locationName || this.data.locationAddress)) {
      payload.location_name = this.data.locationName || "";
      payload.location_address = this.data.locationAddress || "";
      if (
        typeof this.data.latitude === "number" &&
        typeof this.data.longitude === "number"
      ) {
        payload.latitude = this.data.latitude;
        payload.longitude = this.data.longitude;
      }
    }
    if (this.data.timeEnabled) {
      payload.event_at = eventAtFromPicker(this.data.dtRange, this.data.dtValue);
    }

    this.setData({ busy: true });
    upsertMe()
      .catch(function () {})
      .then(function () {
        return publishNote(payload);
      })
      .then(function () {
        try {
          wx.setStorageSync("tenclip_me_open_works", "1");
        } catch (e) {}
        wx.showToast({ title: "已发布", icon: "success" });
        setTimeout(function () {
          wx.switchTab({ url: "/pages/profile/index" });
        }, 400);
      })
      .catch(function (err) {
        wx.showToast({
          title: (err && err.message) || "发布失败",
          icon: "none",
        });
        that.setData({ busy: false });
      });
  },
});
