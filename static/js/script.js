// Highlights the drop area while a file is dragged over it. Uploading is handled by
// the page's own script (templates/index.html), so this file only does styling.
const dropArea = document.getElementById("drop-area");

["dragenter", "dragover"].forEach(eventName => {
  dropArea.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropArea.classList.add("border-blue-500", "bg-blue-50");
  });
});

["dragleave", "drop"].forEach(eventName => {
  dropArea.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropArea.classList.remove("border-blue-500", "bg-blue-50");
  });
});
