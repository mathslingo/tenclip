var STORAGE_KEY = "tenclip_slam_theme";

var THEMES = [
  {
    id: "wimbledon",
    name: "温网草地",
    hint: "绿草条纹",
    nav: "#0c3b2e",
    front: "#ffffff",
    accent: "#3dffb0",
    accentInk: "#042018",
    swatch: "linear-gradient(90deg,#0c3b2e 0%,#0c3b2e 42%,#145c40 42%,#145c40 58%,#0c3b2e 58%,#0c3b2e 100%)",
    vars: "--court-a:#0c3b2e;--court-b:#145c40;--line:#9dffe0;--accent:#3dffb0;--accent-ink:#042018;--ink:#e8fff4;--muted:#9dffe0;",
  },
  {
    id: "roland",
    name: "法网红土",
    hint: "陶土球场",
    nav: "#7a341f",
    front: "#ffffff",
    accent: "#ffe14a",
    accentInk: "#3a140c",
    swatch: "linear-gradient(90deg,#8d4030 0%,#8d4030 42%,#c4623e 42%,#c4623e 58%,#8d4030 58%,#8d4030 100%)",
    vars: "--court-a:#8d4030;--court-b:#c4623e;--line:#ffe7c2;--accent:#ffe14a;--accent-ink:#3a140c;--ink:#fff6ec;--muted:#ffe7c2;",
  },
  {
    id: "australian",
    name: "澳网硬地",
    hint: "蓝色硬地",
    nav: "#0a3d86",
    front: "#ffffff",
    accent: "#7ee0ff",
    accentInk: "#042033",
    swatch: "linear-gradient(90deg,#0d4ea3 0%,#0d4ea3 42%,#1a6fd4 42%,#1a6fd4 58%,#0d4ea3 58%,#0d4ea3 100%)",
    vars: "--court-a:#0d4ea3;--court-b:#1a6fd4;--line:#c9f4ff;--accent:#7ee0ff;--accent-ink:#042033;--ink:#eef9ff;--muted:#c9f4ff;",
  },
  {
    id: "usopen",
    name: "美网夜场",
    hint: "深蓝夜场",
    nav: "#071428",
    front: "#ffffff",
    accent: "#f5c16c",
    accentInk: "#1a1206",
    swatch: "linear-gradient(90deg,#071833 0%,#071833 42%,#12305f 42%,#12305f 58%,#071833 58%,#071833 100%)",
    vars: "--court-a:#071833;--court-b:#12305f;--line:#d7e4ff;--accent:#f5c16c;--accent-ink:#1a1206;--ink:#f4f7ff;--muted:#d7e4ff;",
  },
];

function current() {
  var id = "";
  try {
    id = wx.getStorageSync(STORAGE_KEY) || "";
  } catch (e) {}
  for (var i = 0; i < THEMES.length; i++) {
    if (THEMES[i].id === id) return THEMES[i];
  }
  return THEMES[0];
}

function pageStyle(theme) {
  return (theme || current()).vars;
}

function applyNav(theme) {
  theme = theme || current();
  if (typeof wx.setNavigationBarColor !== "function") return;
  wx.setNavigationBarColor({
    backgroundColor: theme.nav,
    frontColor: theme.front || "#ffffff",
    animation: { duration: 0, timingFunc: "linear" },
  });
}

function setTheme(id) {
  try {
    wx.setStorageSync(STORAGE_KEY, id);
  } catch (e) {}
  var theme = current();
  applyNav(theme);
  return theme;
}

module.exports = {
  STORAGE_KEY: STORAGE_KEY,
  THEMES: THEMES,
  current: current,
  pageStyle: pageStyle,
  applyNav: applyNav,
  setTheme: setTheme,
};
