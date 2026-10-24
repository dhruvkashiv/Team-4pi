// Hostlur API Client v2.0
class HostlurAPI {
  constructor() {
    this.token = localStorage.getItem('hostlur_token') || null;
    this.currentUserId = localStorage.getItem('hostlur_user_id') || null;
    // Configurable backend URL for production / external hosting (defaults to same-origin relative path)
    this.baseUrl = (window.HOSTLUR_CONFIG && window.HOSTLUR_CONFIG.API_URL)
      ? window.HOSTLUR_CONFIG.API_URL.replace(/\/$/, '')
      : '';
  }

  setSession(token, user) {
    this.token = token;
    this.currentUserId = user.id;
    localStorage.setItem('hostlur_token', token);
    localStorage.setItem('hostlur_user_id', user.id);
    localStorage.setItem('hostlur_user_role', user.role);
  }

  clearSession() {
    this.token = null;
    this.currentUserId = null;
    localStorage.removeItem('hostlur_token');
    localStorage.removeItem('hostlur_user_id');
    localStorage.removeItem('hostlur_user_role');
  }

  getHeaders() {
    const headers = {
      'Content-Type': 'application/json'
    };
    if (this.currentUserId) {
      headers['X-User-Id'] = this.currentUserId;
    }
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    return headers;
  }

  async request(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${this.baseUrl}${endpoint}`;
    const config = {
      ...options,
      headers: {
        ...this.getHeaders(),
        ...(options.headers || {})
      }
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || data.message || `HTTP ${response.status}`);
      }
      return data;
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      throw err;
    }
  }

  // --- Auth & User Profile ---
  async login(emailOrId, password, role) {
    const res = await this.request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email_or_id: emailOrId, password, role })
    });
    this.setSession(res.token, res.user);
    return res;
  }

  async logout() {
    try {
      await this.request('/api/auth/logout', { method: 'POST' });
    } catch (e) {
      // Ignore network error on logout
    }
    this.clearSession();
  }

  async getMe() {
    return this.request('/api/auth/me');
  }

  async getUsers() {
    return this.request('/api/users');
  }

  async changePassword(currentPassword, newPassword) {
    return this.request('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
    });
  }

  async updateProfile(profileData) {
    return this.request('/api/auth/profile', {
      method: 'PATCH',
      body: JSON.stringify(profileData)
    });
  }

  // --- Warden Student Management ---
  async getWardenStudents() {
    return this.request('/api/warden/students');
  }

  async createStudent(studentData) {
    return this.request('/api/warden/students', {
      method: 'POST',
      body: JSON.stringify(studentData)
    });
  }

  async resetStudentPassword(studentId) {
    return this.request(`/api/warden/students/${studentId}/reset-password`, {
      method: 'POST'
    });
  }

  // --- Image Upload ---
  async uploadImage(base64Data, filename = 'complaint.jpg') {
    return this.request('/api/upload', {
      method: 'POST',
      body: JSON.stringify({ image_data: base64Data, filename })
    });
  }

  // --- Complaints & AI ---
  async getHealth() {
    return this.request('/api/health');
  }

  async getStats() {
    return this.request('/api/stats');
  }

  async getComplaints(filters = {}) {
    const params = new URLSearchParams();
    if (filters.mine) params.append('mine', 'true');
    if (filters.category) params.append('category', filters.category);
    if (filters.status) params.append('status', filters.status);
    if (filters.block) params.append('block', filters.block);
    if (filters.priority) params.append('priority', filters.priority);
    if (filters.search) params.append('search', filters.search);

    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request(`/api/complaints${query}`);
  }

  async getRelatedComplaints(block, category, search) {
    const params = new URLSearchParams();
    params.append('block', block);
    if (category) params.append('category', category);
    if (search) params.append('q', search);
    return this.request(`/api/complaints/related?${params.toString()}`);
  }

  async getComplaint(id) {
    return this.request(`/api/complaints/${id}`);
  }

  async createComplaint(data) {
    return this.request('/api/complaints', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  async analyzeWithAI(description, block, location, imageData = null) {
    return this.request('/api/ai/analyze', {
      method: 'POST',
      body: JSON.stringify({
        description,
        hostel_block: block,
        location,
        image_data: imageData
      })
    });
  }

  async updateComplaintStatus(id, status, note, confirmedPriority) {
    return this.request(`/api/complaints/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({
        status,
        note,
        confirmed_priority: confirmedPriority
      })
    });
  }

  async verifyResolution(id, action, rating = null, feedback = null, reopenReason = null) {
    return this.request(`/api/complaints/${id}/verify-resolution`, {
      method: 'POST',
      body: JSON.stringify({
        action,
        rating,
        feedback,
        reopen_reason: reopenReason
      })
    });
  }

  async toggleSupport(id) {
    return this.request(`/api/complaints/${id}/support`, {
      method: 'POST'
    });
  }

  // --- Hostel Info ---
  async getContacts() {
    return this.request('/api/hostel/contacts');
  }

  async getMessTimings() {
    return this.request('/api/hostel/mess-timings');
  }

  async getMessMenu() {
    return this.request('/api/hostel/mess-menu');
  }

  async getCurfew() {
    return this.request('/api/hostel/curfew');
  }
}

window.api = new HostlurAPI();
