(() => {
  if (window.SokoUI) return;

  const styleId = 'soko-ui-feedback-style';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .soko-ui-overlay{position:fixed;inset:0;background:rgba(8,15,24,.56);display:none;align-items:center;justify-content:center;z-index:12000;padding:16px}
      .soko-ui-overlay.active{display:flex}
      .soko-ui-modal{width:min(520px,96vw);background:#101722;border:1px solid rgba(149,184,255,.26);border-radius:16px;box-shadow:0 22px 56px rgba(0,0,0,.42);color:#f4f7ff;padding:20px}
      .soko-ui-title{font-size:1.15rem;font-weight:800;margin:0 0 8px}
      .soko-ui-body{font-size:.95rem;line-height:1.52;color:#dce6ff;margin-bottom:14px;white-space:pre-wrap}
      .soko-ui-field{display:flex;flex-direction:column;gap:6px;margin-bottom:12px}
      .soko-ui-field label{font-size:.85rem;color:#b8cbff}
      .soko-ui-field input,.soko-ui-field textarea,.soko-ui-field select{background:#0a111b;border:1px solid #95b8ff;border-radius:10px;color:#fff;padding:10px 12px;font-size:.94rem}
      .soko-ui-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:8px}
      .soko-ui-btn{border:none;border-radius:999px;padding:10px 16px;font-weight:700;font-size:.9rem;cursor:pointer}
      .soko-ui-btn.primary{background:#95b8ff;color:#0b1d3d}
      .soko-ui-btn.secondary{background:#24539a;color:#dce8ff}
      .soko-ui-btn.danger{background:#dc4857;color:#fff}
      .soko-ui-toast-wrap{position:fixed;top:18px;right:18px;z-index:12100;display:flex;flex-direction:column;gap:10px}
      .soko-ui-toast{background:#111b2a;color:#e9f0ff;border:1px solid rgba(149,184,255,.3);border-radius:12px;padding:10px 13px;min-width:230px;max-width:360px;box-shadow:0 10px 30px rgba(0,0,0,.35)}
      .soko-ui-toast.success{border-color:rgba(76,211,149,.5)}
      .soko-ui-toast.error{border-color:rgba(245,96,115,.55)}
      .soko-ui-btn[disabled]{opacity:.7;cursor:not-allowed}
    `;
    document.head.appendChild(style);
  }

  function ensureOverlay() {
    let overlay = document.getElementById('sokoUiOverlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'soko-ui-overlay';
      overlay.id = 'sokoUiOverlay';
      overlay.innerHTML = '<div class="soko-ui-modal" role="dialog" aria-modal="true"></div>';
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay && overlay.dataset.allowBackdropClose === '1') {
          closeModal(null);
        }
      });
      document.body.appendChild(overlay);
    }
    return overlay;
  }

  function ensureToastWrap() {
    let wrap = document.getElementById('sokoUiToastWrap');
    if (!wrap) {
      wrap = document.createElement('div');
      wrap.id = 'sokoUiToastWrap';
      wrap.className = 'soko-ui-toast-wrap';
      document.body.appendChild(wrap);
    }
    return wrap;
  }

  let resolver = null;
  let escHandlerBound = false;

  function closeModal(value) {
    const overlay = ensureOverlay();
    overlay.classList.remove('active');
    overlay.dataset.allowBackdropClose = '0';
    document.body.style.overflow = '';
    const r = resolver;
    resolver = null;
    if (r) r(value);
  }

  function bindEsc() {
    if (escHandlerBound) return;
    escHandlerBound = true;
    document.addEventListener('keydown', (e) => {
      const overlay = document.getElementById('sokoUiOverlay');
      if (!overlay || !overlay.classList.contains('active')) return;
      if (e.key === 'Escape' && overlay.dataset.allowEscapeClose === '1') {
        closeModal(false);
      }
    });
  }

  function openDialog({ title, message, fields = [], variant = 'info', confirmText = 'OK', cancelText = null, allowClose = true }) {
    bindEsc();
    const overlay = ensureOverlay();
    const modal = overlay.querySelector('.soko-ui-modal');
    overlay.dataset.allowBackdropClose = allowClose ? '1' : '0';
    overlay.dataset.allowEscapeClose = allowClose ? '1' : '0';

    const fieldsHtml = fields.map((f, i) => {
      const id = `soko-ui-field-${i}`;
      const type = f.type || 'text';
      const common = `id="${id}" ${f.required ? 'required' : ''} ${f.placeholder ? `placeholder="${String(f.placeholder).replace(/"/g, '&quot;')}"` : ''}`;
      let input = `<input type="${type}" ${common} value="${f.value == null ? '' : String(f.value).replace(/"/g, '&quot;')}" />`;
      if (type === 'textarea') input = `<textarea ${common}>${f.value == null ? '' : String(f.value)}</textarea>`;
      if (type === 'select') {
        const opts = (f.options || []).map((o) => `<option value="${String(o.value).replace(/"/g, '&quot;')}" ${o.value === f.value ? 'selected' : ''}>${String(o.label)}</option>`).join('');
        input = `<select ${common}>${opts}</select>`;
      }
      return `<div class="soko-ui-field"><label for="${id}">${f.label || ''}</label>${input}</div>`;
    }).join('');

    modal.innerHTML = `
      <h3 class="soko-ui-title">${title || ''}</h3>
      <div class="soko-ui-body">${message || ''}</div>
      ${fieldsHtml}
      <div class="soko-ui-actions">
        ${cancelText ? `<button class="soko-ui-btn secondary" data-action="cancel">${cancelText}</button>` : ''}
        <button class="soko-ui-btn ${variant === 'danger' ? 'danger' : 'primary'}" data-action="confirm">${confirmText}</button>
      </div>
    `;

    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
    const firstInput = modal.querySelector('input, textarea, select');
    (firstInput || modal.querySelector('[data-action="confirm"]'))?.focus();

    return new Promise((resolve) => {
      resolver = resolve;
      modal.querySelector('[data-action="confirm"]')?.addEventListener('click', () => {
        if (!fields.length) return closeModal(true);
        const values = {};
        for (let i = 0; i < fields.length; i++) {
          const field = fields[i];
          const el = modal.querySelector(`#soko-ui-field-${i}`);
          const raw = el ? el.value : '';
          if (field.required && !String(raw || '').trim()) {
            el?.focus();
            return;
          }
          values[field.key || `field${i}`] = raw;
        }
        closeModal(values);
      });
      modal.querySelector('[data-action="cancel"]')?.addEventListener('click', () => closeModal(false));
    });
  }

  const SokoUI = {
    toast(message, type = 'success', timeoutMs = 2600) {
      const wrap = ensureToastWrap();
      const el = document.createElement('div');
      el.className = `soko-ui-toast ${type}`;
      el.textContent = message;
      wrap.appendChild(el);
      window.setTimeout(() => {
        el.remove();
      }, timeoutMs);
    },
    async alert(message, title = 'Notice') {
      await openDialog({ title, message, confirmText: 'OK', allowClose: true });
      return true;
    },
    async confirm(message, title = 'Confirm', options = {}) {
      const result = await openDialog({
        title,
        message,
        variant: options.danger ? 'danger' : 'info',
        confirmText: options.confirmText || 'OK',
        cancelText: options.cancelText || 'Cancel',
        allowClose: true,
      });
      return !!result;
    },
    async prompt({ title = 'Input', message = '', fields = [], confirmText = 'Save', cancelText = 'Cancel' }) {
      const result = await openDialog({
        title,
        message,
        fields,
        confirmText,
        cancelText,
        allowClose: true,
      });
      return result || null;
    },
    withButtonLoading(buttonEl, loadingText, fn) {
      return async (...args) => {
        if (!buttonEl) return fn(...args);
        if (buttonEl.dataset.loading === '1') return;
        const previousText = buttonEl.textContent;
        buttonEl.dataset.loading = '1';
        buttonEl.disabled = true;
        if (loadingText) buttonEl.textContent = loadingText;
        try {
          return await fn(...args);
        } finally {
          buttonEl.dataset.loading = '0';
          buttonEl.disabled = false;
          buttonEl.textContent = previousText;
        }
      };
    },
  };

  window.SokoUI = SokoUI;
})();
