(function () {
  if (window.SokoSupportCenter) {
    return;
  }

  var SUPPORT_API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:5000/api/support'
    : '/api/support';

  var CATEGORY_OPTIONS = [
    ['account', 'Account'],
    ['orders', 'Orders'],
    ['payments', 'Payments'],
    ['products', 'Products'],
    ['delivery', 'Delivery'],
    ['verification', 'Verification'],
    ['technical', 'Technical'],
    ['other', 'Other']
  ];

  var PRIORITY_OPTIONS = [
    ['low', 'Low'],
    ['medium', 'Medium'],
    ['high', 'High'],
    ['urgent', 'Urgent']
  ];

  var STATUS_LABELS = {
    open: 'Open',
    in_progress: 'In Progress',
    waiting_for_user: 'Waiting for User',
    resolved: 'Resolved',
    closed: 'Closed'
  };

  function injectStyles() {
    if (document.getElementById('support-center-styles')) {
      return;
    }

    var style = document.createElement('style');
    style.id = 'support-center-styles';
    style.textContent = [
      '.ssc-grid{display:grid;grid-template-columns:1.2fr 1fr;gap:18px;}',
      '.ssc-card{background:#fff;border:1.5px solid var(--border, #DDD8CE);border-radius:16px;padding:20px;box-shadow:0 2px 12px rgba(27,67,50,.06);}',
      '.ssc-title{font-family:"Playfair Display",serif;font-size:1.12rem;font-weight:700;color:var(--forest, #1B4332);margin-bottom:6px;}',
      '.ssc-sub{font-size:.82rem;color:var(--muted, #6B705C);margin-bottom:16px;}',
      '.ssc-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:16px;}',
      '.ssc-stat{background:var(--cream, #FAF6EF);border:1px solid var(--border, #DDD8CE);border-radius:12px;padding:14px;}',
      '.ssc-stat-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted, #6B705C);font-weight:700;margin-bottom:4px;}',
      '.ssc-stat-value{font-family:"Playfair Display",serif;font-size:1.4rem;font-weight:700;color:var(--forest, #1B4332);}',
      '.ssc-form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;}',
      '.ssc-form-full{grid-column:1 / -1;}',
      '.ssc-field{display:flex;flex-direction:column;gap:6px;}',
      '.ssc-field label{font-size:.78rem;font-weight:600;color:var(--ink, #1A1A18);}',
      '.ssc-field input,.ssc-field select,.ssc-field textarea{width:100%;padding:10px 12px;border:1.5px solid var(--border, #DDD8CE);border-radius:10px;background:var(--cream, #FAF6EF);font-family:"DM Sans",sans-serif;font-size:.86rem;outline:none;transition:all .2s;}',
      '.ssc-field input:focus,.ssc-field select:focus,.ssc-field textarea:focus{border-color:var(--leaf, #40916C);background:#fff;box-shadow:0 0 0 3px rgba(64,145,108,.1);}',
      '.ssc-field textarea{min-height:110px;resize:vertical;}',
      '.ssc-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:14px;}',
      '.ssc-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;border:none;border-radius:999px;padding:10px 16px;font-size:.8rem;font-weight:700;cursor:pointer;font-family:"DM Sans",sans-serif;transition:all .2s;}',
      '.ssc-btn:hover{transform:translateY(-1px);}',
      '.ssc-btn:disabled{opacity:.6;cursor:not-allowed;transform:none;}',
      '.ssc-btn-primary{background:linear-gradient(135deg, var(--forest, #1B4332), var(--leaf, #40916C));color:#fff;}',
      '.ssc-btn-outline{background:transparent;border:1.5px solid var(--leaf, #40916C);color:var(--leaf, #40916C);}',
      '.ssc-btn-muted{background:var(--cream, #FAF6EF);border:1px solid var(--border, #DDD8CE);color:var(--ink, #1A1A18);}',
      '.ssc-btn-danger{background:#fee2e2;color:#991b1b;}',
      '.ssc-alert{display:none;padding:12px 14px;border-radius:12px;font-size:.82rem;font-weight:600;margin-bottom:14px;}',
      '.ssc-alert.show{display:block;}',
      '.ssc-alert-success{background:#d1fae5;color:#065f46;border:1px solid #6ee7b7;}',
      '.ssc-alert-error{background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;}',
      '.ssc-toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:16px;}',
      '.ssc-toolbar .ssc-field{min-width:160px;flex:1;}',
      '.ssc-list{display:flex;flex-direction:column;gap:12px;}',
      '.ssc-ticket{border:1px solid var(--border, #DDD8CE);border-radius:14px;padding:16px;background:#fff;}',
      '.ssc-ticket-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap;margin-bottom:8px;}',
      '.ssc-ticket-title{font-weight:700;color:var(--ink, #1A1A18);font-size:.92rem;}',
      '.ssc-ticket-meta{font-size:.76rem;color:var(--muted, #6B705C);display:flex;gap:8px;flex-wrap:wrap;}',
      '.ssc-ticket-body{font-size:.82rem;color:var(--muted, #6B705C);margin:8px 0 12px;line-height:1.55;}',
      '.ssc-pill{display:inline-flex;align-items:center;padding:4px 10px;border-radius:999px;font-size:.72rem;font-weight:700;}',
      '.ssc-status-open{background:rgba(245,158,11,.14);color:#b45309;}',
      '.ssc-status-in_progress{background:rgba(59,130,246,.14);color:#2563eb;}',
      '.ssc-status-waiting_for_user{background:rgba(168,85,247,.14);color:#7c3aed;}',
      '.ssc-status-resolved{background:rgba(16,185,129,.14);color:#047857;}',
      '.ssc-status-closed{background:rgba(107,114,128,.14);color:#374151;}',
      '.ssc-priority-low{background:rgba(16,185,129,.12);color:#047857;}',
      '.ssc-priority-medium{background:rgba(59,130,246,.12);color:#2563eb;}',
      '.ssc-priority-high{background:rgba(245,158,11,.14);color:#b45309;}',
      '.ssc-priority-urgent{background:rgba(239,68,68,.14);color:#b91c1c;}',
      '.ssc-empty{padding:28px 18px;text-align:center;color:var(--muted, #6B705C);border:1px dashed var(--border, #DDD8CE);border-radius:14px;background:var(--cream, #FAF6EF);}',
      '.ssc-modal{position:fixed;inset:0;background:rgba(0,0,0,.45);backdrop-filter:blur(4px);display:none;align-items:center;justify-content:center;z-index:1200;padding:20px;}',
      '.ssc-modal.show{display:flex;}',
      '.ssc-modal-card{width:min(860px,100%);max-height:90vh;overflow:auto;background:#fff;border-radius:20px;box-shadow:0 20px 60px rgba(0,0,0,.22);}',
      '.ssc-modal-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding:20px 22px;border-bottom:1px solid var(--border, #DDD8CE);}',
      '.ssc-close{border:none;background:transparent;font-size:1.5rem;line-height:1;cursor:pointer;color:var(--muted, #6B705C);}',
      '.ssc-modal-body{padding:20px 22px;}',
      '.ssc-thread{display:flex;flex-direction:column;gap:12px;margin:16px 0;}',
      '.ssc-message{border:1px solid var(--border, #DDD8CE);border-radius:14px;padding:14px;background:#fff;}',
      '.ssc-message.internal{background:#faf5ff;border-color:#e9d5ff;}',
      '.ssc-message-head{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px;}',
      '.ssc-message-name{font-size:.8rem;font-weight:700;color:var(--forest, #1B4332);}',
      '.ssc-message-meta{font-size:.74rem;color:var(--muted, #6B705C);}',
      '.ssc-message-body{font-size:.84rem;color:var(--ink, #1A1A18);white-space:pre-wrap;line-height:1.6;}',
      '.ssc-kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-top:8px;}',
      '.ssc-kv-item{background:var(--cream, #FAF6EF);border:1px solid var(--border, #DDD8CE);padding:12px;border-radius:12px;}',
      '.ssc-kv-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted, #6B705C);font-weight:700;margin-bottom:4px;}',
      '.ssc-kv-value{font-size:.84rem;color:var(--ink, #1A1A18);font-weight:600;word-break:break-word;}',
      '.ssc-inline{display:flex;gap:10px;align-items:center;flex-wrap:wrap;}',
      '.ssc-note{font-size:.75rem;color:var(--muted, #6B705C);}',
      '.ssc-table{width:100%;border-collapse:collapse;}',
      '.ssc-table th,.ssc-table td{padding:10px 12px;border-bottom:1px solid var(--border, #DDD8CE);font-size:.82rem;text-align:left;vertical-align:top;}',
      '.ssc-table th{font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted, #6B705C);}',
      '.ssc-toggle{display:inline-flex;align-items:center;gap:8px;font-size:.8rem;color:var(--muted, #6B705C);}',
      '@media (max-width: 900px){.ssc-grid{grid-template-columns:1fr;}.ssc-form-grid{grid-template-columns:1fr;}.ssc-form-full{grid-column:1;}}'
    ].join('');
    document.head.appendChild(style);
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatDate(value) {
    if (!value) {
      return '—';
    }
    var date = new Date(value);
    if (isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString('en-KE', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function readCurrentUser() {
    try {
      return JSON.parse(localStorage.getItem('user') || 'null');
    } catch (err) {
      return null;
    }
  }

  function getUserDisplayName(user) {
    if (!user) {
      return 'User';
    }
    return ((user.first_name || '') + ' ' + (user.last_name || '')).trim() || user.email || 'User';
  }

  function statusPill(status) {
    var label = STATUS_LABELS[status] || status || 'Unknown';
    return '<span class="ssc-pill ssc-status-' + escapeHtml(status || 'open') + '">' + escapeHtml(label) + '</span>';
  }

  function priorityPill(priority) {
    return '<span class="ssc-pill ssc-priority-' + escapeHtml(priority || 'medium') + '">' + escapeHtml((priority || 'medium').replace('_', ' ')) + '</span>';
  }

  function categoryLabel(category) {
    var match = CATEGORY_OPTIONS.find(function (item) { return item[0] === category; });
    return match ? match[1] : (category || 'Other');
  }

  async function requestJson(url, options) {
    var response = await fetch(url, options || {});
    var payload = {};
    try {
      payload = await response.json();
    } catch (err) {
      payload = {};
    }
    if (!response.ok) {
      throw new Error(payload.error || 'Request failed');
    }
    return payload;
  }

  function runWithButtonLoading(button, loadingLabel, fn) {
    if (!button || button.disabled) {
      return Promise.resolve();
    }
    var idle = button.textContent;
    button.disabled = true;
    button.textContent = loadingLabel;
    return Promise.resolve(fn()).finally(function () {
      button.disabled = false;
      button.textContent = idle;
    });
  }

  function setAlert(container, kind, message) {
    if (!container) {
      return;
    }
    if (!message) {
      container.className = 'ssc-alert';
      container.textContent = '';
      return;
    }
    container.className = 'ssc-alert show ' + (kind === 'success' ? 'ssc-alert-success' : 'ssc-alert-error');
    container.textContent = message;
  }

  function userStats(tickets) {
    var stats = { total: tickets.length, open: 0, in_progress: 0, waiting_for_user: 0, resolved: 0 };
    tickets.forEach(function (ticket) {
      if (stats[ticket.status] != null) {
        stats[ticket.status] += 1;
      }
    });
    return stats;
  }

  function renderUserShell(root, roleLabel) {
    root.innerHTML = [
      '<div class="ssc-grid">',
        '<div class="ssc-card">',
          '<div class="ssc-title">Raise a Support Ticket</div>',
          '<div class="ssc-sub">Use the shared support workflow for buyers, farmers, and agro-dealers. Your ticket goes directly to admin-support.</div>',
          '<div class="ssc-alert" data-ssc-alert></div>',
          '<form data-ssc-create-form>',
            '<div class="ssc-form-grid">',
              '<div class="ssc-field">',
                '<label>Role</label>',
                '<input type="text" value="' + escapeHtml(roleLabel) + '" readonly />',
              '</div>',
              '<div class="ssc-field">',
                '<label>Priority</label>',
                '<select name="priority">' + PRIORITY_OPTIONS.map(function (opt) {
                  return '<option value="' + opt[0] + '">' + opt[1] + '</option>';
                }).join('') + '</select>',
              '</div>',
              '<div class="ssc-field">',
                '<label>Category</label>',
                '<select name="category">' + CATEGORY_OPTIONS.map(function (opt) {
                  return '<option value="' + opt[0] + '">' + opt[1] + '</option>';
                }).join('') + '</select>',
              '</div>',
              '<div class="ssc-field">',
                '<label>Subject</label>',
                '<input type="text" name="subject" placeholder="Briefly describe your issue" required />',
              '</div>',
              '<div class="ssc-field ssc-form-full">',
                '<label>Description</label>',
                '<textarea name="description" placeholder="Tell support what happened, what you expected, and any useful context." required></textarea>',
              '</div>',
            '</div>',
            '<div class="ssc-actions">',
              '<button class="ssc-btn ssc-btn-primary" type="submit">Submit Ticket</button>',
              '<span class="ssc-note">Support replies will appear in your ticket thread.</span>',
            '</div>',
          '</form>',
        '</div>',
        '<div class="ssc-card">',
          '<div class="ssc-title">My Ticket Overview</div>',
          '<div class="ssc-sub">Track your current cases and continue conversations with support.</div>',
          '<div class="ssc-stats" data-ssc-stats></div>',
        '</div>',
      '</div>',
      '<div class="ssc-card" style="margin-top:18px;">',
        '<div class="ssc-title">My Tickets</div>',
        '<div class="ssc-sub">Newest and recently updated tickets appear first.</div>',
        '<div class="ssc-list" data-ssc-ticket-list></div>',
      '</div>',
      '<div class="ssc-modal" data-ssc-modal>',
        '<div class="ssc-modal-card">',
          '<div class="ssc-modal-head">',
            '<div>',
              '<div class="ssc-title" style="margin-bottom:4px;">Ticket Details</div>',
              '<div class="ssc-sub" style="margin-bottom:0;">Reply to support and track ticket progress.</div>',
            '</div>',
            '<button class="ssc-close" type="button" data-ssc-close>&times;</button>',
          '</div>',
          '<div class="ssc-modal-body" data-ssc-modal-body></div>',
        '</div>',
      '</div>'
    ].join('');
  }

  function renderUserStats(state) {
    var stats = userStats(state.tickets);
    state.root.querySelector('[data-ssc-stats]').innerHTML = [
      ['Total', stats.total],
      ['Open', stats.open],
      ['In Progress', stats.in_progress],
      ['Waiting', stats.waiting_for_user],
      ['Resolved', stats.resolved]
    ].map(function (item) {
      return '<div class="ssc-stat"><div class="ssc-stat-label">' + item[0] + '</div><div class="ssc-stat-value">' + item[1] + '</div></div>';
    }).join('');
  }

  function renderUserTicketList(state) {
    var list = state.root.querySelector('[data-ssc-ticket-list]');
    if (!state.tickets.length) {
      list.innerHTML = '<div class="ssc-empty">No tickets yet. Raise your first issue and it will appear here.</div>';
      return;
    }

    list.innerHTML = state.tickets.map(function (ticket) {
      return [
        '<div class="ssc-ticket">',
          '<div class="ssc-ticket-top">',
            '<div>',
              '<div class="ssc-ticket-title">' + escapeHtml(ticket.subject) + '</div>',
              '<div class="ssc-ticket-meta">',
                '<span>' + escapeHtml(ticket.ticket_number) + '</span>',
                '<span>' + escapeHtml(categoryLabel(ticket.category)) + '</span>',
                '<span>' + escapeHtml(formatDate(ticket.updated_at || ticket.created_at)) + '</span>',
              '</div>',
            '</div>',
            '<div class="ssc-inline">',
              priorityPill(ticket.priority),
              statusPill(ticket.status),
            '</div>',
          '</div>',
          '<div class="ssc-ticket-body">' + escapeHtml(ticket.description || ticket.last_message || '') + '</div>',
          '<div class="ssc-actions" style="margin-top:0;">',
            '<button class="ssc-btn ssc-btn-outline" type="button" data-ssc-view-ticket="' + escapeHtml(ticket.id) + '">Open Thread</button>',
            '<span class="ssc-note">' + escapeHtml(String(ticket.message_count || 0)) + ' messages</span>',
          '</div>',
        '</div>'
      ].join('');
    }).join('');
  }

  function renderThread(messages) {
    return (messages || []).map(function (message) {
      var messageClasses = 'ssc-message' + (message.is_internal_note ? ' internal' : '');
      return [
        '<div class="' + messageClasses + '">',
          '<div class="ssc-message-head">',
            '<div class="ssc-message-name">' + escapeHtml(message.sender_name || (message.sender_type === 'admin' ? 'Admin Support' : 'User')) + '</div>',
            '<div class="ssc-message-meta">' + escapeHtml(message.sender_type === 'admin' ? 'Admin' : 'User') + ' · ' + escapeHtml(formatDate(message.created_at)) + '</div>',
          '</div>',
          message.is_internal_note ? '<div class="ssc-note" style="margin-bottom:8px;">Internal note</div>' : '',
          '<div class="ssc-message-body">' + escapeHtml(message.message || '') + '</div>',
        '</div>'
      ].join('');
    }).join('');
  }

  function renderUserTicketDetail(state, ticket) {
    var body = state.root.querySelector('[data-ssc-modal-body]');
    body.innerHTML = [
      '<div class="ssc-inline" style="justify-content:space-between;margin-bottom:12px;">',
        '<div>',
          '<div class="ssc-title" style="font-size:1rem;margin-bottom:2px;">' + escapeHtml(ticket.subject) + '</div>',
          '<div class="ssc-note">' + escapeHtml(ticket.ticket_number) + '</div>',
        '</div>',
        '<div class="ssc-inline">',
          priorityPill(ticket.priority),
          statusPill(ticket.status),
        '</div>',
      '</div>',
      '<div class="ssc-kv">',
        '<div class="ssc-kv-item"><div class="ssc-kv-label">Category</div><div class="ssc-kv-value">' + escapeHtml(categoryLabel(ticket.category)) + '</div></div>',
        '<div class="ssc-kv-item"><div class="ssc-kv-label">Assigned To</div><div class="ssc-kv-value">' + escapeHtml(ticket.assigned_admin_email || 'Unassigned') + '</div></div>',
        '<div class="ssc-kv-item"><div class="ssc-kv-label">Opened</div><div class="ssc-kv-value">' + escapeHtml(formatDate(ticket.created_at)) + '</div></div>',
      '</div>',
      ticket.resolution_summary ? '<div class="ssc-card" style="padding:14px;margin-top:14px;"><div class="ssc-kv-label">Resolution Summary</div><div class="ssc-message-body">' + escapeHtml(ticket.resolution_summary) + '</div></div>' : '',
      '<div class="ssc-title" style="font-size:1rem;margin:18px 0 8px;">Conversation</div>',
      '<div class="ssc-thread">' + renderThread(ticket.messages) + '</div>',
      '<div class="ssc-card" style="padding:16px;background:var(--cream, #FAF6EF);">',
        '<div class="ssc-title" style="font-size:1rem;">Reply to Support</div>',
        '<div class="ssc-sub">Add more details, answer a question, or reopen the conversation.</div>',
        '<form data-ssc-reply-form>',
          '<div class="ssc-field">',
            '<label>Message</label>',
            '<textarea name="message" placeholder="Type your reply here..." required></textarea>',
          '</div>',
          '<div class="ssc-actions">',
            '<button class="ssc-btn ssc-btn-primary" type="submit">Send Reply</button>',
          '</div>',
        '</form>',
      '</div>'
    ].join('');

    state.activeTicketId = ticket.id;
    state.root.querySelector('[data-ssc-modal]').classList.add('show');
  }

  async function loadUserTickets(state) {
    var payload = await requestJson(SUPPORT_API_BASE + '/tickets/my/' + encodeURIComponent(state.firebaseUid));
    state.tickets = payload.tickets || [];
    renderUserStats(state);
    renderUserTicketList(state);
  }

  async function openUserTicket(state, ticketId) {
    var payload = await requestJson(SUPPORT_API_BASE + '/tickets/' + encodeURIComponent(ticketId) + '?firebase_uid=' + encodeURIComponent(state.firebaseUid));
    renderUserTicketDetail(state, payload.ticket);
  }

  function bindUserEvents(state) {
    state.root.addEventListener('submit', async function (event) {
      var createForm = event.target.closest('[data-ssc-create-form]');
      var replyForm = event.target.closest('[data-ssc-reply-form]');
      if (!createForm && !replyForm) {
        return;
      }
      event.preventDefault();

      var submitBtn =
        (event.submitter && event.submitter.matches('button[type="submit"]') && event.submitter) ||
        (createForm && createForm.querySelector('button[type="submit"]')) ||
        (replyForm && replyForm.querySelector('button[type="submit"]'));

      try {
        if (createForm) {
          await runWithButtonLoading(submitBtn, 'Submitting…', async function () {
            setAlert(state.root.querySelector('[data-ssc-alert]'), null, '');
            var formData = new FormData(createForm);
            await requestJson(SUPPORT_API_BASE + '/tickets', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                firebase_uid: state.firebaseUid,
                category: formData.get('category'),
                priority: formData.get('priority'),
                subject: formData.get('subject'),
                description: formData.get('description')
              })
            });
            createForm.reset();
            createForm.querySelector('select[name="priority"]').value = 'medium';
            createForm.querySelector('select[name="category"]').value = 'account';
            setAlert(state.root.querySelector('[data-ssc-alert]'), 'success', 'Ticket submitted successfully. Admin-support can now respond.');
            await loadUserTickets(state);
          });
        } else if (replyForm && state.activeTicketId) {
          await runWithButtonLoading(submitBtn, 'Sending…', async function () {
            var replyData = new FormData(replyForm);
            await requestJson(SUPPORT_API_BASE + '/tickets/' + encodeURIComponent(state.activeTicketId) + '/messages', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                firebase_uid: state.firebaseUid,
                message: replyData.get('message')
              })
            });
            await openUserTicket(state, state.activeTicketId);
            await loadUserTickets(state);
          });
        }
      } catch (err) {
        setAlert(state.root.querySelector('[data-ssc-alert]'), 'error', err.message || 'Something went wrong.');
      }
    });

    state.root.addEventListener('click', async function (event) {
      var viewButton = event.target.closest('[data-ssc-view-ticket]');
      var closeButton = event.target.closest('[data-ssc-close]');
      var modal = state.root.querySelector('[data-ssc-modal]');

      if (viewButton) {
        await runWithButtonLoading(viewButton, 'Loading…', async function () {
          try {
            await openUserTicket(state, viewButton.getAttribute('data-ssc-view-ticket'));
          } catch (err) {
            setAlert(state.root.querySelector('[data-ssc-alert]'), 'error', err.message || 'Could not load ticket.');
          }
        });
      }

      if (closeButton || event.target === modal) {
        modal.classList.remove('show');
      }
    });
  }

  function adminStatsShell(root) {
    return [
      '<div class="ssc-stats" data-ssc-admin-stats></div>',
      '<div class="ssc-card">',
        '<div class="ssc-title">Support Queue</div>',
        '<div class="ssc-sub">Filter, assign, reply, and resolve tickets from one admin view.</div>',
        '<div class="ssc-alert" data-ssc-admin-alert></div>',
        '<div class="ssc-toolbar">',
          '<div class="ssc-field"><label>Status</label><select data-ssc-filter-status>',
            '<option value="all">All statuses</option>',
            '<option value="open">Open</option>',
            '<option value="in_progress">In Progress</option>',
            '<option value="waiting_for_user">Waiting for User</option>',
            '<option value="resolved">Resolved</option>',
            '<option value="closed">Closed</option>',
          '</select></div>',
          '<div class="ssc-field"><label>Priority</label><select data-ssc-filter-priority>',
            '<option value="all">All priorities</option>',
            '<option value="low">Low</option>',
            '<option value="medium">Medium</option>',
            '<option value="high">High</option>',
            '<option value="urgent">Urgent</option>',
          '</select></div>',
          '<div class="ssc-field"><label>Search</label><input type="text" data-ssc-filter-search placeholder="Search subject, email, or ticket number" /></div>',
          '<div class="ssc-actions" style="margin-top:26px;"><button class="ssc-btn ssc-btn-primary" type="button" data-ssc-admin-refresh>Refresh Queue</button></div>',
        '</div>',
        '<div style="overflow:auto;">',
          '<table class="ssc-table">',
            '<thead><tr><th>Ticket</th><th>User</th><th>Category</th><th>Priority</th><th>Status</th><th>Updated</th><th>Action</th></tr></thead>',
            '<tbody data-ssc-admin-list></tbody>',
          '</table>',
        '</div>',
        '<div class="ssc-inline" style="justify-content:flex-end;flex-wrap:wrap;gap:8px;padding-top:12px;">',
          '<button type="button" class="ssc-btn ssc-btn-outline" data-ssc-admin-page-prev>Previous</button>',
          '<span data-ssc-admin-page-label style="font-size:.8rem;color:var(--muted, #6B705C);">Page 1</span>',
          '<button type="button" class="ssc-btn ssc-btn-outline" data-ssc-admin-page-next>Next</button>',
        '</div>',
      '</div>',
      '<div class="ssc-modal" data-ssc-admin-modal>',
        '<div class="ssc-modal-card">',
          '<div class="ssc-modal-head">',
            '<div><div class="ssc-title" style="margin-bottom:4px;">Admin Ticket View</div><div class="ssc-sub" style="margin-bottom:0;">Reply, add notes, assign, and update workflow state.</div></div>',
            '<button class="ssc-close" type="button" data-ssc-admin-close>&times;</button>',
          '</div>',
          '<div class="ssc-modal-body" data-ssc-admin-modal-body></div>',
        '</div>',
      '</div>'
    ].join('');
  }

  function renderAdminStats(root, stats) {
    var shell = root.querySelector('[data-ssc-admin-stats]');
    shell.innerHTML = [
      ['Open', stats.open_tickets || 0],
      ['In Progress', stats.in_progress_tickets || 0],
      ['Waiting', stats.waiting_for_user_tickets || 0],
      ['Resolved', stats.resolved_tickets || 0],
      ['Urgent', stats.urgent_tickets || 0]
    ].map(function (item) {
      return '<div class="ssc-stat"><div class="ssc-stat-label">' + item[0] + '</div><div class="ssc-stat-value">' + item[1] + '</div></div>';
    }).join('');
  }

  var ADMIN_TICKETS_PER_PAGE = 10;

  function renderAdminList(state) {
    var list = state.root.querySelector('[data-ssc-admin-list]');
    var label = state.root.querySelector('[data-ssc-admin-page-label]');
    var all = state.allTickets || state.tickets || [];
    if (!all.length) {
      list.innerHTML = '<tr><td colspan="7"><div class="ssc-empty">No tickets match the current filters.</div></td></tr>';
      if (label) label.textContent = 'Page 1';
      var b0 = state.root.querySelector('[data-ssc-admin-page-prev]');
      var b1 = state.root.querySelector('[data-ssc-admin-page-next]');
      if (b0) b0.disabled = true;
      if (b1) b1.disabled = true;
      return;
    }
    var page = Math.max(0, state.adminTicketPage || 0);
    var totalPages = Math.max(1, Math.ceil(all.length / ADMIN_TICKETS_PER_PAGE));
    if (page >= totalPages) page = totalPages - 1;
    state.adminTicketPage = page;
    var start = page * ADMIN_TICKETS_PER_PAGE;
    var slice = all.slice(start, start + ADMIN_TICKETS_PER_PAGE);

    list.innerHTML = slice.map(function (ticket) {
      return [
        '<tr>',
          '<td><strong>' + escapeHtml(ticket.ticket_number) + '</strong><br /><span class="ssc-note">' + escapeHtml(ticket.subject) + '</span></td>',
          '<td><strong>' + escapeHtml(ticket.user_name || ticket.user_email || 'User') + '</strong><br /><span class="ssc-note">' + escapeHtml(ticket.user_email || '') + '</span></td>',
          '<td>' + escapeHtml(categoryLabel(ticket.category)) + '</td>',
          '<td>' + priorityPill(ticket.priority) + '</td>',
          '<td>' + statusPill(ticket.status) + '</td>',
          '<td>' + escapeHtml(formatDate(ticket.updated_at || ticket.created_at)) + '</td>',
          '<td><button class="ssc-btn ssc-btn-outline" type="button" data-ssc-admin-view="' + escapeHtml(ticket.id) + '">Open</button></td>',
        '</tr>'
      ].join('');
    }).join('');

    if (label) label.textContent = 'Page ' + (page + 1) + ' of ' + totalPages;
    var prevB = state.root.querySelector('[data-ssc-admin-page-prev]');
    var nextB = state.root.querySelector('[data-ssc-admin-page-next]');
    if (prevB) prevB.disabled = page === 0;
    if (nextB) nextB.disabled = page >= totalPages - 1;
  }

  function renderAdminTicket(state, ticket) {
    var body = state.root.querySelector('[data-ssc-admin-modal-body]');
    body.innerHTML = [
      '<div class="ssc-inline" style="justify-content:space-between;margin-bottom:12px;">',
        '<div>',
          '<div class="ssc-title" style="font-size:1rem;margin-bottom:2px;">' + escapeHtml(ticket.subject) + '</div>',
          '<div class="ssc-note">' + escapeHtml(ticket.ticket_number) + ' · ' + escapeHtml(ticket.user_name || ticket.user_email || '') + '</div>',
        '</div>',
        '<div class="ssc-inline">',
          priorityPill(ticket.priority),
          statusPill(ticket.status),
        '</div>',
      '</div>',
      '<div class="ssc-kv">',
        '<div class="ssc-kv-item"><div class="ssc-kv-label">User Role</div><div class="ssc-kv-value">' + escapeHtml(ticket.user_role || 'Unknown') + '</div></div>',
        '<div class="ssc-kv-item"><div class="ssc-kv-label">Assigned Admin</div><div class="ssc-kv-value">' + escapeHtml(ticket.assigned_admin_email || 'Unassigned') + '</div></div>',
        '<div class="ssc-kv-item"><div class="ssc-kv-label">Created</div><div class="ssc-kv-value">' + escapeHtml(formatDate(ticket.created_at)) + '</div></div>',
        '<div class="ssc-kv-item"><div class="ssc-kv-label">Phone</div><div class="ssc-kv-value">' + escapeHtml(ticket.phone_number || '—') + '</div></div>',
      '</div>',
      ticket.resolution_summary ? '<div class="ssc-card" style="padding:14px;margin-top:14px;"><div class="ssc-kv-label">Resolution Summary</div><div class="ssc-message-body">' + escapeHtml(ticket.resolution_summary) + '</div></div>' : '',
      '<div class="ssc-title" style="font-size:1rem;margin:18px 0 8px;">Conversation</div>',
      '<div class="ssc-thread">' + renderThread(ticket.messages) + '</div>',
      '<div class="ssc-grid" style="grid-template-columns:1fr 1fr;">',
        '<div class="ssc-card" style="padding:16px;">',
          '<div class="ssc-title" style="font-size:1rem;">Reply or Note</div>',
          '<form data-ssc-admin-reply-form>',
            '<div class="ssc-field">',
              '<label>Message</label>',
              '<textarea name="message" placeholder="Write a reply to the user or an internal note..." required></textarea>',
            '</div>',
            '<label class="ssc-toggle" style="margin-top:10px;"><input type="checkbox" name="is_internal_note" /> Save as internal note</label>',
            '<div class="ssc-actions">',
              '<button class="ssc-btn ssc-btn-primary" type="submit">Post Message</button>',
              '<button class="ssc-btn ssc-btn-outline" type="button" data-ssc-admin-assign>Assign to Me</button>',
            '</div>',
          '</form>',
        '</div>',
        '<div class="ssc-card" style="padding:16px;">',
          '<div class="ssc-title" style="font-size:1rem;">Workflow Controls</div>',
          '<form data-ssc-admin-status-form>',
            '<div class="ssc-field">',
              '<label>Status</label>',
              '<select name="status">',
                '<option value="open"' + (ticket.status === 'open' ? ' selected' : '') + '>Open</option>',
                '<option value="in_progress"' + (ticket.status === 'in_progress' ? ' selected' : '') + '>In Progress</option>',
                '<option value="waiting_for_user"' + (ticket.status === 'waiting_for_user' ? ' selected' : '') + '>Waiting for User</option>',
                '<option value="resolved"' + (ticket.status === 'resolved' ? ' selected' : '') + '>Resolved</option>',
                '<option value="closed"' + (ticket.status === 'closed' ? ' selected' : '') + '>Closed</option>',
              '</select>',
            '</div>',
            '<div class="ssc-field" style="margin-top:12px;">',
              '<label>Resolution Summary</label>',
              '<textarea name="resolution_summary" placeholder="Optional summary for the customer and support records.">' + escapeHtml(ticket.resolution_summary || '') + '</textarea>',
            '</div>',
            '<div class="ssc-actions">',
              '<button class="ssc-btn ssc-btn-primary" type="submit">Update Status</button>',
            '</div>',
          '</form>',
        '</div>',
      '</div>'
    ].join('');

    state.activeTicketId = ticket.id;
    state.root.querySelector('[data-ssc-admin-modal]').classList.add('show');
  }

  async function loadAdminStats(state) {
    var payload = await requestJson(SUPPORT_API_BASE + '/admin/stats');
    renderAdminStats(state.root, payload.stats || {});
  }

  async function loadAdminTickets(state) {
    var status = state.root.querySelector('[data-ssc-filter-status]').value;
    var priority = state.root.querySelector('[data-ssc-filter-priority]').value;
    var search = state.root.querySelector('[data-ssc-filter-search]').value.trim();
    var query = new URLSearchParams();
    if (status && status !== 'all') {
      query.set('status', status);
    }
    if (priority && priority !== 'all') {
      query.set('priority', priority);
    }
    if (search) {
      query.set('search', search);
    }

    var payload = await requestJson(SUPPORT_API_BASE + '/admin/tickets' + (query.toString() ? '?' + query.toString() : ''));
    state.allTickets = payload.tickets || [];
    state.tickets = state.allTickets;
    state.adminTicketPage = 0;
    renderAdminList(state);
  }

  async function openAdminTicket(state, ticketId) {
    var payload = await requestJson(SUPPORT_API_BASE + '/admin/tickets/' + encodeURIComponent(ticketId));
    renderAdminTicket(state, payload.ticket);
  }

  function bindAdminEvents(state) {
    state.root.addEventListener('click', async function (event) {
      var refresh = event.target.closest('[data-ssc-admin-refresh]');
      var view = event.target.closest('[data-ssc-admin-view]');
      var close = event.target.closest('[data-ssc-admin-close]');
      var assign = event.target.closest('[data-ssc-admin-assign]');
      var pagePrev = event.target.closest('[data-ssc-admin-page-prev]');
      var pageNext = event.target.closest('[data-ssc-admin-page-next]');
      var modal = state.root.querySelector('[data-ssc-admin-modal]');

      try {
        if (pagePrev && !pagePrev.disabled) {
          state.adminTicketPage = (state.adminTicketPage || 0) - 1;
          renderAdminList(state);
        }
        if (pageNext && !pageNext.disabled) {
          state.adminTicketPage = (state.adminTicketPage || 0) + 1;
          renderAdminList(state);
        }
        if (refresh) {
          await runWithButtonLoading(refresh, 'Refreshing…', async function () {
            await loadAdminStats(state);
            await loadAdminTickets(state);
          });
        }
        if (view) {
          await runWithButtonLoading(view, 'Loading…', async function () {
            await openAdminTicket(state, view.getAttribute('data-ssc-admin-view'));
          });
        }
        if (assign && state.activeTicketId) {
          await runWithButtonLoading(assign, 'Assigning…', async function () {
            await requestJson(SUPPORT_API_BASE + '/admin/tickets/' + encodeURIComponent(state.activeTicketId) + '/assign', {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ admin_email: state.adminEmail })
            });
            await openAdminTicket(state, state.activeTicketId);
            await loadAdminStats(state);
            await loadAdminTickets(state);
          });
        }
        if (close || event.target === modal) {
          modal.classList.remove('show');
        }
      } catch (err) {
        setAlert(state.root.querySelector('[data-ssc-admin-alert]'), 'error', err.message || 'Action failed.');
      }
    });

    state.root.addEventListener('change', function (event) {
      if (
        event.target.matches('[data-ssc-filter-status]') ||
        event.target.matches('[data-ssc-filter-priority]')
      ) {
        loadAdminTickets(state).catch(function (err) {
          setAlert(state.root.querySelector('[data-ssc-admin-alert]'), 'error', err.message || 'Could not refresh queue.');
        });
      }
    });

    state.root.addEventListener('keydown', function (event) {
      if (event.target.matches('[data-ssc-filter-search]') && event.key === 'Enter') {
        event.preventDefault();
        loadAdminTickets(state).catch(function (err) {
          setAlert(state.root.querySelector('[data-ssc-admin-alert]'), 'error', err.message || 'Could not refresh queue.');
        });
      }
    });

    state.root.addEventListener('submit', async function (event) {
      var replyForm = event.target.closest('[data-ssc-admin-reply-form]');
      var statusForm = event.target.closest('[data-ssc-admin-status-form]');
      if (!replyForm && !statusForm) {
        return;
      }
      event.preventDefault();

      var adminSubmitBtn =
        (event.submitter && event.submitter.matches('button[type="submit"]') && event.submitter) ||
        (replyForm && replyForm.querySelector('button[type="submit"]')) ||
        (statusForm && statusForm.querySelector('button[type="submit"]'));

      try {
        if (replyForm && state.activeTicketId) {
          await runWithButtonLoading(adminSubmitBtn, 'Posting…', async function () {
            var replyData = new FormData(replyForm);
            await requestJson(SUPPORT_API_BASE + '/admin/tickets/' + encodeURIComponent(state.activeTicketId) + '/messages', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                admin_email: state.adminEmail,
                admin_name: state.adminEmail,
                message: replyData.get('message'),
                is_internal_note: replyData.get('is_internal_note') === 'on'
              })
            });
            await openAdminTicket(state, state.activeTicketId);
            await loadAdminStats(state);
            await loadAdminTickets(state);
            setAlert(state.root.querySelector('[data-ssc-admin-alert]'), 'success', 'Message posted successfully.');
          });
        } else if (statusForm && state.activeTicketId) {
          await runWithButtonLoading(adminSubmitBtn, 'Updating…', async function () {
            var statusData = new FormData(statusForm);
            await requestJson(SUPPORT_API_BASE + '/admin/tickets/' + encodeURIComponent(state.activeTicketId) + '/status', {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                admin_email: state.adminEmail,
                status: statusData.get('status'),
                resolution_summary: statusData.get('resolution_summary')
              })
            });
            await openAdminTicket(state, state.activeTicketId);
            await loadAdminStats(state);
            await loadAdminTickets(state);
            setAlert(state.root.querySelector('[data-ssc-admin-alert]'), 'success', 'Ticket status updated.');
          });
        }
      } catch (err) {
        setAlert(state.root.querySelector('[data-ssc-admin-alert]'), 'error', err.message || 'Action failed.');
      }
    });
  }

  async function initUserSupport(options) {
    injectStyles();

    var root = document.getElementById(options.rootId);
    var user = readCurrentUser();
    if (!root || !user) {
      return;
    }
    if (root.dataset.supportReady === 'true') {
      return;
    }

    var state = {
      root: root,
      firebaseUid: user.firebase_uid || user.id,
      roleLabel: options.roleLabel || (user.role || 'User'),
      userName: getUserDisplayName(user),
      tickets: [],
      activeTicketId: null
    };

    if (!state.firebaseUid) {
      root.innerHTML = '<div class="ssc-empty">Please sign in to use support.</div>';
      return;
    }

    renderUserShell(root, state.roleLabel);
    bindUserEvents(state);
    root.dataset.supportReady = 'true';

    try {
      await loadUserTickets(state);
    } catch (err) {
      setAlert(root.querySelector('[data-ssc-alert]'), 'error', err.message || 'Could not load support tickets.');
      renderUserStats(state);
      renderUserTicketList(state);
    }
  }

  async function initAdminSupport(options) {
    injectStyles();

    var root = document.getElementById(options.rootId);
    if (!root) {
      return;
    }
    if (root.dataset.supportReady === 'true') {
      return;
    }

    var state = {
      root: root,
      adminEmail: options.adminEmail || 'admin@mkulimasokoni.com',
      tickets: [],
      allTickets: [],
      adminTicketPage: 0,
      activeTicketId: null
    };

    root.innerHTML = adminStatsShell(root);
    bindAdminEvents(state);
    root.dataset.supportReady = 'true';

    try {
      await loadAdminStats(state);
      await loadAdminTickets(state);
    } catch (err) {
      setAlert(root.querySelector('[data-ssc-admin-alert]'), 'error', err.message || 'Could not load admin support queue.');
    }
  }

  window.SokoSupportCenter = {
    initUserSupport: initUserSupport,
    initAdminSupport: initAdminSupport
  };
})();
