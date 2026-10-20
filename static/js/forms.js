"use strict";
// Native forms remain usable without JavaScript. Never show saved before a server response.
document.querySelectorAll("form[data-dirty-warning]").forEach((form) => {
  let dirty = false;
  const status = form.querySelector(".form-status");
  form.addEventListener("input", () => {
    dirty = true;
    if (status) status.textContent = "Unsaved changes";
  });
  form.addEventListener("submit", () => {
    dirty = false;
    if (status) status.textContent = "Saving…";
  });
  window.addEventListener("beforeunload", (event) => {
    if (dirty) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
});
