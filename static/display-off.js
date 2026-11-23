(function () {
  var stage = document.getElementById("stage");
  var clock = document.getElementById("display-off-clock");
  if (!stage || !clock) return;
  var timeNode = clock.querySelector(".display-off-time");
  var dateNode = clock.querySelector(".display-off-date");

  var formatter;
  var dateFormatter;
  var zone = "";
  var boundaryTimer = null;

  function updateClock() {
    var configuredZone = stage.getAttribute("data-timezone") || "Asia/Kolkata";
    if (configuredZone !== zone) {
      zone = configuredZone;
      try {
        formatter = new Intl.DateTimeFormat("en-GB", {
          timeZone: zone, hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
        });
        dateFormatter = new Intl.DateTimeFormat("en-GB", {
          timeZone: zone, weekday: "short", day: "2-digit", month: "short", year: "numeric",
        });
      } catch (_error) {
        formatter = null;
        dateFormatter = null;
      }
    }
    var now = new Date();
    var timeText = formatter ? formatter.format(now) : now.toLocaleTimeString();
    var dateText = dateFormatter ? dateFormatter.format(now) : now.toLocaleDateString();
    timeNode.textContent = timeText;
    dateNode.textContent = dateText;
  }

  function moveClock() {
    if (stage.getAttribute("data-display-off") !== "true") return;
    var margin = 24;
    var width = clock.offsetWidth;
    var height = clock.offsetHeight;
    var maxX = Math.max(margin, stage.clientWidth - width - margin);
    var maxY = Math.max(margin, stage.clientHeight - height - margin);
    clock.style.left = Math.round(margin + Math.random() * (maxX - margin)) + "px";
    clock.style.top = Math.round(margin + Math.random() * (maxY - margin)) + "px";
  }


  function scheduleBoundaryRefresh() {
    if (boundaryTimer) window.clearTimeout(boundaryTimer);
    boundaryTimer = null;
    var target = Date.parse(stage.getAttribute("data-next-display-off-change") || "");
    if (!isFinite(target)) return;
    var delay = target - Date.now();
    if (delay < 0) return;
    boundaryTimer = window.setTimeout(function () {
      var event = document.createEvent("Event");
      event.initEvent("display-schedule-boundary", true, true);
      window.dispatchEvent(event);
    }, delay + 150);
  }
  updateClock();
  moveClock();
  window.setInterval(updateClock, 1000);
  window.setInterval(moveClock, 20000);
  window.addEventListener("resize", moveClock);
  window.addEventListener("display-schedule-boundary", scheduleBoundaryRefresh);
  scheduleBoundaryRefresh();
  if (window.MutationObserver) {
    new MutationObserver(function () { moveClock(); scheduleBoundaryRefresh(); }).observe(stage, { attributes: true, attributeFilter: ["data-display-off", "data-next-display-off-change"] });
  }
})();
