/* Neuro grid cells: each selection is saved immediately and its state is shown on the cell. */
document.addEventListener("change", async ev => {
  const el = ev.target;
  if (!el.matches("[data-exam-cell]") || !el.value) return;
  el.disabled = true;
  el.title = "جارٍ الحفظ…";
  try {
    await ML.api("POST", el.dataset.url, { test_code: el.dataset.test, side: el.dataset.side, result: "RECORDED", value_text: el.value,
      amend_reason: el.dataset.saved ? "تصحيح أثناء الفحص" : undefined });
    el.dataset.saved = "1";
    el.title = "حُفظ ✓";
    el.classList.remove("cell-failed");
  } catch (err) {
    el.title = "فشل الحفظ";
    el.classList.add("cell-failed");
    ML.toast("فشل حفظ الخلية: " + ((err.error && err.error.message) || ""), "danger");
  } finally { el.disabled = false; }
});
