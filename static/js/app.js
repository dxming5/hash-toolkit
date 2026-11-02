/* Hash-Toolkit 前端：拉取算法目录 -> 动态渲染表单 -> 调用 API -> 展示结果 */

"use strict";

const nav = document.getElementById("nav");
const placeholder = document.getElementById("placeholder");
const workspace = document.getElementById("workspace");
const algName = document.getElementById("alg-name");
const algDesc = document.getElementById("alg-desc");
const algForm = document.getElementById("alg-form");
const resultBox = document.getElementById("result");

let currentAlg = null;
let fileStore = new Map(); // 文件名 -> 选中的 File 对象

/* ---------- 算法目录加载与导航渲染 ---------- */

async function loadCatalog() {
  const resp = await fetch("/api/algorithms");
  if (!resp.ok) {
    placeholder.textContent = "加载算法目录失败，请检查服务是否正常运行";
    return;
  }
  const data = await resp.json();
  nav.textContent = "";
  let firstAlg = null;
  for (const group of data.groups) {
    const groupEl = document.createElement("div");
    groupEl.className = "nav-group";
    const title = document.createElement("div");
    title.className = "nav-group-title";
    title.textContent = group.name;
    groupEl.appendChild(title);
    for (const alg of group.algorithms) {
      const btn = document.createElement("button");
      btn.className = "nav-item";
      btn.textContent = alg.name;
      btn.addEventListener("click", () => selectAlgorithm(alg, btn));
      groupEl.appendChild(btn);
      if (!firstAlg) firstAlg = { alg, btn };
    }
    nav.appendChild(groupEl);
  }
  if (firstAlg) selectAlgorithm(firstAlg.alg, firstAlg.btn);
}

/* ---------- 算法选择与动态表单 ---------- */

function selectAlgorithm(alg, btn) {
  currentAlg = alg;
  fileStore.clear();
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");

  algName.textContent = alg.name;
  algDesc.textContent = alg.description || "";
  algForm.textContent = "";
  resultBox.textContent = "";
  placeholder.hidden = true;
  workspace.hidden = false;

  for (const input of alg.inputs) {
    const field = document.createElement("div");
    field.className = "field";
    const label = document.createElement("label");
    label.className = "field-label";
    label.innerHTML = `${input.label}${input.required ? '<span class="req">*</span>' : ""}`;
    field.appendChild(label);
    field.appendChild(buildControl(input));
    algForm.appendChild(field);
  }

  const submit = document.createElement("button");
  submit.id = "submit-btn";
  submit.type = "submit";
  submit.textContent = "执行计算";
  algForm.appendChild(submit);

  algForm.onsubmit = onSubmit;
}

function buildControl(input) {
  switch (input.type) {
    case "file":
      return buildDropZone(input);
    case "select": {
      const sel = document.createElement("select");
      sel.name = input.name;
      for (const opt of input.options || []) {
        const o = document.createElement("option");
        o.value = opt.value;
        o.textContent = opt.label;
        if (opt.value === input.default) o.selected = true;
      }
      return sel;
    }
    case "number": {
      const num = document.createElement("input");
      num.type = "number";
      num.name = input.name;
      if (input.min !== null && input.min !== undefined) num.min = input.min;
      if (input.max !== null && input.max !== undefined) num.max = input.max;
      num.value = input.default ?? "";
      return num;
    }
    case "key": {
      const wrap = document.createElement("div");
      wrap.className = "key-wrap";
      const key = document.createElement("input");
      key.type = "password";
      key.name = input.name;
      key.placeholder = input.placeholder || "";
      key.autocomplete = "off";
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "key-toggle";
      toggle.textContent = "显示";
      toggle.addEventListener("click", () => {
        const show = key.type === "password";
        key.type = show ? "text" : "password";
        toggle.textContent = show ? "隐藏" : "显示";
      });
      wrap.appendChild(key);
      wrap.appendChild(toggle);
      return wrap;
    }
    default: { // text
      const ta = document.createElement("textarea");
      ta.name = input.name;
      ta.placeholder = input.placeholder || "";
      return ta;
    }
  }
}

function buildDropZone(input) {
  const zone = document.createElement("div");
  zone.className = "drop-zone";
  zone.textContent = "点击选择文件，或将文件拖拽到此处";
  const hidden = document.createElement("input");
  hidden.type = "file";
  hidden.name = input.name;
  hidden.addEventListener("change", () => {
    if (hidden.files.length) setFile(zone, input.name, hidden.files[0]);
  });
  zone.addEventListener("click", () => hidden.click());
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("dragover");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");
    if (e.dataTransfer.files.length) setFile(zone, input.name, e.dataTransfer.files[0]);
  });
  zone.appendChild(hidden);
  return zone;
}

function setFile(zone, name, file) {
  fileStore.set(name, file);
  zone.classList.add("has-file");
  const old = zone.querySelector(".file-name");
  if (old) zone.removeChild(old);
  const info = document.createElement("div");
  info.className = "file-name";
  info.textContent = `已选择：${file.name}（${formatSize(file.size)}）`;
  zone.appendChild(info);
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " MB";
  return (bytes / 1024 / 1024 / 1024).toFixed(2) + " GB";
}

/* ---------- 提交与结果渲染 ---------- */

async function onSubmit(e) {
  e.preventDefault();
  resultBox.textContent = "";
  const submitBtn = algForm.querySelector("#submit-btn");

  // 前端必填校验
  for (const input of currentAlg.inputs) {
    if (!input.required) continue;
    const ctrl = algForm.querySelector(`[name="${input.name}"]`);
    if (!ctrl || (ctrl.value.trim() === "" && !fileStore.has(input.name))) {
      showError(`请填写必填项：${input.label}`);
      return;
    }
  }

  const fd = new FormData();
  for (const input of currentAlg.inputs) {
    if (input.type === "file") {
      const f = fileStore.get(input.name);
      if (f) fd.append(input.name, f);
    } else {
      const ctrl = algForm.querySelector(`[name="${input.name}"]`);
      if (ctrl && ctrl.value !== "") fd.append(input.name, ctrl.value);
    }
  }

  submitBtn.disabled = true;
  submitBtn.textContent = "计算中...";
  const t0 = performance.now();
  try {
    const resp = await fetch(`/api/compute/${currentAlg.id}`, { method: "POST", body: fd });
    const data = await resp.json();
    const elapsed = ((performance.now() - t0) / 1000).toFixed(2);
    renderResult(data, elapsed);
  } catch (err) {
    showError(`请求失败：${err.message}`);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "执行计算";
  }
}

function renderResult(data, elapsed) {
  resultBox.textContent = "";
  if (data.error) {
    showError(data.error);
    return;
  }
  const meta = document.createElement("div");
  meta.className = "result-meta";
  meta.textContent = `计算完成，耗时 ${elapsed} 秒`;
  resultBox.appendChild(meta);
  for (const out of data.outputs || []) {
    resultBox.appendChild(buildResultCard(out));
  }
}

function buildResultCard(out) {
  const card = document.createElement("div");
  card.className = "result-card";
  const head = document.createElement("div");
  head.className = "result-card-head";
  const title = document.createElement("span");
  title.className = "result-card-title";
  title.textContent = out.label || "结果";
  head.appendChild(title);
  const actions = document.createElement("div");
  actions.className = "result-card-actions";
  const copyBtn = document.createElement("button");
  copyBtn.className = "action-btn";
  copyBtn.textContent = "复制";
  copyBtn.addEventListener("click", () => copyText(out.value, copyBtn));
  actions.appendChild(copyBtn);
  if (out.filename) {
    const dlBtn = document.createElement("button");
    dlBtn.className = "action-btn";
    dlBtn.textContent = "下载";
    dlBtn.addEventListener("click", () => downloadText(out.value, out.filename));
    actions.appendChild(dlBtn);
  }
  head.appendChild(actions);
  card.appendChild(head);
  const value = document.createElement("div");
  value.className = "result-value";
  value.textContent = out.value;
  card.appendChild(value);
  if (out.note) {
    const note = document.createElement("div");
    note.className = "result-note";
    note.textContent = out.note;
    card.appendChild(note);
  }
  return card;
}

function showError(msg) {
  const box = document.createElement("div");
  box.className = "error-box";
  box.textContent = msg;
  resultBox.textContent = "";
  resultBox.appendChild(box);
}

async function copyText(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
    const old = btn.textContent;
    btn.textContent = "已复制";
    setTimeout(() => (btn.textContent = old), 1500);
  } catch {
    btn.textContent = "复制失败";
  }
}

function downloadText(text, filename) {
  const blob = new Blob([text], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

loadCatalog();
