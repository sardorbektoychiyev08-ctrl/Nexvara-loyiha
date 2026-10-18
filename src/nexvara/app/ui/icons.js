"use strict";

// One stroke vocabulary for the sidebar and the drawing toolbar.
const UI_ICON_PATHS = {
  home: "<path d='m3 10 9-7 9 7v10H3z'/><path d='M9 20v-7h6v7'/>",
  chat: "<path d='M4 4h16v12H8l-4 4z'/><path d='M8 9h8M8 12h5'/>",
  office: "<rect x='4' y='3' width='16' height='18' rx='2'/><path d='M8 8h8M8 12h8M8 16h5'/>",
  library: "<path d='M4 4h7a3 3 0 0 1 3 3v14a3 3 0 0 0-3-3H4zM20 4h-3a3 3 0 0 0-3 3v14a3 3 0 0 1 3-3h3z'/>",
  files: "<path d='M3 7V5h7l2 2h9v12H3z'/>",
  bi: "<path d='M3 20h18M6 16v-5M12 16V4M18 16V8'/>",
  cad: "<path d='M3 19 19 3l2 2L5 21zM10 12l2 2M14 8l2 2'/>",
  workflows: "<rect x='3' y='3' width='6' height='5' rx='1'/><rect x='15' y='16' width='6' height='5' rx='1'/><path d='M6 8v10h9M18 16V7H9'/>",
  teach: "<path d='M12 3 3 8l9 5 9-5zM6 11v6c4 3 8 3 12 0v-6M21 8v7'/>",
  memory: "<path d='M9 4a4 4 0 0 0-5 5 4 4 0 0 0 0 6 4 4 0 0 0 5 5M15 4a4 4 0 0 1 5 5 4 4 0 0 1 0 6 4 4 0 0 1-5 5M9 4v16M15 4v16M9 10h6M9 15h6'/>",
  history: "<path d='M3 12a9 9 0 1 0 3-7M3 4v4h4M12 7v5l4 3'/>",
  devices: "<rect x='3' y='4' width='13' height='12' rx='2'/><path d='M6 20h7M9 16v4'/><rect x='17' y='8' width='4' height='11' rx='1'/>",
  settings: "<circle cx='12' cy='12' r='3'/><path d='M10 2h4l1 3 3 1 3-1 2 4-2 2v2l2 2-2 4-3-1-3 1-1 3h-4l-1-3-3-1-3 1-2-4 2-2v-2L1 9l2-4 3 1 3-1z'/>",
  new: "<path d='M12 4v16M4 12h16'/>",
  open: "<path d='M3 7V5h7l2 2h9v12H3zM12 16l4-4 4 4M16 12v7'/>",
  last: "<path d='M3 12a9 9 0 1 0 3-7M3 4v4h4M12 7v5l4 3'/>",
  save: "<path d='M4 3h14l3 3v15H3V3zM7 3v6h10V3M7 21v-8h10v8'/>",
  saveas: "<path d='M4 3h14l3 3v15H3V3zM7 3v6h10V3M7 21v-8h10v8M11 17h3'/>",
  pdf: "<path d='M6 2h9l4 4v16H6zM15 2v5h4M9 14h6M9 17h5'/>",
  png: "<rect x='3' y='3' width='18' height='18' rx='2'/><circle cx='8' cy='9' r='2'/><path d='m4 18 5-5 3 3 3-4 5 6'/>",
  line: "<path d='M4 19 20 5'/><circle cx='4' cy='19' r='2'/><circle cx='20' cy='5' r='2'/>",
  polyline: "<path d='m3 19 7-12 5 6 6-9'/><circle cx='10' cy='7' r='1'/>",
  rect: "<rect x='4' y='5' width='16' height='14'/>",
  circle: "<circle cx='12' cy='12' r='8'/>",
  arc: "<path d='M4 18a8 8 0 0 1 15-8'/><circle cx='4' cy='18' r='1'/><circle cx='19' cy='10' r='1'/>",
  text: "<path d='M4 6V4h16v2M12 4v16M8 20h8'/>",
  dim: "<path d='M4 5v14M20 5v14M5 12h14m-11-3-3 3 3 3m8-6 3 3-3 3'/>",
  select: "<path d='M4 3v17l5-5 4 6 3-2-4-6 7-1z'/>",
  move: "<path d='M12 2v20M2 12h20m-13-7 3-3 3 3m-6 14 3 3 3-3M5 9l-3 3 3 3m14-6 3 3-3 3'/>",
  copy: "<rect x='7' y='7' width='13' height='13' rx='2'/><path d='M4 16H3V4h13v1'/>",
  rotate: "<path d='M4 12a8 8 0 1 0 3-6M4 3v4h4M12 8v4l3 2'/>",
  mirror: "<path d='M12 2v20M9 5 3 12l6 7M15 5l6 7-6 7'/>",
  offset: "<path d='M4 19 14 5M10 20 20 6'/>",
  erase: "<path d='m4 16 9-12 8 6-9 11H8zM8 21h13'/>",
  undo: "<path d='M9 7 4 12l5 5M4 12h10a6 6 0 0 1 6 6'/>",
  redo: "<path d='m15 7 5 5-5 5m5-5H10a6 6 0 0 0-6 6'/>",
  extents: "<path d='M9 3H3v6m12-6h6v6M3 15v6h6m12-6v6h-6M8 12h8'/>",
  measure: "<path d='M3 17 17 3l4 4L7 21zM9 14l2 2M12 11l2 2M15 8l2 2'/>",
};
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".nav-item, #cad-toolbar .cad-btn").forEach((button) => {
    const name = button.dataset.page || button.dataset.tool || button.dataset.cad;
    const path = UI_ICON_PATHS[name];
    if (!path) return;
    const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("viewBox", "0 0 24 24"); icon.setAttribute("aria-hidden", "true");
    icon.setAttribute("class", "ui-icon"); icon.innerHTML = path;
    button.prepend(icon);
  });
});
