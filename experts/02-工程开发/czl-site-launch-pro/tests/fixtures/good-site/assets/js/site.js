(function () {
  var form = document.querySelector("form");
  if (!form) return;
  form.addEventListener("submit", function (event) {
    var phone = form.querySelector("#phone");
    if (!phone || phone.value.trim().length < 7) {
      event.preventDefault();
      phone.setAttribute("aria-invalid", "true");
      phone.focus();
    }
  });
})();
