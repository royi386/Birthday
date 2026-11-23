(function () {
  function fitFleetBoards() {
    var grids = document.querySelectorAll(".fleet-grid");
    for (var i = 0; i < grids.length; i++) {
      var grid = grids[i];
      var count = grid.children.length;
      if (!count) continue;
      var columns = getComputedStyle(grid).gridTemplateColumns.trim().split(/\s+/).length;
      var rows = Math.max(1, Math.ceil(count / Math.max(1, columns)));
      grid.style.setProperty("--fleet-rows", rows);
    }
  }

  window.addEventListener("resize", fitFleetBoards);
  if (window.MutationObserver) {
    new MutationObserver(fitFleetBoards).observe(document.getElementById("slides"), {
      childList: true,
      subtree: true,
    });
  }
  fitFleetBoards();
})();
