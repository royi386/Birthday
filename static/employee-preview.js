(function () {
  var stage = document.getElementById("stage");
  if (!stage || !document.body.classList.contains("employee-preview")) return;

  var slides = Array.prototype.slice.call(document.querySelectorAll("[data-slide]"));
  var counter = document.getElementById("preview-count");
  var status = document.getElementById("alignment-status");
  var zoomLevel = document.getElementById("zoom-level");
  var targetControl = document.getElementById("adjust-target");
  var pending = {};
  var active = 0;
  var rotation = null;
  var dragging = null;

  function number(value, fallback) {
    var result = parseFloat(value);
    return isNaN(result) ? (fallback === undefined ? 50 : fallback) : result;
  }

  function bounded(value, low, high) {
    return Math.max(low, Math.min(high, value));
  }

  function selectedKind(slide) {
    if (targetControl.value === "recognition" && slide.dataset.hasWorkPhoto === "true") return "recognition";
    return slide.dataset.photoKind;
  }

  function coords(slide, kind) {
    var work = kind === "recognition";
    return {
      x: number(work ? slide.dataset.workPhotoX : slide.dataset.photoX),
      y: number(work ? slide.dataset.workPhotoY : slide.dataset.photoY),
      zoom: number(work ? slide.dataset.workPhotoZoom : slide.dataset.photoZoom, 160)
    };
  }

  function applyImage(image, x, y, zoom, fitPortrait) {
    if (image.classList.contains("portrait-image") && !image.parentElement.classList.contains("photo-window")) {
      var window = document.createElement("div");
      window.className = "photo-window";
      image.parentNode.insertBefore(window, image);
      window.appendChild(image);
    }
    var zoomScale = zoom / 100;
    var naturalWidth = image.naturalWidth || image.clientWidth || 1;
    var naturalHeight = image.naturalHeight || image.clientHeight || 1;
    var frameWidth = image.clientWidth || 1;
    var frameHeight = image.clientHeight || 1;
    var coverScale = Math.max(frameWidth / naturalWidth, frameHeight / naturalHeight);
    var containScale = Math.min(frameWidth / naturalWidth, frameHeight / naturalHeight);
    var scale = zoomScale * (fitPortrait ? coverScale / containScale : 1);
    var renderedScale = containScale * scale;
    var overflowX = Math.max(0, naturalWidth * renderedScale - frameWidth);
    var overflowY = Math.max(0, naturalHeight * renderedScale - frameHeight);
    var moveX = ((50 - x) / 100) * overflowX;
    var moveY = ((50 - y) / 100) * overflowY;
    image.style.transform = "translate(" + moveX + "px, " + moveY + "px) scale(" + scale + ")";
    image.style.objectFit = "contain";
    image.style.objectPosition = fitPortrait ? "50% 50%" : x + "% " + y + "%";
    if (fitPortrait) image.style.background = "transparent";
    image.draggable = false;
    image.style.pointerEvents = "none";
    image.style.touchAction = "none";
    image.ondragstart = function () { return false; };
    if (!image.dataset.zoomLoadBound) {
      image.dataset.zoomLoadBound = "true";
      image.addEventListener("load", function () {
        var slide = image.closest("[data-slide]");
        if (slide) paint(slide);
      }, { once: true });
    }
  }

  function paint(slide) {
    var profile = coords(slide, "employee");
    var work = coords(slide, "recognition");
    Array.prototype.forEach.call(slide.querySelectorAll(".portrait-image, .employee-photo img"), function (image) {
      applyImage(image, profile.x, profile.y, profile.zoom, true);
    });
    Array.prototype.forEach.call(slide.querySelectorAll(".work-photo img"), function (image) {
      applyImage(image, work.x, work.y, work.zoom, false);
    });
  }

  function savePending(slide, kind) {
    var work = kind === "recognition";
    var values = coords(slide, kind);
    var id = work ? slide.dataset.recognitionId : slide.dataset.photoId;
    if (!id || !kind) return;
    pending[kind + ":" + id] = { kind: kind, id: id, x: values.x, y: values.y, zoom: values.zoom };
    status.textContent = "Unsaved photo adjustments";
  }

  function setPosition(slide, kind, x, y) {
    x = Math.round(bounded(x, 0, 100));
    y = Math.round(bounded(y, 0, 100));
    var work = kind === "recognition";
    var prefix = work ? "workPhoto" : "photo";
    slide.dataset[prefix + "X"] = x;
    slide.dataset[prefix + "Y"] = y;
    paint(slide);
    savePending(slide, kind);
  }

  function setZoom(slide, kind, zoom) {
    zoom = Math.round(bounded(zoom, 25, 300));
    var work = kind === "recognition";
    slide.dataset[work ? "workPhotoZoom" : "photoZoom"] = zoom;
    paint(slide);
    savePending(slide, kind);
    if (slide === slides[active] && kind === selectedKind(slide)) zoomLevel.textContent = zoom + "%";
  }

  function updateControls() {
    var slide = slides[active];
    if (!slide) return;
    var hasWork = slide.dataset.hasWorkPhoto === "true";
    targetControl.querySelector('option[value="recognition"]').hidden = !hasWork;
    if (!hasWork) targetControl.value = "employee";
    var values = coords(slide, selectedKind(slide));
    zoomLevel.textContent = values.zoom + "%";
  }

  function show(index) {
    if (!slides.length) return;
    active = (index + slides.length) % slides.length;
    slides.forEach(function (slide, i) {
      slide.classList.toggle("current", i === active);
    });
    counter.textContent = (active + 1) + " / " + slides.length;
    targetControl.value = "employee";
    updateControls();
  }

  slides.forEach(paint);

  function startDrag(event) {
    if ((event.type === "pointerdown" && event.pointerType === "mouse") || dragging) return;
    var slide = event.target.closest("[data-slide]");
    if (!slide || slide !== slides[active]) return;
    var image = event.target.closest("img.portrait-image, .employee-photo img, .work-photo img");
    if (!image) {
      var photoFrame = event.target.closest(".visual, .employee-photo, .work-photo");
      if (photoFrame) image = photoFrame.querySelector("img.portrait-image, .employee-photo img, .work-photo img");
    }
    if (!image) return;

    var workPhoto = !!image.closest(".work-photo");
    var kind = workPhoto ? "recognition" : slide.dataset.photoKind;
    if (!kind) return;
    targetControl.value = workPhoto ? "recognition" : "employee";
    updateControls();
    event.preventDefault();
    window.clearInterval(rotation);

    var current = coords(slide, kind);
    var naturalWidth = image.naturalWidth || image.clientWidth || 1;
    var naturalHeight = image.naturalHeight || image.clientHeight || 1;
    var frameWidth = image.clientWidth || 1;
    var frameHeight = image.clientHeight || 1;
    var coverScale = Math.max(frameWidth / naturalWidth, frameHeight / naturalHeight);
    var containScale = Math.min(frameWidth / naturalWidth, frameHeight / naturalHeight);
    var fitPortrait = !workPhoto;
    var zoomScale = current.zoom / 100;
    var renderedScale = containScale * zoomScale * (fitPortrait ? coverScale / containScale : 1);
    dragging = {
      slide: slide,
      kind: kind,
      startX: event.clientX,
      startY: event.clientY,
      x: current.x,
      y: current.y,
      rangeX: Math.max(naturalWidth * renderedScale - frameWidth, 1),
      rangeY: Math.max(naturalHeight * renderedScale - frameHeight, 1)
    };
  }

  document.addEventListener("pointerdown", startDrag);
  document.addEventListener("mousedown", startDrag);

  function movePhoto(event) {
    if (!dragging) return;
    setPosition(
      dragging.slide,
      dragging.kind,
      dragging.x - ((event.clientX - dragging.startX) / dragging.rangeX) * 100,
      dragging.y - ((event.clientY - dragging.startY) / dragging.rangeY) * 100
    );
  }
  document.addEventListener("pointermove", function (event) {
    if (event.pointerType !== "mouse") movePhoto(event);
  });
  document.addEventListener("mousemove", movePhoto);
  document.addEventListener("pointerup", function (event) {
    if (event.pointerType !== "mouse") dragging = null;
  });
  document.addEventListener("pointercancel", function () { dragging = null; });
  document.addEventListener("mouseup", function () { dragging = null; });

  targetControl.addEventListener("change", updateControls);
  document.getElementById("zoom-out").addEventListener("click", function () {
    var slide = slides[active];
    var values = coords(slide, selectedKind(slide));
    setZoom(slide, selectedKind(slide), values.zoom - 10);
  });
  document.getElementById("zoom-in").addEventListener("click", function () {
    var slide = slides[active];
    var values = coords(slide, selectedKind(slide));
    setZoom(slide, selectedKind(slide), values.zoom + 10);
  });
  document.getElementById("preview-prev").addEventListener("click", function () { window.clearInterval(rotation); show(active - 1); });
  document.getElementById("preview-next").addEventListener("click", function () { window.clearInterval(rotation); show(active + 1); });
  document.addEventListener("keydown", function (event) {
    if (event.key === "ArrowLeft") { window.clearInterval(rotation); show(active - 1); }
    if (event.key === "ArrowRight") { window.clearInterval(rotation); show(active + 1); }
  });

  document.getElementById("save-photo-alignment").addEventListener("click", function () {
    var updates = Object.keys(pending).map(function (key) { return pending[key]; });
    if (!updates.length) { status.textContent = "No photo adjustments to save"; return; }
    var csrf = document.querySelector("#alignment-form [name=csrfmiddlewaretoken]").value;
    var body = new URLSearchParams();
    body.set("csrfmiddlewaretoken", csrf);
    body.set("alignments", JSON.stringify(updates));
    fetch(stage.dataset.photoAlignmentUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": csrf },
      body: body.toString()
    }).then(function (response) {
      if (!response.ok) throw new Error("Save failed");
      return response.json();
    }).then(function () {
      pending = {};
      status.textContent = "Photo adjustments saved";
    }).catch(function () {
      status.textContent = "Could not save photo adjustments";
    });
  });

  show(0);
  rotation = window.setInterval(function () { show(active + 1); }, 8000);
})();
