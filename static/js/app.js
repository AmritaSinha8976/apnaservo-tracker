(function () {
  var c = document.getElementById("clock");
  if (c) { var t = function () { c.textContent = new Date().toLocaleTimeString("en-IN", {hour: "2-digit", minute: "2-digit", second: "2-digit"}); }; t(); setInterval(t, 1000); }
  var open = document.getElementById("endBtn"), dlg = document.getElementById("confirmEnd");
  if (open && dlg) {
    open.addEventListener("click", function () {
      var f = document.getElementById("reportForm");
      if (f.reportValidity()) dlg.showModal();
    });
    document.getElementById("cancelEnd").addEventListener("click", function () { dlg.close(); });
  }
})();
