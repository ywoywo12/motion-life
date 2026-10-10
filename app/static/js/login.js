document.addEventListener("DOMContentLoaded", () => {
  const f = document.getElementById("login-form");
  f.addEventListener("submit", async ev => {
    ev.preventDefault();
    const box = f.querySelector(".form-errors");
    box.innerHTML = "";
    const btn = f.querySelector("button");
    btn.disabled = true;
    try {
      const res = await ML.api("POST", "/api/auth/login", { username: f.username.value.trim(), password: f.password.value });
      location.href = res.must_change_password ? "/account?first=1" : (f.dataset.next || "/dashboard");
    } catch (err) {
      box.innerHTML = ML.renderError(err);
      f.password.value = "";
      f.password.focus();
    } finally { btn.disabled = false; }
  });
});
