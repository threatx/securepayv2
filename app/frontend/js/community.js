/**
 * Community Scam Reports Frontend
 */

let scamTypes = [];

document.addEventListener('DOMContentLoaded', init);

async function init() {
    setupTabs();
    setupEventListeners();
    await loadScamTypes();
    await loadStats();
    await loadSubmissions();
}

// --- Tab Switching ---

function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');

            if (btn.dataset.tab === 'browse') {
                loadSubmissions();
            }
        });
    });
}

// --- Event Listeners ---

function setupEventListeners() {
    document.getElementById('submit-btn').addEventListener('click', submitReport);
    document.getElementById('add-ioc-btn').addEventListener('click', addIOCRow);
    document.getElementById('search-btn').addEventListener('click', searchSubmissions);
    document.getElementById('clear-search-btn').addEventListener('click', () => {
        document.getElementById('search-input').value = '';
        loadSubmissions();
    });
    document.getElementById('search-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') searchSubmissions();
    });
    document.getElementById('filter-status').addEventListener('change', loadSubmissions);
    document.getElementById('filter-scam-type').addEventListener('change', loadSubmissions);

    // Modal close handlers
    document.getElementById('modal-close').addEventListener('click', closeReviewModal);
    document.getElementById('modal-cancel-btn').addEventListener('click', closeReviewModal);
    document.getElementById('review-modal').addEventListener('click', e => {
        if (e.target === document.getElementById('review-modal')) closeReviewModal();
    });
}

// --- Load Scam Types ---

async function loadScamTypes() {
    try {
        const response = await fetch('/api/review/taxonomies');
        if (!response.ok) return;
        const data = await response.json();
        scamTypes = data.scam_types || [];

        const selects = [document.getElementById('scam-type'), document.getElementById('filter-scam-type')];
        scamTypes.forEach(st => {
            selects.forEach(sel => {
                const opt = document.createElement('option');
                opt.value = st.type_id;
                opt.textContent = st.type_name.replace(/_/g, ' ');
                sel.appendChild(opt);
            });
        });
    } catch (err) {
        console.error('Failed to load scam types:', err);
    }
}

// --- Load Stats ---

async function loadStats() {
    try {
        const response = await fetch('/api/community/stats');
        if (!response.ok) return;
        const data = await response.json();
        document.getElementById('stat-total').textContent = data.total;
        document.getElementById('stat-pending').textContent = data.pending;
        document.getElementById('stat-verified').textContent = data.verified;
    } catch (err) {
        console.error('Failed to load stats:', err);
    }
}

// --- Submit Report ---

async function submitReport() {
    const desc = document.getElementById('incident-desc').value.trim();
    if (desc.length < 20) {
        alert('Please describe the scam in more detail (at least 20 characters).');
        return;
    }

    // Collect IOCs
    const iocs = [];
    document.querySelectorAll('.ioc-row').forEach(row => {
        const type = row.querySelector('.ioc-type').value;
        const value = row.querySelector('.ioc-value').value.trim();
        if (type && value) iocs.push({ type, value });
    });

    const body = {
        incident_description: desc,
        scam_type: document.getElementById('scam-type').value || null,
        loss_amount: parseFloat(document.getElementById('loss-amount').value) || null,
        iocs: iocs,
        submitter_alias: document.getElementById('submitter-alias').value.trim() || null
    };

    const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.textContent = 'Submitting...';

    try {
        const response = await fetch('/api/community/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: 'Submission failed' }));
            throw new Error(err.detail);
        }

        // Show success
        document.getElementById('submit-success').classList.remove('hidden');

        // Reset form
        document.getElementById('incident-desc').value = '';
        document.getElementById('scam-type').value = '';
        document.getElementById('loss-amount').value = '';
        document.getElementById('submitter-alias').value = '';
        document.getElementById('ioc-list').innerHTML = '';

        // Update stats
        await loadStats();

        // Hide success after 5 seconds
        setTimeout(() => {
            document.getElementById('submit-success').classList.add('hidden');
        }, 5000);

    } catch (err) {
        alert('Error: ' + err.message);
    }

    btn.disabled = false;
    btn.textContent = 'Submit Report';
}

// --- Dynamic IOC Rows ---

function addIOCRow() {
    const list = document.getElementById('ioc-list');
    const row = document.createElement('div');
    row.className = 'ioc-row';
    row.innerHTML = `
        <select class="ioc-type">
            <option value="upi_id">UPI ID</option>
            <option value="phone_number">Phone Number</option>
            <option value="url">URL</option>
            <option value="telegram_id">Telegram ID</option>
            <option value="email">Email</option>
            <option value="app_name">App Name</option>
        </select>
        <input type="text" class="ioc-value" placeholder="Enter value...">
        <button class="remove-ioc" title="Remove">x</button>
    `;
    row.querySelector('.remove-ioc').addEventListener('click', () => row.remove());
    list.appendChild(row);
}

// --- Browse Submissions ---

async function loadSubmissions() {
    const status = document.getElementById('filter-status').value;
    const scamType = document.getElementById('filter-scam-type').value;
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (scamType) params.append('scam_type', scamType);

    try {
        const response = await fetch(`/api/community/submissions?${params}`);
        if (!response.ok) throw new Error('Failed to load submissions');
        const data = await response.json();
        renderSubmissions(data.submissions, false);
    } catch (err) {
        document.getElementById('submissions-list').innerHTML =
            `<p class="no-results">Failed to load submissions.</p>`;
    }
}

// --- Semantic Search ---

async function searchSubmissions() {
    const query = document.getElementById('search-input').value.trim();
    if (query.length < 5) {
        alert('Search query must be at least 5 characters.');
        return;
    }

    const btn = document.getElementById('search-btn');
    btn.disabled = true;
    btn.textContent = 'Searching...';

    try {
        const response = await fetch('/api/community/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, top_k: 10 })
        });

        if (!response.ok) throw new Error('Search failed');
        const data = await response.json();
        renderSubmissions(data.results, true);
    } catch (err) {
        document.getElementById('submissions-list').innerHTML =
            `<p class="no-results">Search failed. Please try again.</p>`;
    }

    btn.disabled = false;
    btn.textContent = 'Find Similar';
}

// --- Render Submissions ---

function renderSubmissions(items, showSimilarity) {
    const container = document.getElementById('submissions-list');

    if (!items || items.length === 0) {
        container.innerHTML = '<p class="no-results">No submissions found.</p>';
        return;
    }

    container.innerHTML = items.map(s => {
        const date = s.submitted_at ? new Date(s.submitted_at).toLocaleDateString() : '';
        const typeLabel = s.scam_type ? s.scam_type.replace(/_/g, ' ') : '';
        const text = escapeHtml(s.incident_description || '');
        const truncated = text.length > 400 ? text.slice(0, 400) + '...' : text;

        let iocsHtml = '';
        if (s.iocs && s.iocs.length > 0) {
            const tags = s.iocs.map(ioc =>
                `<span class="ioc-tag">${escapeHtml(ioc.type)}: ${escapeHtml(ioc.value)}</span>`
            ).join('');
            iocsHtml = `<div class="ioc-tags">${tags}</div>`;
        }

        return `
            <div class="submission-card">
                <div class="submission-header">
                    <span class="status-badge ${s.status}">${s.status}</span>
                    ${typeLabel ? `<span class="type-badge">${typeLabel}</span>` : ''}
                    ${showSimilarity && s.similarity ? `<span class="similarity-badge">${(s.similarity * 100).toFixed(0)}% match</span>` : ''}
                    <span class="submission-date">${date}</span>
                </div>
                <p class="submission-text">${truncated}</p>
                <div class="submission-meta">
                    ${s.loss_amount ? `<span>Loss: &#8377;${s.loss_amount.toLocaleString()}</span>` : ''}
                    ${s.submitter_alias ? `<span>By: ${escapeHtml(s.submitter_alias)}</span>` : ''}
                    ${s.iocs && s.iocs.length > 0 ? `<span>${s.iocs.length} IOC(s)</span>` : ''}
                </div>
                ${iocsHtml}
                ${s.status === 'pending' ? `<button class="review-btn" data-id="${s.submission_id}">Review</button>` : ''}
            </div>
        `;
    }).join('');

    container.querySelectorAll('.review-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const item = items.find(i => i.submission_id === btn.dataset.id);
            if (item) openReviewModal(item);
        });
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// --- Review Modal ---

function openReviewModal(s) {
    document.getElementById('modal-status-badge').textContent = s.status;
    document.getElementById('modal-status-badge').className = `status-badge ${s.status}`;

    const typeBadge = document.getElementById('modal-type-badge');
    typeBadge.textContent = s.scam_type ? s.scam_type.replace(/_/g, ' ') : '';
    typeBadge.style.display = s.scam_type ? '' : 'none';

    document.getElementById('modal-date').textContent =
        s.submitted_at ? new Date(s.submitted_at).toLocaleDateString() : '';
    document.getElementById('modal-description').textContent = s.incident_description || '';
    document.getElementById('modal-loss').textContent =
        s.loss_amount ? `Loss: \u20b9${s.loss_amount.toLocaleString()}` : '';
    document.getElementById('modal-alias').textContent =
        s.submitter_alias ? `By: ${s.submitter_alias}` : '';

    const iocsEl = document.getElementById('modal-iocs');
    iocsEl.innerHTML = (s.iocs || []).map(ioc =>
        `<span class="ioc-tag">${escapeHtml(ioc.type)}: ${escapeHtml(ioc.value)}</span>`
    ).join('');

    document.getElementById('modal-verify-btn').onclick = () => submitReview(s.submission_id, 'verified');
    document.getElementById('modal-reject-btn').onclick = () => submitReview(s.submission_id, 'rejected');

    document.getElementById('review-modal').classList.remove('hidden');
}

function closeReviewModal() {
    document.getElementById('review-modal').classList.add('hidden');
}

async function submitReview(submission_id, status) {
    const verifyBtn = document.getElementById('modal-verify-btn');
    const rejectBtn = document.getElementById('modal-reject-btn');
    verifyBtn.disabled = true;
    rejectBtn.disabled = true;

    try {
        const res = await fetch(`/api/community/review/${submission_id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });
        if (!res.ok) throw new Error('Failed to update');

        closeReviewModal();
        await loadSubmissions();
        await loadStats();
    } catch (err) {
        alert('Failed to update status. Please try again.');
    } finally {
        verifyBtn.disabled = false;
        rejectBtn.disabled = false;
    }
}
