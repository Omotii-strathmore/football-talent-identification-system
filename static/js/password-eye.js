/* Adds an eye button inside every password box to show or hide what was typed.
   Forms marked data-no-autofill also stop the browser from filling in saved logins on page load. */
(function () {
  var EYE = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  var EYE_OFF = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 19c-7 0-11-7-11-7a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 7 11 7a18.5 18.5 0 0 1-2.16 3.19"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';

  function addStyles() {
    if (document.getElementById('pw-eye-style')) return;
    var css = '.pw-eye-wrap{position:relative;display:block}' +
      '.pw-eye-wrap>input{padding-right:46px!important}' +
      '.pw-eye{position:absolute;top:50%;right:6px;transform:translateY(-50%);width:36px;height:36px;' +
      'display:flex;align-items:center;justify-content:center;border:0;border-radius:8px;background:transparent;' +
      'color:#5b6b62;cursor:pointer;padding:0}' +
      '.pw-eye:hover,.pw-eye:focus-visible{color:#006b3f;background:rgba(0,107,63,.08);outline:none}' +
      '.pw-eye[aria-pressed="true"]{color:#006b3f}';
    var style = document.createElement('style');
    style.id = 'pw-eye-style';
    style.textContent = css;
    document.head.appendChild(style);
  }

  function attach(input) {
    if (input.dataset.pwEye) return;
    input.dataset.pwEye = '1';
    var wrap = document.createElement('span');
    wrap.className = 'pw-eye-wrap';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pw-eye';
    btn.setAttribute('aria-label', 'Show password');
    btn.setAttribute('aria-pressed', 'false');
    btn.title = 'Show password';
    btn.innerHTML = EYE;
    btn.addEventListener('click', function () {
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.innerHTML = show ? EYE_OFF : EYE;
      btn.setAttribute('aria-pressed', show ? 'true' : 'false');
      btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
      btn.title = show ? 'Hide password' : 'Show password';
      input.focus();
    });
    wrap.appendChild(btn);
  }

  function blockAutofill(form) {
    form.setAttribute('autocomplete', 'off');
    var fields = form.querySelectorAll('input[type="email"], input[type="text"], input[type="password"]');
    Array.prototype.forEach.call(fields, function (field) {
      field.setAttribute('autocomplete', field.type === 'password' ? 'new-password' : 'off');
      // Browsers do not fill read-only boxes; unlock as soon as the person uses the box.
      field.setAttribute('readonly', 'readonly');
      var unlock = function () { field.removeAttribute('readonly'); };
      field.addEventListener('focus', unlock);
      field.addEventListener('pointerdown', unlock);
      field.addEventListener('touchstart', unlock, { passive: true });
    });
  }

  function init() {
    addStyles();
    Array.prototype.forEach.call(document.querySelectorAll('input[type="password"]'), attach);
    Array.prototype.forEach.call(document.querySelectorAll('form[data-no-autofill]'), blockAutofill);
  }

  // When a page comes back from the Back/Forward cache (for example after logging out), empty its password boxes.
  window.addEventListener('pageshow', function (event) {
    if (!event.persisted) return;
    Array.prototype.forEach.call(document.querySelectorAll('form[data-no-autofill]'), function (form) { form.reset(); });
    Array.prototype.forEach.call(document.querySelectorAll('.pw-eye-wrap > input'), function (input) {
      input.value = '';
      input.type = 'password';
      var btn = input.parentNode.querySelector('.pw-eye');
      if (btn) { btn.innerHTML = EYE; btn.setAttribute('aria-pressed', 'false'); btn.setAttribute('aria-label', 'Show password'); btn.title = 'Show password'; }
    });
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
