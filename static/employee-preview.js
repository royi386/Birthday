(function () {
  var stage = document.getElementById("stage");
  if (!stage || !document.body.classList.contains("employee-preview")) return;

  var slides = Array.prototype.slice.call(document.querySelectorAll("[data-slide]"));
  var counter = document.getElementById("preview-count");
  var status = document.getElementById("alignment-status");
  var xControl = document.getElementById("align-x");
  var yControl = document.getElementById("align-y");
  var pending = {};
  var active = 0;
  var rotation = null;
  var dragging = null;

  function number(value) {
    var result = parseFloat(value);
    return isNaN(result) ? 50 : Math.max(0, Math.min(100, result));
  }

  function applyImage(image, x, y) {
    var moveX = ((50 - x) / 100) * image.clientWidth * 0.8;
    var moveY = ((50 - y) / 100) * image.clientHeight * 0.8;
    image.style.transform = "translate(" + moveX + "px, " + moveY + "px) scale(1.6)";
    image.style.objectPosition = x + "% " + y + "%";
    image.draggable = false;
    image.style.touchAction = "none";
    image.ondragstart = function () { return false; };
  }

  function paint(slide) {
    var x = number(slide.dataset.photoX);
    var y = number(slide.dataset.photoY);
    var workX = number(slide.dataset.workPhotoX);
    var workY = number(slide.dataset.workPhotoY);
    Array.prototype.forEach.call(slide.querySelectorAll(".portrait-image, .employee-photo img"), function (image) {
      applyImage(image, x, y);
    });
    Array.prototype.forEach.call(slide.querySelectorAll(".work-photo img"), function (image) {
      applyImage(image, workX, workY);
    });
  }

  function setPosition(slide, kind, x, y) {
    x = Math.round(Math.max(0, Math.min(100, x)));
    y = Math.round(Math.max(0, Math.min(100, y)));
    var isWorkPhoto = kind === "recognition";
    var prefix = isWorkPhoto ? "workPhoto" : "photo";
    slide.dataset[prefix + "X"] = x;
    slide.dataset[prefix + "Y"] = y;
    paint(slide);
    var id = isWorkPhoto ? slide.dataset.recognitionId : slide.dataset.photoId;
    if (!id || !kind) return;
    pending[kind + ":" + id] = { kind: kind, id: id, x: x, y: y };
    status.textContent = "Unsaved alignment";
    if (slide === slides[active] && !isWorkPhoto) {
      xControl.value = x;
      yControl.value = y;
    }
  }

  function show(index) {
    if (!slides.length) return;
    active = (index + slides.length) % slides.length;
    slides.forEach(function (slide, i) {
      slide.classList.toggle("current", i === active);
    });
    counter.textContent = (active + 1) + " / " + slides.length;
    xControl.value = number(slides[active].dataset.photoX);
    yControl.value = number(slides[active].dataset.photoY);
  }

  slides.forEach(function (slide) {
    paint(slide);
    slide.addEventListener("pointerdown", function (event) {
      var image = event.target.closest("img");
      if (!image) return;
      var workPhoto = !!image.closest(".work-photo");
      var employeePhoto = !!image.closest(".employee-photo") || image.classList.contains("portrait-image");
      if (!workPhoto && !employeePhoto) return;
      var kind = workPhoto ? "recognition" : slide.dataset.photoKind;
      if (!kind) return;
      event.preventDefault();
      window.clearInterval(rotation);
      dragging = {
        slide: slide,
        image: image,
        kind: kind,
        workPhoto: workPhoto,
        startX: event.clientX,
        startY: event.clientY,
        x: number(workPhoto ? slide.dataset.workPhotoX : slide.dataset.photoX),
        y: number(workPhoto ? slide.dataset.workPhotoY : slide.dataset.photoY),
        rangeX: Math.max(image.clientWidth * 0.8, 1),
        rangeY: Math.max(image.clientHeight * 0.8, 1)
      };
      if (image.setPointerCapture) image.setPointerCapture(event.pointerId);
    });
  });

  document.addEventListener("pointermove", function (event) {
    if (!dragging) return;
    setPosition(
      dragging.slide,
      dragging.kind,
      dragging.x - ((event.clientX - dragging.startX) / dragging.rangeX) * 100,
      dragging.y - ((event.clientY - dragging.startY) / dragging.rangeY) * 100
    );
  });
  document.addEventListener("pointerup", function () { dragging = null; });
  document.addEventListener("pointercancel", function () { dragging = null; });

  function adjustFromSliders() {
    window.clearInterval(rotation);
    var slide = slides[active];
    if (slide.dataset.photoKind) setPosition(slide, slide.dataset.photoKind, number(xControl.value), number(yControl.value));
  }

  xControl.addEventListener("input", adjustFromSliders);
  yControl.addEventListener("input", adjustFromSliders);
  document.getElementById("preview-prev").addEventListener("click", function () { window.clearInterval(rotation); show(active - 1); });
  document.getElementById("preview-next").addEventListener("click", function () { window.clearInterval(rotation); show(active + 1); });
  document.addEventListener("keydown", function (event) {
    if (event.key === "ArrowLeft") { window.clearInterval(rotation); show(active - 1); }
    if (event.key === "ArrowRight") { window.clearInterval(rotation); show(active + 1); }
  });

  document.getElementById("save-photo-alignment").addEventListener("click", function () {
    var updates = Object.keys(pending).map(function (key) { return pending[key]; });
    if (!updates.length) { status.textContent = "No alignment changes"; return; }
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
      status.textContent = "Alignment saved";
    }).catch(function () {
      status.textContent = "Could not save alignment";
    });
  });

  show(0);
  rotation = window.setInterval(function () { show(active + 1); }, 8000);
})();
