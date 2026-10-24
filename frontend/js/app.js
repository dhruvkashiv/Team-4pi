// Hostlur Application Controller v2.0
// Dual Resolution, Gemma 4 Vision, Role Auth & Theme System

let currentUser = null;
let currentView = 'landing';
let currentTheme = localStorage.getItem('hostlur_theme') || 'dark';
let activeMenuDay = 'Monday';
let pendingImageBase64 = null;
let pendingImageUrl = null;
let currentFilters = {
  search: '',
  category: '',
  status: '',
  block: '',
  mine: false
};
let complaintsList = [];
let relatedDebounceTimer = null;
let currentResolvingComplaintId = null;

// Views
const views = {
  auth: document.getElementById('view-auth'),
  student: document.getElementById('view-student'),
  newComplaint: document.getElementById('view-new-complaint'),
  warden: document.getElementById('view-warden'),
  mess: document.getElementById('view-mess'),
  curfew: document.getElementById('view-curfew'),
  manual: document.getElementById('view-manual')
};

// Portal Selection & Auth Screen Switching
function showAuthScreen(screen) {
  const sel = document.getElementById('auth-portal-selection');
  const stu = document.getElementById('auth-student-login');
  const war = document.getElementById('auth-warden-login');

  if (sel) sel.style.display = (screen === 'selection') ? 'block' : 'none';
  if (stu) stu.style.display = (screen === 'student') ? 'block' : 'none';
  if (war) war.style.display = (screen === 'warden') ? 'block' : 'none';

  const stuErr = document.getElementById('student-login-error');
  const warErr = document.getElementById('warden-login-error');
  if (stuErr) { stuErr.style.display = 'none'; stuErr.textContent = ''; }
  if (warErr) { warErr.style.display = 'none'; warErr.textContent = ''; }
}

function autofillLogin(role) {
  if (role === 'student') {
    const email = document.getElementById('student-login-email');
    const pwd = document.getElementById('student-login-pwd');
    if (email) email.value = 'aarav@campus.edu';
    if (pwd) pwd.value = 'Student@123';
  } else if (role === 'warden') {
    const email = document.getElementById('warden-login-email');
    const pwd = document.getElementById('warden-login-pwd');
    if (email) email.value = 'warden.sharma@campus.edu';
    if (pwd) pwd.value = 'Warden@123';
  }
}

function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = '🙈';
  } else {
    input.type = 'password';
    btn.textContent = '👁️';
  }
}

// Toast notification helper
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Theme Toggle
function initTheme() {
  document.documentElement.setAttribute('data-theme', currentTheme);
  const btn = document.getElementById('btn-theme-toggle');
  if (btn) btn.textContent = currentTheme === 'dark' ? '☀️' : '🌙';
}

function toggleTheme() {
  currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('hostlur_theme', currentTheme);
  document.documentElement.setAttribute('data-theme', currentTheme);
  const btn = document.getElementById('btn-theme-toggle');
  if (btn) btn.textContent = currentTheme === 'dark' ? '☀️' : '🌙';
  showToast(`Switched to ${currentTheme} theme.`, 'info');
}

// Navigation & View Switching
function switchView(viewName) {
  // If unauthenticated, STRICTLY lock view to 'auth'
  if (!currentUser) {
    viewName = 'auth';
  } else {
    // Role-based route enforcement
    if (currentUser.role === 'student' && viewName === 'warden') {
      viewName = 'student';
    }
    if (currentUser.role === 'warden' && (viewName === 'student' || viewName === 'newComplaint')) {
      viewName = 'warden';
    }
  }

  currentView = viewName;

  document.querySelectorAll('.nav-item-btn').forEach(btn => {
    if (btn.dataset.view === viewName) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  Object.keys(views).forEach(key => {
    if (views[key]) {
      views[key].style.display = (key === viewName) ? 'block' : 'none';
    }
  });

  window.scrollTo({ top: 0, behavior: 'smooth' });

  // Load View Data
  if (viewName === 'auth') {
    showAuthScreen('selection');
  } else if (viewName === 'student') {
    loadStudentDashboard();
  } else if (viewName === 'warden') {
    loadWardenDashboard();
  } else if (viewName === 'newComplaint') {
    autoFillStudentProfileInForm();
  } else if (viewName === 'mess') {
    loadMessData();
  } else if (viewName === 'curfew') {
    loadCurfewAndContacts();
  }
}

// Auth State & User Session
async function initUser() {
  if (!window.api.token) {
    currentUser = null;
    updateUserInterface();
    switchView('auth');
    showAuthScreen('selection');
    return;
  }

  try {
    currentUser = await window.api.getMe();
    updateUserInterface();
    populateUserSwitcherDropdown();
    if (currentUser.role === 'warden') {
      switchView('warden');
    } else {
      switchView('student');
    }
  } catch (err) {
    window.api.clearSession();
    currentUser = null;
    updateUserInterface();
    switchView('auth');
    showAuthScreen('selection');
  }
}

function updateUserInterface() {
  const navMenuWrap = document.getElementById('nav-menu-wrap');
  const navAuthBlock = document.getElementById('nav-auth-user-block');
  const nameEl = document.getElementById('nav-user-name');
  const roleEl = document.getElementById('nav-user-role');
  const wardenNav = document.getElementById('nav-warden-btn');
  const studentNav = document.getElementById('nav-student-btn');
  const reportNav = document.getElementById('nav-report-btn');

  if (!currentUser) {
    if (navMenuWrap) navMenuWrap.style.display = 'none';
    if (navAuthBlock) navAuthBlock.style.display = 'none';
    return;
  }

  // Authenticated state
  if (navMenuWrap) navMenuWrap.style.display = 'block';
  if (navAuthBlock) navAuthBlock.style.display = 'flex';

  if (nameEl) nameEl.textContent = currentUser.name;
  if (roleEl) {
    roleEl.textContent = currentUser.role === 'warden' ? 'Warden' : 'Student';
    roleEl.className = `role-pill ${currentUser.role === 'warden' ? 'role-warden' : 'role-student'}`;
  }

  if (wardenNav) wardenNav.style.display = (currentUser.role === 'warden') ? 'inline-flex' : 'none';
  if (studentNav) studentNav.style.display = (currentUser.role === 'student') ? 'inline-flex' : 'none';
  if (reportNav) reportNav.style.display = (currentUser.role === 'student') ? 'inline-flex' : 'none';

  // Update greeting text on student dashboard
  const greetEl = document.getElementById('student-greeting-name');
  if (greetEl) greetEl.textContent = currentUser.name;
  const blockEl = document.getElementById('student-greeting-block');
  if (blockEl) blockEl.textContent = `${currentUser.hostel_block || 'Hostel'} • ${currentUser.floor || ''} ${currentUser.room || ''}`;
}

async function populateUserSwitcherDropdown() {
  try {
    const users = await window.api.getUsers();
    const select = document.getElementById('persona-switcher-select');
    if (!select) return;

    select.innerHTML = '';
    users.forEach(u => {
      const opt = document.createElement('option');
      opt.value = u.id;
      opt.textContent = `${u.role === 'warden' ? '🛡️ Warden' : '🎓 Student'}: ${u.name} (${u.room || 'Admin'})`;
      if (u.id === currentUser.id) opt.selected = true;
      select.appendChild(opt);
    });

    select.onchange = async (e) => {
      window.api.currentUserId = e.target.value;
      localStorage.setItem('hostlur_user_id', e.target.value);
      currentUser = await window.api.getMe();
      updateUserInterface();
      showToast(`Switched persona to ${currentUser.name} (${currentUser.role})`, 'info');
      if (currentUser.role === 'warden') switchView('warden');
      else switchView('student');
    };
  } catch (err) {
    console.error('Error loading demo switchers:', err);
  }
}

// Student Auto-Fill
function autoFillStudentProfileInForm() {
  if (!currentUser) return;
  const blockSelect = document.getElementById('form-block');
  const floorInput = document.getElementById('form-floor');
  const locationInput = document.getElementById('form-location');
  const ownRoomCheckbox = document.getElementById('form-own-room-check');

  if (blockSelect && currentUser.hostel_block) {
    blockSelect.value = currentUser.hostel_block;
  }
  if (floorInput && currentUser.floor) {
    floorInput.value = currentUser.floor;
  }
  if (locationInput && currentUser.room) {
    locationInput.value = `Room ${currentUser.room}`;
  }

  if (ownRoomCheckbox) {
    ownRoomCheckbox.checked = true;
    locationInput.readOnly = true;
    ownRoomCheckbox.onchange = (e) => {
      if (e.target.checked) {
        locationInput.value = `Room ${currentUser.room}`;
        locationInput.readOnly = true;
      } else {
        locationInput.readOnly = false;
        locationInput.value = '';
        locationInput.placeholder = 'e.g. 2nd Floor Common Washroom / Study Hall';
      }
    };
  }
}

// Login Modal
function openLoginModal(defaultRole = 'student') {
  const modal = document.getElementById('login-modal');
  if (!modal) return;
  modal.classList.add('active');
  setLoginRoleTab(defaultRole);
}

function closeLoginModal() {
  const modal = document.getElementById('login-modal');
  if (modal) modal.classList.remove('active');
}

function setLoginRoleTab(role) {
  document.querySelectorAll('.login-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.role === role);
  });
  document.getElementById('login-role-hidden').value = role;

  const hint = document.getElementById('login-demo-hint');
  if (hint) {
    if (role === 'warden') {
      hint.innerHTML = `Demo Warden Credentials: <strong>warden.sharma@campus.edu</strong> / <strong>warden123</strong> <button type="button" class="btn btn-secondary btn-sm" onclick="quickFillLogin('warden.sharma@campus.edu', 'warden123', 'warden')">1-Click Auto Fill</button>`;
    } else {
      hint.innerHTML = `Demo Student Credentials: <strong>aarav@campus.edu</strong> / <strong>student123</strong> <button type="button" class="btn btn-secondary btn-sm" onclick="quickFillLogin('aarav@campus.edu', 'student123', 'student')">1-Click Auto Fill</button>`;
    }
  }
}

function quickFillLogin(email, password, role) {
  document.getElementById('login-email-input').value = email;
  document.getElementById('login-password-input').value = password;
  setLoginRoleTab(role);
}

async function handleStudentLoginSubmit(e) {
  e.preventDefault();
  const emailInput = document.getElementById('student-login-email');
  const pwdInput = document.getElementById('student-login-pwd');
  const btn = document.getElementById('student-login-btn');
  const errBox = document.getElementById('student-login-error');

  const email = emailInput ? emailInput.value.trim() : '';
  const password = pwdInput ? pwdInput.value : '';

  if (errBox) { errBox.style.display = 'none'; errBox.textContent = ''; }

  if (!email || !password) {
    if (errBox) {
      errBox.textContent = 'Please enter both student email/ID and password.';
      errBox.style.display = 'block';
    }
    return;
  }

  try {
    btn.disabled = true;
    btn.textContent = 'Signing in...';
    const res = await window.api.login(email, password, 'student');
    currentUser = res.user;
    updateUserInterface();
    populateUserSwitcherDropdown();
    if (pwdInput) pwdInput.value = '';
    showToast(`Welcome back, ${currentUser.name}!`, 'success');
    switchView('student');
  } catch (err) {
    if (errBox) {
      errBox.textContent = err.message || 'Invalid student credentials.';
      errBox.style.display = 'block';
    }
    showToast('Sign in failed: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign In as Student →';
  }
}

async function handleWardenLoginSubmit(e) {
  e.preventDefault();
  const emailInput = document.getElementById('warden-login-email');
  const pwdInput = document.getElementById('warden-login-pwd');
  const btn = document.getElementById('warden-login-btn');
  const errBox = document.getElementById('warden-login-error');

  const email = emailInput ? emailInput.value.trim() : '';
  const password = pwdInput ? pwdInput.value : '';

  if (errBox) { errBox.style.display = 'none'; errBox.textContent = ''; }

  if (!email || !password) {
    if (errBox) {
      errBox.textContent = 'Please enter both warden email/ID and password.';
      errBox.style.display = 'block';
    }
    return;
  }

  try {
    btn.disabled = true;
    btn.textContent = 'Signing in...';
    const res = await window.api.login(email, password, 'warden');
    currentUser = res.user;
    updateUserInterface();
    populateUserSwitcherDropdown();
    if (pwdInput) pwdInput.value = '';
    showToast(`Welcome, Warden ${currentUser.name}!`, 'success');
    switchView('warden');
  } catch (err) {
    if (errBox) {
      errBox.textContent = err.message || 'Invalid warden credentials.';
      errBox.style.display = 'block';
    }
    showToast('Sign in failed: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign In as Warden →';
  }
}

async function handleLogout() {
  await window.api.logout();
  currentUser = null;
  complaintsList = [];
  updateUserInterface();
  switchView('auth');
  showAuthScreen('selection');
  showToast('Signed out successfully.', 'info');
}

// Student Dashboard Loader
async function loadStudentDashboard() {
  try {
    const stats = await window.api.getStats();
    const s = stats.student;
    document.getElementById('stat-student-total').textContent = s.total_submitted;
    document.getElementById('stat-student-submitted').textContent = s.submitted;
    document.getElementById('stat-student-progress').textContent = s.in_progress;
    document.getElementById('stat-student-pending-verify').textContent = s.pending_verification || 0;
    document.getElementById('stat-student-resolved').textContent = s.resolved;

    const complaints = await window.api.getComplaints(currentFilters);
    complaintsList = complaints;
    renderComplaints('student-complaints-list', complaints, false);
  } catch (err) {
    showToast('Failed to load student complaints.', 'error');
  }
}

// Warden Dashboard Loader
async function loadWardenDashboard() {
  try {
    const stats = await window.api.getStats();
    const w = stats.warden;
    document.getElementById('stat-warden-open').textContent = w.total_open;
    document.getElementById('stat-warden-urgent').textContent = w.urgent;
    document.getElementById('stat-warden-progress').textContent = w.in_progress;
    document.getElementById('stat-warden-pending-confirm').textContent = w.pending_student_confirmation || 0;
    document.getElementById('stat-warden-resolved').textContent = w.resolved;

    const complaints = await window.api.getComplaints(currentFilters);
    complaintsList = complaints;
    renderComplaints('warden-complaints-list', complaints, true);

    loadWardenStudentList();
  } catch (err) {
    showToast('Failed to load warden complaints.', 'error');
  }
}

// Landing Live Preview
async function loadLandingPreview() {
  try {
    const complaints = await window.api.getComplaints();
    const container = document.getElementById('landing-preview-cards');
    if (!container) return;
    const sample = complaints.slice(0, 2);
    container.innerHTML = sample.map(c => renderComplaintCardHtml(c, false)).join('');
  } catch (err) {
    console.error('Preview error:', err);
  }
}

// Render Complaint Cards
function renderComplaints(containerId, complaints, isWarden = false) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (complaints.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 3.5rem 1.5rem; background: var(--color-bg-card); border: 1px dashed var(--color-border); border-radius: var(--radius-lg);">
        <div style="font-size: 2.8rem; margin-bottom: 0.8rem;">📭</div>
        <h3>No complaints found</h3>
        <p style="color: var(--color-text-secondary); margin-bottom: 1.2rem;">No reports match the selected filters.</p>
        ${!isWarden ? `<button class="btn btn-primary" onclick="switchView('newComplaint')">Report an Issue →</button>` : ''}
      </div>
    `;
    return;
  }

  container.innerHTML = complaints.map(c => renderComplaintCardHtml(c, isWarden)).join('');
}

function renderComplaintCardHtml(c, isWarden = false) {
  let statusBadgeClass = 'badge-submitted';
  if (c.status === 'Under Review') statusBadgeClass = 'badge-review';
  if (c.status === 'In Progress') statusBadgeClass = 'badge-progress';
  if (c.status === 'Pending Student Confirmation') statusBadgeClass = 'badge-pending-confirm';
  if (c.status === 'Resolved') statusBadgeClass = 'badge-resolved';
  if (c.status === 'Reopened') statusBadgeClass = 'badge-reopened';

  const isPendingStudentVerification = (c.status === 'Pending Student Confirmation');
  const isAuthor = (currentUser && currentUser.id === c.created_by_user_id);

  // Dual Verification Interactive Callout for the author
  let dualVerificationBanner = '';
  if (isPendingStudentVerification && isAuthor) {
    dualVerificationBanner = `
      <div class="dual-verification-alert">
        <div class="dual-alert-text">
          <strong>⚠️ Resolution Verification Required:</strong>
          <div>The warden marked work as completed: <em>"${escapeHtml(c.warden_note || 'Repairs completed.')}"</em>. Please verify if the problem is fully resolved.</div>
        </div>
        <div class="dual-alert-actions">
          <button class="btn btn-success btn-sm" onclick="openResolutionModal('${c.id}', 'confirm')">
            ✅ Confirm Resolved
          </button>
          <button class="btn btn-danger btn-sm" onclick="openResolutionModal('${c.id}', 'reject')">
            ❌ Still Broken / Reopen
          </button>
        </div>
      </div>
    `;
  }

  const prio = c.confirmed_priority || c.suggested_priority;
  const imageThumb = c.image_url ? `
    <img src="${c.image_url}" alt="Complaint image" class="complaint-img-preview" onclick="openImageModal('${c.image_url}')">
  ` : '';

  const aiSummary = c.summary ? `
    <div class="gemma-summary-callout">
      <span style="font-size: 0.75rem; font-weight: 800; background: var(--color-ai); color: #2D1452; padding: 0.2rem 0.5rem; border-radius: 12px;">Gemma 4 AI</span>
      <span>${escapeHtml(c.summary)}</span>
    </div>
  ` : '';

  const ratingDisplay = (c.student_rating && c.status === 'Resolved') ? `
    <span style="color: var(--color-primary); font-size: 0.85rem; font-weight: 700;">
      ${'★'.repeat(c.student_rating)}${'☆'.repeat(5 - c.student_rating)} Student Confirmed
    </span>
  ` : '';

  return `
    <div class="complaint-card ${isPendingStudentVerification ? 'pending-verification-card' : ''} ${c.is_hazard ? 'hazard-flagged' : ''}" id="card-${c.id}">
      <div class="card-header-row">
        <div>
          <span class="card-id-stamp">${c.id}</span>
          <h3 class="card-heading">${escapeHtml(c.title)}</h3>
        </div>
        <div class="card-tag-group">
          <span class="status-badge ${statusBadgeClass}">${c.status}</span>
          <span class="status-badge badge-submitted">${prio}</span>
          ${c.is_hazard ? '<span class="status-badge badge-hazard">🚨 Hazard</span>' : ''}
          <span class="status-badge badge-submitted">${escapeHtml(c.category)}</span>
          ${ratingDisplay}
        </div>
      </div>

      <div style="display: flex; gap: 1rem; align-items: flex-start;">
        ${imageThumb}
        <p style="font-size: 0.95rem; color: var(--color-text-secondary); flex: 1; line-height: 1.55;">
          ${escapeHtml(c.description)}
        </p>
      </div>

      ${aiSummary}
      ${dualVerificationBanner}

      <div class="card-footer-meta">
        <div class="meta-group">
          <span>📍 ${escapeHtml(c.hostel_block)} • ${escapeHtml(c.location)}</span>
          <span>👤 ${escapeHtml(c.created_by_name)} ${c.created_by_room ? `(${c.created_by_room})` : ''}</span>
          <span>⏱️ ${new Date(c.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
          ${c.reopened_count > 0 ? `<span style="color: var(--color-urgent); font-weight: 700;">⚠️ Reopened ${c.reopened_count}x</span>` : ''}
        </div>

        <div style="display: flex; align-items: center; gap: 0.6rem;">
          <button class="btn btn-secondary btn-sm" onclick="handleSupportClick('${c.id}')">
            👍 ${c.supporters_count} Support
          </button>
          <button class="btn btn-primary btn-sm" onclick="openComplaintModal('${c.id}')">
            ${isWarden ? 'Manage & Status →' : 'View Timeline →'}
          </button>
        </div>
      </div>
    </div>
  `;
}

// Dual Resolution Modal (Confirm / Reject)
function openResolutionModal(complaintId, action) {
  currentResolvingComplaintId = complaintId;
  const modal = document.getElementById('resolution-confirm-modal');
  if (!modal) return;

  const titleEl = document.getElementById('resolution-modal-title');
  const confirmBox = document.getElementById('resolution-confirm-fields');
  const rejectBox = document.getElementById('resolution-reject-fields');
  const actionBtn = document.getElementById('resolution-submit-btn');

  if (action === 'confirm') {
    titleEl.textContent = 'Confirm Issue Resolved';
    confirmBox.style.display = 'block';
    rejectBox.style.display = 'none';
    actionBtn.className = 'btn btn-success';
    actionBtn.textContent = 'Verify & Close Ticket';
    actionBtn.onclick = () => submitResolutionVerification('confirm');
  } else {
    titleEl.textContent = 'Report Issue Still Persists';
    confirmBox.style.display = 'none';
    rejectBox.style.display = 'block';
    actionBtn.className = 'btn btn-danger';
    actionBtn.textContent = 'Reopen Issue for Re-inspection';
    actionBtn.onclick = () => submitResolutionVerification('reject');
  }

  modal.classList.add('active');
}

function closeResolutionModal() {
  const modal = document.getElementById('resolution-confirm-modal');
  if (modal) modal.classList.remove('active');
}

async function submitResolutionVerification(action) {
  try {
    let rating = 5;
    let feedback = '';
    let reopenReason = '';

    if (action === 'confirm') {
      rating = parseInt(document.querySelector('input[name="star-rating"]:checked')?.value || '5');
      feedback = document.getElementById('resolution-feedback-input').value.trim();
    } else {
      reopenReason = document.getElementById('resolution-reopen-reason-input').value.trim();
      if (!reopenReason) {
        showToast('Please provide a reason why the issue persists.', 'error');
        return;
      }
    }

    await window.api.verifyResolution(currentResolvingComplaintId, action, rating, feedback, reopenReason);
    closeResolutionModal();
    showToast(action === 'confirm' ? 'Resolution verified and ticket closed!' : 'Issue reopened for warden review.', 'success');
    loadStudentDashboard();
  } catch (err) {
    showToast('Failed to update resolution: ' + err.message, 'error');
  }
}

// Complaint Details Modal
async function openComplaintModal(complaintId) {
  try {
    const c = await window.api.getComplaint(complaintId);
    const modal = document.getElementById('complaint-detail-modal');
    if (!modal) return;

    document.getElementById('modal-complaint-id').textContent = c.id;
    document.getElementById('modal-complaint-title').textContent = c.title;
    document.getElementById('modal-complaint-desc').textContent = c.description;
    document.getElementById('modal-complaint-location').textContent = `${c.hostel_block} • ${c.location} (Floor: ${c.floor || 'N/A'})`;
    document.getElementById('modal-complaint-author').textContent = `${c.created_by_name} (${c.created_by_room || 'Room N/A'})`;
    document.getElementById('modal-complaint-time').textContent = new Date(c.created_at).toLocaleString();
    document.getElementById('modal-complaint-status-badge').textContent = c.status;
    document.getElementById('modal-complaint-priority-badge').textContent = c.confirmed_priority || c.suggested_priority;

    // Image in modal
    const imgWrap = document.getElementById('modal-complaint-image-wrap');
    const imgEl = document.getElementById('modal-complaint-image');
    if (c.image_url) {
      imgWrap.style.display = 'block';
      imgEl.src = c.image_url;
    } else {
      imgWrap.style.display = 'none';
    }

    // Dual Resolution info in modal
    const dualInfo = document.getElementById('modal-dual-resolution-info');
    if (dualInfo) {
      dualInfo.innerHTML = `
        <div style="background: var(--color-bg-surface); padding: 0.8rem; border-radius: var(--radius-md); font-size: 0.88rem;">
          <div><strong>Warden Status:</strong> ${c.warden_confirmed ? '✅ Confirmed Completed (' + new Date(c.warden_confirmed_at).toLocaleTimeString() + ')' : '⏳ In Progress'}</div>
          <div><strong>Student Verification:</strong> ${c.student_confirmed ? '✅ Verified Solved (' + (c.student_rating || 5) + '/5 ★)' : (c.status === 'Pending Student Confirmation' ? '⏳ Awaiting Student Inspection' : 'Pending')}</div>
        </div>
      `;
    }

    // AI Box
    const aiBox = document.getElementById('modal-ai-box');
    if (c.summary) {
      aiBox.style.display = 'block';
      document.getElementById('modal-ai-summary').textContent = c.summary;
      document.getElementById('modal-ai-category').textContent = c.category;
      document.getElementById('modal-ai-priority').textContent = c.suggested_priority;
    } else {
      aiBox.style.display = 'none';
    }

    // Timeline History
    const timeline = document.getElementById('modal-timeline');
    if (c.history && c.history.length > 0) {
      timeline.innerHTML = c.history.map(h => `
        <div class="audit-entry">
          <div class="audit-bullet"></div>
          <strong>${h.new_status}</strong> by ${escapeHtml(h.changed_by_name)}
          <div style="color: var(--color-text-tertiary); font-size: 0.8rem;">${new Date(h.created_at).toLocaleString()}</div>
          ${h.note ? `<div style="margin-top: 0.2rem; font-style: italic; color: var(--color-text-secondary);">"${escapeHtml(h.note)}"</div>` : ''}
        </div>
      `).join('');
    } else {
      timeline.innerHTML = `<div style="color: var(--color-text-secondary);">No updates logged yet.</div>`;
    }

    // Warden Status Management
    const wardenActions = document.getElementById('modal-warden-actions');
    if (currentUser && currentUser.role === 'warden') {
      wardenActions.style.display = 'block';
      document.getElementById('modal-status-select').value = c.status;
      document.getElementById('modal-priority-select').value = c.confirmed_priority || c.suggested_priority;
      document.getElementById('modal-status-note').value = '';

      document.getElementById('modal-save-status-btn').onclick = async () => {
        const newStatus = document.getElementById('modal-status-select').value;
        const newPrio = document.getElementById('modal-priority-select').value;
        const note = document.getElementById('modal-status-note').value.trim();

        try {
          await window.api.updateComplaintStatus(c.id, newStatus, note, newPrio);
          showToast(`Status updated to ${newStatus}`, 'success');
          closeComplaintModal();
          loadWardenDashboard();
        } catch (err) {
          showToast('Status update failed: ' + err.message, 'error');
        }
      };
    } else {
      wardenActions.style.display = 'none';
    }

    modal.classList.add('active');
  } catch (err) {
    showToast('Failed to load complaint details: ' + err.message, 'error');
  }
}

function closeComplaintModal() {
  const modal = document.getElementById('complaint-detail-modal');
  if (modal) modal.classList.remove('active');
}

function openImageModal(imgUrl) {
  const modal = document.getElementById('image-viewer-modal');
  const imgEl = document.getElementById('image-viewer-el');
  if (modal && imgEl) {
    imgEl.src = imgUrl;
    modal.classList.add('active');
  }
}

function closeImageModal() {
  const modal = document.getElementById('image-viewer-modal');
  if (modal) modal.classList.remove('active');
}

// Support Action
async function handleSupportClick(complaintId) {
  try {
    const res = await window.api.toggleSupport(complaintId);
    showToast(res.supported ? 'Added +1 Support to this issue!' : 'Removed support.', 'info');
    if (currentView === 'student') loadStudentDashboard();
    else if (currentView === 'warden') loadWardenDashboard();
    else loadLandingPreview();
  } catch (err) {
    showToast('Failed to support: ' + err.message, 'error');
  }
}

// Image Selection & Gemma 4 Vision Analysis in New Complaint
function setupImageUploadHandlers() {
  const dropzone = document.getElementById('image-dropzone');
  const fileInput = document.getElementById('form-image-input');
  const previewWrap = document.getElementById('image-preview-wrap');
  const previewImg = document.getElementById('image-preview-thumb');
  const removeBtn = document.getElementById('image-remove-btn');

  if (!dropzone || !fileInput) return;

  dropzone.onclick = () => fileInput.click();

  fileInput.onchange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async () => {
      pendingImageBase64 = reader.result;
      previewImg.src = reader.result;
      previewWrap.style.display = 'flex';
      dropzone.style.display = 'none';

      try {
        const uploadRes = await window.api.uploadImage(pendingImageBase64, file.name);
        pendingImageUrl = uploadRes.image_url;
        showToast('Image attached and ready for Gemma 4 vision analysis.', 'success');
      } catch (err) {
        showToast('Image upload failed: ' + err.message, 'error');
      }
    };
    reader.readAsDataURL(file);
  };

  if (removeBtn) {
    removeBtn.onclick = () => {
      pendingImageBase64 = null;
      pendingImageUrl = null;
      fileInput.value = '';
      previewWrap.style.display = 'none';
      dropzone.style.display = 'flex';
    };
  }

  // Auto Analyze with Gemma 4 Vision Button
  const aiBtn = document.getElementById('form-ai-btn');
  if (aiBtn) {
    aiBtn.onclick = async () => {
      const desc = document.getElementById('form-description').value.trim();
      const block = document.getElementById('form-block').value;
      const location = document.getElementById('form-location').value.trim();

      if (desc.length < 5 && !pendingImageBase64) {
        showToast('Please enter a description or attach an image first.', 'info');
        return;
      }

      try {
        aiBtn.disabled = true;
        aiBtn.innerHTML = `<span>⏳ Analyzing with Gemma 4 ${pendingImageBase64 ? 'Vision...' : '...'}</span>`;

        const res = await window.api.analyzeWithAI(desc || 'Please inspect attached image', block, location, pendingImageBase64);

        if (res.category) {
          const catSelect = document.getElementById('form-category');
          if (catSelect) catSelect.value = res.category;
        }
        if (res.location && !document.getElementById('form-location').value) {
          document.getElementById('form-location').value = res.location;
        }
        if (!document.getElementById('form-title').value.trim() && res.summary) {
          document.getElementById('form-title').value = res.summary;
        }

        const previewBox = document.getElementById('form-ai-preview');
        if (previewBox) previewBox.style.display = 'block';

        const catEl = document.getElementById('form-ai-cat-suggest');
        if (catEl) catEl.textContent = res.category || '-';

        const subcatEl = document.getElementById('form-ai-subcat-suggest');
        if (subcatEl) subcatEl.textContent = res.subcategory || 'Standard';

        const confEl = document.getElementById('form-ai-confidence-suggest');
        if (confEl) {
          const confVal = (typeof res.confidence === 'number' && res.confidence > 0) ? res.confidence : 0.95;
          confEl.textContent = `${Math.round(confVal * 100)}% confidence score`;
        }

        const evEl = document.getElementById('form-ai-evidence-suggest');
        if (evEl) {
          if (res.visual_evidence && res.visual_evidence.length > 0) {
            evEl.textContent = res.visual_evidence.join('; ');
          } else {
            evEl.textContent = 'Derived from problem description and visual features.';
          }
        }

        const prioEl = document.getElementById('form-ai-prio-suggest');
        if (prioEl) prioEl.textContent = res.suggested_priority || 'Medium';

        const sumEl = document.getElementById('form-ai-summary-suggest');
        if (sumEl) sumEl.textContent = res.summary || '-';

        const reviewAlert = document.getElementById('form-ai-review-alert');
        if (reviewAlert) {
          reviewAlert.style.display = (res.needs_human_review || (res.confidence && res.confidence < 0.6)) ? 'block' : 'none';
        }

        const hazardAlert = document.getElementById('form-ai-hazard-alert');
        const hazardReason = document.getElementById('form-ai-hazard-reason');
        if (hazardAlert && hazardReason) {
          if (res.is_hazard) {
            hazardAlert.style.display = 'block';
            hazardReason.textContent = res.hazard_reason || 'Critical physical or electrical issue';
          } else {
            hazardAlert.style.display = 'none';
          }
        }

        showToast(`Gemma 4 ${res.image_analyzed ? 'Vision' : 'AI'} analysis complete!`, 'success');
      } catch (err) {
        showToast('AI note: ' + err.message, 'info');
      } finally {
        aiBtn.disabled = false;
        aiBtn.innerHTML = `<span>✨ Auto-Analyze with Gemma 4 ${pendingImageBase64 ? 'Vision' : 'AI'}</span>`;
      }
    };
  }
}

// Complaint Form Submission
async function handleComplaintSubmit(e) {
  e.preventDefault();

  const title = document.getElementById('form-title').value.trim();
  const category = document.getElementById('form-category').value;
  const block = document.getElementById('form-block').value;
  const floor = document.getElementById('form-floor').value.trim();
  const location = document.getElementById('form-location').value.trim();
  const description = document.getElementById('form-description').value.trim();
  const duration = document.getElementById('form-duration').value.trim();
  const submitBtn = document.getElementById('form-submit-btn');

  if (!title || !category || !block || !location || !description) {
    showToast('Please fill in all required fields.', 'error');
    return;
  }

  try {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving Complaint...';

    const payload = {
      title,
      category,
      hostel_block: block,
      floor,
      location,
      description,
      duration: duration || null,
      image_url: pendingImageUrl,
      run_ai: true
    };

    const created = await window.api.createComplaint(payload);
    showToast(`Complaint ${created.id} submitted successfully!`, 'success');

    // Reset Form
    document.getElementById('complaint-form').reset();
    pendingImageBase64 = null;
    pendingImageUrl = null;
    document.getElementById('image-preview-wrap').style.display = 'none';
    document.getElementById('image-dropzone').style.display = 'flex';
    document.getElementById('form-ai-preview').style.display = 'none';

    switchView('student');
  } catch (err) {
    showToast('Submission failed: ' + err.message, 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Submit Complaint →';
  }
}

// Warden Student Management
async function loadWardenStudentList() {
  const container = document.getElementById('warden-students-table-body');
  if (!container) return;

  try {
    const students = await window.api.getWardenStudents();
    if (students.length === 0) {
      container.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem;">No students registered yet.</td></tr>`;
      return;
    }

    container.innerHTML = students.map(s => `
      <tr>
        <td style="font-weight: 700;">${escapeHtml(s.name)}</td>
        <td>${escapeHtml(s.email)}</td>
        <td>${escapeHtml(s.hostel_block)}</td>
        <td>${escapeHtml(s.floor || '')} • ${escapeHtml(s.room || '')}</td>
        <td>${escapeHtml(s.phone || '')}</td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="handleWardenPasswordReset('${s.id}', '${escapeHtml(s.name)}')">
            🔑 Reset Password
          </button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    container.innerHTML = `<tr><td colspan="6" style="color: var(--color-urgent);">Error loading student directory: ${err.message}</td></tr>`;
  }
}

async function handleWardenCreateStudent(e) {
  e.preventDefault();
  const name = document.getElementById('new-student-name').value.trim();
  const email = document.getElementById('new-student-email').value.trim();
  const block = document.getElementById('new-student-block').value;
  const floor = document.getElementById('new-student-floor').value.trim();
  const room = document.getElementById('new-student-room').value.trim();
  const phone = document.getElementById('new-student-phone').value.trim();
  const pwd = document.getElementById('new-student-pwd').value.trim();

  try {
    const res = await window.api.createStudent({
      name, email, hostel_block: block, floor, room, phone, initial_password: pwd || null
    });

    document.getElementById('create-student-form').reset();
    showToast(`Student ${name} created successfully!`, 'success');

    // Show initial credentials dialog
    openCredentialModal(name, email, res.initial_password);
    loadWardenStudentList();
  } catch (err) {
    showToast('Failed to create student: ' + err.message, 'error');
  }
}

async function handleWardenPasswordReset(studentId, studentName) {
  try {
    const res = await window.api.resetStudentPassword(studentId);
    openCredentialModal(studentName, 'Student Portal', res.temporary_password, true);
  } catch (err) {
    showToast('Password reset failed: ' + err.message, 'error');
  }
}

function openCredentialModal(name, email, password, isReset = false) {
  const modal = document.getElementById('credentials-display-modal');
  if (!modal) return;
  document.getElementById('cred-modal-title').textContent = isReset ? 'Temporary Password Generated' : 'New Student Account Credentials';
  document.getElementById('cred-modal-name').textContent = name;
  document.getElementById('cred-modal-email').textContent = email;
  document.getElementById('cred-modal-password').textContent = password;
  modal.classList.add('active');
}

function closeCredentialModal() {
  const modal = document.getElementById('credentials-display-modal');
  if (modal) modal.classList.remove('active');
}

// Mess Data Loader
async function loadMessData() {
  try {
    const timings = await window.api.getMessTimings();
    const timingsContainer = document.getElementById('mess-timings-grid');
    if (timingsContainer) {
      timingsContainer.innerHTML = Object.keys(timings).map(key => `
        <div class="timing-row">
          <strong>${timings[key].title}</strong>
          <span style="font-family: var(--font-mono); font-weight: 700; color: var(--color-primary);">${timings[key].time}</span>
        </div>
      `).join('');
    }

    const weekly = await window.api.getMessMenu();
    window.messMenuData = weekly;
    renderDailyMessMenu(activeMenuDay);
  } catch (err) {
    showToast('Failed to load mess information.', 'error');
  }
}

function selectMessDay(day) {
  activeMenuDay = day;
  document.querySelectorAll('.day-menu-pill').forEach(pill => {
    pill.classList.toggle('active', pill.dataset.day === day);
  });
  renderDailyMessMenu(day);
}

function renderDailyMessMenu(day) {
  const container = document.getElementById('daily-mess-content');
  if (!container || !window.messMenuData) return;

  const item = window.messMenuData.find(m => m.day_of_week === day) || window.messMenuData[0];
  if (!item) return;

  container.innerHTML = `
    <div style="display: flex; flex-direction: column; gap: 1rem;">
      <div style="background: var(--color-bg-surface); padding: 1rem 1.25rem; border-radius: var(--radius-md);">
        <div style="font-size: 0.8rem; font-weight: 800; text-transform: uppercase; color: var(--color-primary); margin-bottom: 0.3rem;">🍳 Breakfast</div>
        <div style="font-size: 0.95rem; font-weight: 600;">${escapeHtml(item.breakfast)}</div>
      </div>
      <div style="background: var(--color-bg-surface); padding: 1rem 1.25rem; border-radius: var(--radius-md);">
        <div style="font-size: 0.8rem; font-weight: 800; text-transform: uppercase; color: var(--color-primary); margin-bottom: 0.3rem;">🍛 Lunch</div>
        <div style="font-size: 0.95rem; font-weight: 600;">${escapeHtml(item.lunch)}</div>
      </div>
      <div style="background: var(--color-bg-surface); padding: 1rem 1.25rem; border-radius: var(--radius-md);">
        <div style="font-size: 0.8rem; font-weight: 800; text-transform: uppercase; color: var(--color-primary); margin-bottom: 0.3rem;">☕ Evening Snacks</div>
        <div style="font-size: 0.95rem; font-weight: 600;">${escapeHtml(item.snacks)}</div>
      </div>
      <div style="background: var(--color-bg-surface); padding: 1rem 1.25rem; border-radius: var(--radius-md);">
        <div style="font-size: 0.8rem; font-weight: 800; text-transform: uppercase; color: var(--color-primary); margin-bottom: 0.3rem;">🍲 Dinner</div>
        <div style="font-size: 0.95rem; font-weight: 600;">${escapeHtml(item.dinner)}</div>
      </div>
      ${item.special_note ? `<div style="font-style: italic; font-size: 0.85rem; color: var(--color-text-secondary); text-align: right;">Chef Note: ${escapeHtml(item.special_note)}</div>` : ''}
    </div>
  `;
}

// Curfew & Contacts Loader
async function loadCurfewAndContacts() {
  try {
    const curfewData = await window.api.getCurfew();
    document.getElementById('curfew-weekday-text').textContent = curfewData.rules.weekday;
    document.getElementById('curfew-weekend-text').textContent = curfewData.rules.weekend;
    document.getElementById('curfew-policy-text').textContent = curfewData.rules.late_entry_policy;

    const annContainer = document.getElementById('announcements-list');
    if (annContainer) {
      annContainer.innerHTML = curfewData.announcements.map(a => `
        <div style="background: var(--color-bg-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 1.2rem; margin-bottom: 0.8rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
            <strong style="color: var(--color-primary); font-size: 1rem;">${escapeHtml(a.title)}</strong>
            <span class="status-badge badge-submitted">${a.category}</span>
          </div>
          <p style="font-size: 0.9rem; color: var(--color-text-secondary);">${escapeHtml(a.content)}</p>
          <div style="font-size: 0.78rem; color: var(--color-text-tertiary); margin-top: 0.4rem;">${new Date(a.created_at).toLocaleDateString()}</div>
        </div>
      `).join('');
    }

    const contacts = await window.api.getContacts();
    const contactContainer = document.getElementById('contacts-grid');
    if (contactContainer) {
      contactContainer.innerHTML = `
        <div class="info-card">
          <h3>🛡️ Chief Warden</h3>
          <div style="font-size: 0.95rem; font-weight: 700;">${escapeHtml(contacts.chief_warden.name)}</div>
          <div style="font-size: 0.88rem; color: var(--color-text-secondary); margin-bottom: 0.6rem;">${escapeHtml(contacts.chief_warden.role)}</div>
          <div class="timing-row"><span>Email</span><a href="mailto:${contacts.chief_warden.email}">${escapeHtml(contacts.chief_warden.email)}</a></div>
          <div class="timing-row"><span>Phone</span><a href="tel:${contacts.chief_warden.phone}">${escapeHtml(contacts.chief_warden.phone)}</a></div>
          <div class="timing-row"><span>Office</span><span>${escapeHtml(contacts.chief_warden.office)}</span></div>
          <div class="timing-row"><span>Hours</span><span>${escapeHtml(contacts.chief_warden.office_hours)}</span></div>
        </div>

        <div class="info-card">
          <h3>🏢 Caretakers</h3>
          <div style="font-size: 0.92rem; font-weight: 700;">${escapeHtml(contacts.caretaker_block_b.name)} (Boys)</div>
          <div class="timing-row"><span>Phone</span><a href="tel:${contacts.caretaker_block_b.phone}">${escapeHtml(contacts.caretaker_block_b.phone)}</a></div>
          <div style="font-size: 0.92rem; font-weight: 700; margin-top: 0.8rem;">${escapeHtml(contacts.caretaker_block_c.name)} (Girls)</div>
          <div class="timing-row"><span>Phone</span><a href="tel:${contacts.caretaker_block_c.phone}">${escapeHtml(contacts.caretaker_block_c.phone)}</a></div>
        </div>

        <div class="info-card" style="border-left: 5px solid var(--color-urgent);">
          <h3 style="color: var(--color-urgent);">🚨 Emergency Helpline</h3>
          <div class="timing-row"><span>24/7 Helpline</span><strong>${escapeHtml(contacts.emergency.helpline)}</strong></div>
          <div class="timing-row"><span>Ambulance</span><strong>${escapeHtml(contacts.emergency.campus_ambulance)}</strong></div>
          <div class="timing-row"><span>Security</span><strong>${escapeHtml(contacts.emergency.campus_security)}</strong></div>
        </div>
      `;
    }
  } catch (err) {
    showToast('Failed to load curfew & contacts.', 'error');
  }
}

// User Manual Accordion Toggle
function toggleManualAccordion(headerEl) {
  const content = headerEl.nextElementSibling;
  const arrow = headerEl.querySelector('.manual-arrow');
  if (content.style.display === 'block') {
    content.style.display = 'none';
    if (arrow) arrow.textContent = '▼';
  } else {
    content.style.display = 'block';
    if (arrow) arrow.textContent = '▲';
  }
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// Search and Filter Listeners
function setupSearchAndFilters() {
  const studentSearch = document.getElementById('student-search-input');
  if (studentSearch) {
    studentSearch.oninput = (e) => {
      currentFilters.search = e.target.value;
      loadStudentDashboard();
    };
  }

  const studentCat = document.getElementById('student-filter-category');
  if (studentCat) {
    studentCat.onchange = (e) => {
      currentFilters.category = e.target.value;
      loadStudentDashboard();
    };
  }

  const studentStatus = document.getElementById('student-filter-status');
  if (studentStatus) {
    studentStatus.onchange = (e) => {
      currentFilters.status = e.target.value;
      loadStudentDashboard();
    };
  }

  const studentMine = document.getElementById('student-filter-mine');
  if (studentMine) {
    studentMine.onchange = (e) => {
      currentFilters.mine = e.target.checked;
      loadStudentDashboard();
    };
  }

  const wardenSearch = document.getElementById('warden-search-input');
  if (wardenSearch) {
    wardenSearch.oninput = (e) => {
      currentFilters.search = e.target.value;
      loadWardenDashboard();
    };
  }

  const wardenBlock = document.getElementById('warden-filter-block');
  if (wardenBlock) {
    wardenBlock.onchange = (e) => {
      currentFilters.block = e.target.value;
      loadWardenDashboard();
    };
  }

  const wardenCat = document.getElementById('warden-filter-category');
  if (wardenCat) {
    wardenCat.onchange = (e) => {
      currentFilters.category = e.target.value;
      loadWardenDashboard();
    };
  }

  const wardenStatus = document.getElementById('warden-filter-status');
  if (wardenStatus) {
    wardenStatus.onchange = (e) => {
      currentFilters.status = e.target.value;
      loadWardenDashboard();
    };
  }
}

// App Initialization
document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  setupSearchAndFilters();
  setupImageUploadHandlers();

  // Brand Logo Click
  const brandLogo = document.getElementById('brand-logo-link');
  if (brandLogo) {
    brandLogo.addEventListener('click', (e) => {
      e.preventDefault();
      if (currentUser) {
        switchView(currentUser.role === 'warden' ? 'warden' : 'student');
      } else {
        switchView('auth');
        showAuthScreen('selection');
      }
    });
  }

  // Navigation Links
  document.querySelectorAll('[data-view-nav]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      switchView(el.getAttribute('data-view-nav'));
    });
  });

  // Complaint Form Submit
  const form = document.getElementById('complaint-form');
  if (form) form.onsubmit = handleComplaintSubmit;

  // Student First-Screen Login Form Submit
  const studentLoginForm = document.getElementById('student-login-form');
  if (studentLoginForm) studentLoginForm.onsubmit = handleStudentLoginSubmit;

  // Warden First-Screen Login Form Submit
  const wardenLoginForm = document.getElementById('warden-login-form');
  if (wardenLoginForm) wardenLoginForm.onsubmit = handleWardenLoginSubmit;

  // Modal Login Form Submit (if triggered)
  const loginForm = document.getElementById('login-form');
  if (loginForm) loginForm.onsubmit = handleLoginFormSubmit;

  // Warden Student Form Submit
  const createStudentForm = document.getElementById('create-student-form');
  if (createStudentForm) createStudentForm.onsubmit = handleWardenCreateStudent;

  // Check user session and set initial view
  await initUser();
});
