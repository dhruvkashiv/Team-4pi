// Hostlur Main Application Logic

let currentUser = null;
let currentView = 'landing';
let currentFilters = {
  search: '',
  category: '',
  status: '',
  block: '',
  mine: false
};
let complaintsList = [];
let relatedDebounceTimer = null;

// DOM Elements
const views = {
  landing: document.getElementById('view-landing'),
  student: document.getElementById('view-student'),
  newComplaint: document.getElementById('view-new-complaint'),
  warden: document.getElementById('view-warden')
};

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
  }, 3500);
}

// Navigation & View Routing
function switchView(viewName) {
  currentView = viewName;

  // Update navigation link highlights
  document.querySelectorAll('.nav-link').forEach(link => {
    if (link.dataset.view === viewName) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });

  // Toggle View Containers
  Object.keys(views).forEach(key => {
    if (views[key]) {
      views[key].style.display = (key === viewName) ? 'block' : 'none';
    }
  });

  window.scrollTo({ top: 0, behavior: 'smooth' });

  // Load View Specific Data
  if (viewName === 'student') {
    loadStudentDashboard();
  } else if (viewName === 'warden') {
    loadWardenDashboard();
  } else if (viewName === 'landing') {
    loadLandingPreview();
  }
}

// User Initialization and Demo Persona Switcher
async function initUser() {
  try {
    const users = await window.api.getUsers();
    const select = document.getElementById('user-switcher-select');
    if (select) {
      select.innerHTML = '';
      users.forEach(u => {
        const opt = document.createElement('option');
        opt.value = u.id;
        opt.textContent = `${u.role === 'warden' ? '🛡️ Warden' : '🎓 Student'}: ${u.name} (${u.room || u.role})`;
        if (u.id === window.api.currentUserId) opt.selected = true;
        select.appendChild(opt);
      });

      select.addEventListener('change', async (e) => {
        window.api.setUserId(e.target.value);
        await refreshUserData();
        showToast(`Switched persona to ${currentUser.name} (${currentUser.role})`, 'success');
        
        // Auto navigate if role changed
        if (currentUser.role === 'warden') {
          switchView('warden');
        } else {
          switchView('student');
        }
      });
    }

    await refreshUserData();
  } catch (err) {
    console.error('Failed to init user:', err);
  }
}

async function refreshUserData() {
  try {
    currentUser = await window.api.getMe();
    
    // Update navbar badges and role-based links
    const wardenLink = document.getElementById('nav-warden-link');
    const studentLink = document.getElementById('nav-student-link');
    
    if (currentUser.role === 'warden') {
      if (wardenLink) wardenLink.style.display = 'inline-block';
    } else {
      if (wardenLink) wardenLink.style.display = 'inline-block'; // allow preview
    }

    // Update greeting on student dashboard
    const greetingEl = document.getElementById('student-user-name');
    if (greetingEl) greetingEl.textContent = currentUser.name;
    
    const blockEl = document.getElementById('student-user-block');
    if (blockEl) blockEl.textContent = `${currentUser.hostel_block} • Room ${currentUser.room}`;

  } catch (err) {
    console.error('Refresh user error:', err);
  }
}

// Landing Page Dashboard Live Preview
async function loadLandingPreview() {
  try {
    const complaints = await window.api.getComplaints();
    const previewContainer = document.getElementById('landing-preview-cards');
    if (!previewContainer) return;

    const sample = complaints.slice(0, 2);
    previewContainer.innerHTML = sample.map(c => renderComplaintCardHtml(c, false)).join('');
  } catch (err) {
    console.error('Preview error:', err);
  }
}

// Student Dashboard Loader
async function loadStudentDashboard() {
  try {
    // 1. Fetch Real Stats
    const statsData = await window.api.getStats();
    const s = statsData.student;
    document.getElementById('stat-student-total').textContent = s.total_submitted;
    document.getElementById('stat-student-submitted').textContent = s.submitted;
    document.getElementById('stat-student-progress').textContent = s.in_progress;
    document.getElementById('stat-student-resolved').textContent = s.resolved;

    // 2. Fetch Complaints
    const complaints = await window.api.getComplaints(currentFilters);
    complaintsList = complaints;
    renderComplaintsList('student-complaints-list', complaints);
  } catch (err) {
    showToast('Failed to load dashboard records.', 'error');
  }
}

// Warden Dashboard Loader
async function loadWardenDashboard() {
  try {
    const statsData = await window.api.getStats();
    const w = statsData.warden;
    document.getElementById('stat-warden-open').textContent = w.total_open;
    document.getElementById('stat-warden-urgent').textContent = w.urgent;
    document.getElementById('stat-warden-progress').textContent = w.in_progress;
    document.getElementById('stat-warden-resolved').textContent = w.resolved;

    const complaints = await window.api.getComplaints(currentFilters);
    complaintsList = complaints;
    renderComplaintsList('warden-complaints-list', complaints, true);
  } catch (err) {
    showToast('Failed to load warden complaint list.', 'error');
  }
}

// Render Complaints List HTML
function renderComplaintsList(containerId, complaints, isWarden = false) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (complaints.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📭</div>
        <h3>No complaints found</h3>
        <p>No complaints match your current search or filter criteria.</p>
        ${!isWarden ? `<button class="btn btn-primary" onclick="switchView('newComplaint')">Report an Issue →</button>` : ''}
      </div>
    `;
    return;
  }

  container.innerHTML = complaints.map(c => renderComplaintCardHtml(c, isWarden)).join('');
}

// Helper to build Card HTML
function renderComplaintCardHtml(c, isWarden = false) {
  // Status Badge Class
  let statusBadgeClass = 'badge-submitted';
  if (c.status === 'Under Review') statusBadgeClass = 'badge-review';
  if (c.status === 'In Progress') statusBadgeClass = 'badge-progress';
  if (c.status === 'Resolved') statusBadgeClass = 'badge-resolved';

  // Priority Badge Class
  let priorityBadgeClass = 'badge-medium';
  const prio = c.confirmed_priority || c.suggested_priority;
  if (prio === 'Urgent') priorityBadgeClass = 'badge-urgent';
  if (prio === 'High') priorityBadgeClass = 'badge-high';
  if (prio === 'Low') priorityBadgeClass = 'badge-low';

  const hazardBanner = c.is_hazard ? `
    <div style="background: var(--color-urgent); border-radius: var(--radius-sm); padding: 0.5rem 0.8rem; font-size: 0.85rem; font-weight: 700; color: #8C1D18; display: flex; align-items: center; gap: 0.4rem; margin-top: 0.4rem;">
      ⚠️ Safety Alert: ${c.hazard_reason || 'Urgent hazard detected.'}
    </div>
  ` : '';

  const aiSummary = c.summary ? `
    <div class="ai-summary-pill">
      <span style="font-size: 0.8rem; font-weight: 800; background: var(--color-ai); padding: 0.15rem 0.5rem; border-radius: 12px; color: #2D1D60;">Gemma AI</span>
      <span>${c.summary}</span>
    </div>
  ` : '';

  return `
    <div class="complaint-card ${c.is_hazard ? 'hazard-card' : ''}" id="card-${c.id}">
      <div class="card-top">
        <div class="card-title-area">
          <span class="card-id-tag">${c.id}</span>
          <h3 class="card-title">${escapeHtml(c.title)}</h3>
        </div>
        <div class="card-badges">
          <span class="badge ${statusBadgeClass}">${c.status}</span>
          <span class="badge ${priorityBadgeClass}">${prio}</span>
          ${c.is_hazard ? '<span class="badge badge-hazard">🚨 Hazard</span>' : ''}
          <span class="badge badge-submitted">${escapeHtml(c.category)}</span>
        </div>
      </div>

      <p class="card-desc">${escapeHtml(c.description)}</p>

      ${aiSummary}
      ${hazardBanner}

      <div class="card-meta-row">
        <div class="meta-details">
          <span class="meta-item">📍 ${escapeHtml(c.hostel_block)} • ${escapeHtml(c.location)}</span>
          <span class="meta-item">👤 ${escapeHtml(c.created_by_name)} ${c.created_by_room ? `(${c.created_by_room})` : ''}</span>
          <span class="meta-item">⏱️ ${new Date(c.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
        </div>

        <div class="card-actions">
          <button class="btn-support ${c.has_supported ? 'active' : ''}" onclick="handleSupportClick('${c.id}')">
            👍 ${c.supporters_count} Support
          </button>
          <button class="btn btn-secondary btn-sm" onclick="openComplaintModal('${c.id}')">
            ${isWarden ? 'Manage & Update →' : 'View Timeline →'}
          </button>
        </div>
      </div>
    </div>
  `;
}

// Support Upvote Action
async function handleSupportClick(complaintId) {
  try {
    const res = await window.api.toggleSupport(complaintId);
    showToast(res.supported ? 'Added your support to this issue!' : 'Removed support.', 'info');
    
    // Refresh current view
    if (currentView === 'student') loadStudentDashboard();
    else if (currentView === 'warden') loadWardenDashboard();
    else loadLandingPreview();
  } catch (err) {
    showToast('Failed to toggle support: ' + err.message, 'error');
  }
}

// Complaint Detail & Warden Update Modal
async function openComplaintModal(complaintId) {
  try {
    const c = await window.api.getComplaint(complaintId);
    const modal = document.getElementById('complaint-detail-modal');
    if (!modal) return;

    document.getElementById('modal-complaint-id').textContent = c.id;
    document.getElementById('modal-complaint-title').textContent = c.title;
    document.getElementById('modal-complaint-desc').textContent = c.description;
    document.getElementById('modal-complaint-location').textContent = `${c.hostel_block} • ${c.location}`;
    document.getElementById('modal-complaint-author').textContent = `${c.created_by_name} (${c.created_by_room || 'Room N/A'})`;
    document.getElementById('modal-complaint-time').textContent = new Date(c.created_at).toLocaleString();
    document.getElementById('modal-complaint-status-badge').textContent = c.status;
    document.getElementById('modal-complaint-priority-badge').textContent = c.confirmed_priority || c.suggested_priority;

    // AI Analysis Block
    const aiBox = document.getElementById('modal-ai-box');
    if (c.summary) {
      aiBox.style.display = 'block';
      document.getElementById('modal-ai-summary').textContent = c.summary;
      document.getElementById('modal-ai-category').textContent = c.category;
      document.getElementById('modal-ai-priority').textContent = c.suggested_priority;
      
      const missingList = document.getElementById('modal-ai-missing');
      if (c.missing_information && c.missing_information.length > 0) {
        missingList.innerHTML = c.missing_information.map(m => `<li>${escapeHtml(m)}</li>`).join('');
        document.getElementById('modal-ai-missing-wrap').style.display = 'block';
      } else {
        document.getElementById('modal-ai-missing-wrap').style.display = 'none';
      }
    } else {
      aiBox.style.display = 'none';
    }

    // Timeline History
    const timelineContainer = document.getElementById('modal-timeline');
    if (c.history && c.history.length > 0) {
      timelineContainer.innerHTML = c.history.map(h => `
        <div class="timeline-item">
          <div class="timeline-dot"></div>
          <strong>${h.new_status}</strong> by ${escapeHtml(h.changed_by_name)}
          <div style="color: var(--color-text-secondary); font-size: 0.82rem;">${new Date(h.created_at).toLocaleString()}</div>
          ${h.note ? `<div style="margin-top: 0.2rem; font-style: italic;">"${escapeHtml(h.note)}"</div>` : ''}
        </div>
      `).join('');
    } else {
      timelineContainer.innerHTML = `<div style="color: var(--color-text-secondary);">No history updates yet.</div>`;
    }

    // Warden Status Management Section
    const wardenSection = document.getElementById('modal-warden-actions');
    if (currentUser && currentUser.role === 'warden') {
      wardenSection.style.display = 'block';
      document.getElementById('modal-status-select').value = c.status;
      document.getElementById('modal-priority-select').value = c.confirmed_priority || c.suggested_priority;
      document.getElementById('modal-status-note').value = '';
      
      const saveBtn = document.getElementById('modal-save-status-btn');
      saveBtn.onclick = async () => {
        const newStatus = document.getElementById('modal-status-select').value;
        const newPriority = document.getElementById('modal-priority-select').value;
        const note = document.getElementById('modal-status-note').value;

        try {
          saveBtn.disabled = true;
          saveBtn.textContent = 'Updating...';
          await window.api.updateComplaintStatus(c.id, newStatus, note, newPriority);
          showToast(`Status updated to ${newStatus}`, 'success');
          closeComplaintModal();
          loadWardenDashboard();
        } catch (err) {
          showToast('Failed to update status: ' + err.message, 'error');
        } finally {
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save Status Update';
        }
      };
    } else {
      wardenSection.style.display = 'none';
    }

    modal.classList.add('open');
  } catch (err) {
    showToast('Failed to load complaint details: ' + err.message, 'error');
  }
}

function closeComplaintModal() {
  const modal = document.getElementById('complaint-detail-modal');
  if (modal) modal.classList.remove('open');
}

// Live Gemma AI Assistant in New Complaint Form
async function handleAIAssist() {
  const desc = document.getElementById('form-description').value.trim();
  const block = document.getElementById('form-block').value;
  const location = document.getElementById('form-location').value.trim();

  if (desc.length < 10) {
    showToast('Please write a bit more in the description first (at least 10 characters).', 'info');
    return;
  }

  const aiBtn = document.getElementById('form-ai-btn');
  const previewBox = document.getElementById('form-ai-preview');

  try {
    aiBtn.disabled = true;
    aiBtn.innerHTML = `<span>⏳ Analyzing with Gemma 4...</span>`;

    const result = await window.api.analyzeWithAI(desc, block, location);
    
    // Auto populate category
    if (result.category) {
      document.getElementById('form-category').value = result.category;
    }

    // Auto populate location if extracted and empty
    if (result.location && !document.getElementById('form-location').value) {
      document.getElementById('form-location').value = result.location;
    }

    // Show preview box
    previewBox.style.display = 'block';
    document.getElementById('form-ai-cat-suggest').textContent = result.category;
    document.getElementById('form-ai-prio-suggest').textContent = result.suggested_priority;
    document.getElementById('form-ai-summary-suggest').textContent = result.summary;

    if (result.is_hazard) {
      document.getElementById('form-ai-hazard-alert').style.display = 'block';
      document.getElementById('form-ai-hazard-reason').textContent = result.hazard_reason;
    } else {
      document.getElementById('form-ai-hazard-alert').style.display = 'none';
    }

    showToast('Gemma analyzed your issue and suggested category & priority!', 'success');

  } catch (err) {
    showToast('AI analysis note: ' + err.message, 'info');
  } finally {
    aiBtn.disabled = false;
    aiBtn.innerHTML = `<span>✨ Auto-Analyze with Gemma AI</span>`;
  }
}

// Real-time Duplicate / Related Issue Search
function handleFormInputForDuplicates() {
  clearTimeout(relatedDebounceTimer);
  relatedDebounceTimer = setTimeout(async () => {
    const block = document.getElementById('form-block').value;
    const category = document.getElementById('form-category').value;
    const desc = document.getElementById('form-description').value.trim();

    if (!block || desc.length < 5) {
      document.getElementById('form-related-warning').style.display = 'none';
      return;
    }

    try {
      const related = await window.api.getRelatedComplaints(block, category, desc.slice(0, 30));
      const box = document.getElementById('form-related-warning');
      const list = document.getElementById('form-related-list');

      if (related && related.length > 0) {
        box.style.display = 'block';
        list.innerHTML = related.map(r => `
          <div style="background: #FFFFFF; border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 0.6rem 0.8rem; margin-top: 0.4rem; display: flex; align-items: center; justify-content: space-between;">
            <div>
              <strong>${escapeHtml(r.title)}</strong>
              <div style="font-size: 0.8rem; color: var(--color-text-secondary);">${r.location} • ${r.status} (${r.supporters_count} supporters)</div>
            </div>
            <button type="button" class="btn btn-secondary btn-sm" onclick="openComplaintModal('${r.id}')">View / Support</button>
          </div>
        `).join('');
      } else {
        box.style.display = 'none';
      }
    } catch (e) {
      // Non-blocking
    }
  }, 400);
}

// Complaint Form Submission
async function handleComplaintSubmit(e) {
  e.preventDefault();

  const title = document.getElementById('form-title').value.trim();
  const category = document.getElementById('form-category').value;
  const block = document.getElementById('form-block').value;
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
      location,
      description,
      duration: duration || null,
      run_ai: true
    };

    const created = await window.api.createComplaint(payload);

    showToast(`Complaint ${created.id} submitted successfully!`, 'success');
    document.getElementById('complaint-form').reset();
    document.getElementById('form-ai-preview').style.display = 'none';
    document.getElementById('form-related-warning').style.display = 'none';

    // Navigate to student dashboard
    switchView('student');

  } catch (err) {
    showToast('Failed to submit complaint: ' + err.message, 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Submit Complaint →';
  }
}

// HTML Escape helper
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// Search and Filter Listeners
function setupSearchAndFilters() {
  // Student Search
  const searchInput = document.getElementById('student-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      currentFilters.search = e.target.value;
      loadStudentDashboard();
    });
  }

  // Student Category Filter
  const catFilter = document.getElementById('student-filter-category');
  if (catFilter) {
    catFilter.addEventListener('change', (e) => {
      currentFilters.category = e.target.value;
      loadStudentDashboard();
    });
  }

  // Student Status Filter
  const statusFilter = document.getElementById('student-filter-status');
  if (statusFilter) {
    statusFilter.addEventListener('change', (e) => {
      currentFilters.status = e.target.value;
      loadStudentDashboard();
    });
  }

  // Student "My Complaints Only" toggle
  const mineToggle = document.getElementById('student-filter-mine');
  if (mineToggle) {
    mineToggle.addEventListener('change', (e) => {
      currentFilters.mine = e.target.checked;
      loadStudentDashboard();
    });
  }

  // Warden Filters
  const wardenSearch = document.getElementById('warden-search-input');
  if (wardenSearch) {
    wardenSearch.addEventListener('input', (e) => {
      currentFilters.search = e.target.value;
      loadWardenDashboard();
    });
  }

  const wardenBlock = document.getElementById('warden-filter-block');
  if (wardenBlock) {
    wardenBlock.addEventListener('change', (e) => {
      currentFilters.block = e.target.value;
      loadWardenDashboard();
    });
  }

  const wardenCat = document.getElementById('warden-filter-category');
  if (wardenCat) {
    wardenCat.addEventListener('change', (e) => {
      currentFilters.category = e.target.value;
      loadWardenDashboard();
    });
  }

  const wardenStatus = document.getElementById('warden-filter-status');
  if (wardenStatus) {
    wardenStatus.addEventListener('change', (e) => {
      currentFilters.status = e.target.value;
      loadWardenDashboard();
    });
  }
}

// Application Startup
document.addEventListener('DOMContentLoaded', async () => {
  await initUser();
  setupSearchAndFilters();

  // Attach Navigation Listeners
  document.querySelectorAll('[data-view-nav]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      const target = el.getAttribute('data-view-nav');
      switchView(target);
    });
  });

  // Attach Form Submit
  const form = document.getElementById('complaint-form');
  if (form) {
    form.addEventListener('submit', handleComplaintSubmit);
  }

  // Attach Form Input Duplicate Search
  const descInput = document.getElementById('form-description');
  if (descInput) {
    descInput.addEventListener('input', handleFormInputForDuplicates);
  }
  const blockSelect = document.getElementById('form-block');
  if (blockSelect) {
    blockSelect.addEventListener('change', handleFormInputForDuplicates);
  }

  // Attach AI Assist button
  const aiBtn = document.getElementById('form-ai-btn');
  if (aiBtn) {
    aiBtn.addEventListener('click', handleAIAssist);
  }

  // Close modal on click outside
  const modal = document.getElementById('complaint-detail-modal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeComplaintModal();
    });
  }

  // Initial view is Landing
  switchView('landing');
});
