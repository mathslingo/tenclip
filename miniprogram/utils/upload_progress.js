function mapUploadProgressPercent(wxPct) {
  return Math.min(58, Math.max(22, 22 + Math.round((wxPct || 0) * 0.36)));
}

function compressProgressMessage(sizeBytes, simulatedPct) {
  var mb = sizeBytes ? (sizeBytes / (1024 * 1024)).toFixed(0) : "?";
  if (simulatedPct < 8) {
    return "正在读取并压缩视频（约 " + mb + " MB），请稍候…";
  }
  if (simulatedPct < 18) {
    return "压缩进行中（约 " + simulatedPct + "%），长视频可能需要 1～3 分钟…";
  }
  return "即将完成压缩（约 " + simulatedPct + "%），随后自动上传…";
}

function compressTickIntervalMs(sizeBytes) {
  var mb = sizeBytes / (1024 * 1024);
  if (mb >= 100) return 2200;
  if (mb >= 50) return 1800;
  if (mb >= 20) return 1400;
  return 1000;
}

module.exports = {
  mapUploadProgressPercent,
  compressProgressMessage,
  compressTickIntervalMs,
};
