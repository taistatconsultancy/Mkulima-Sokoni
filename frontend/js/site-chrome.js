(function () {
  var year = String(new Date().getFullYear());
  document.querySelectorAll('.yr, #yr').forEach(function (el) {
    el.textContent = year;
  });
})();
