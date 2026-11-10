// Atajos para el DOM.
export const $ = id => document.getElementById(id);
export const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
