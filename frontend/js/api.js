// Hostlur API Client
class HostlurAPI {
  constructor() {
    this.currentUserId = localStorage.getItem('hostlur_user_id') || 'student-aarav';
  }

  setUserId(userId) {
    this.currentUserId = userId;
    localStorage.setItem('hostlur_user_id', userId);
  }

  getHeaders() {
    return {
      'Content-Type': 'application/json',
      'X-User-Id': this.currentUserId
    };
  }

  async request(endpoint, options = {}) {
    const config = {
      ...options,
      headers: {
        ...this.getHeaders(),
        ...(options.headers || {})
      }
    };

    try {
      const response = await fetch(endpoint, config);
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

  async getHealth() {
    return this.request('/api/health');
  }

  async getMe() {
    return this.request('/api/auth/me');
  }

  async getUsers() {
    return this.request('/api/users');
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

  async analyzeWithAI(description, block, location) {
    return this.request('/api/ai/analyze', {
      method: 'POST',
      body: JSON.stringify({
        description,
        hostel_block: block,
        location
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

  async toggleSupport(id) {
    return this.request(`/api/complaints/${id}/support`, {
      method: 'POST'
    });
  }
}

window.api = new HostlurAPI();
