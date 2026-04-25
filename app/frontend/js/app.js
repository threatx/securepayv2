/**
 * SecurePay Frontend - Fraud Analyzer
 */

let similarityChart = null;

/**
 * Main analysis function - called when user clicks Analyze
 */
async function analyzeQuery() {
    const queryInput = document.getElementById('query-input');
    const analyzeBtn = document.getElementById('analyze-btn');
    const btnText = analyzeBtn.querySelector('.btn-text');
    const spinner = analyzeBtn.querySelector('.spinner');
    const resultsSection = document.getElementById('results-section');
    const errorSection = document.getElementById('error-section');

    const query = queryInput.value.trim();

    // Validation
    if (query.length < 10) {
        showError('Please describe the situation in more detail (at least 10 characters).');
        return;
    }

    // Show loading state
    btnText.textContent = 'Analyzing...';
    spinner.classList.remove('hidden');
    analyzeBtn.disabled = true;
    resultsSection.classList.add('hidden');
    errorSection.classList.add('hidden');
    document.getElementById('patterns-section').classList.add('hidden');

    try {
        const response = await fetch('/api/analyze/multi-signal', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                top_k: 5
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Analysis failed');
        }

        const data = await response.json();
        displayResults(data);

    } catch (error) {
        showError(error.message || 'An error occurred during analysis.');
    } finally {
        // Reset button state
        btnText.textContent = 'Analyze';
        spinner.classList.add('hidden');
        analyzeBtn.disabled = false;
    }
}

/**
 * Display extracted patterns (mechanisms, red flags, type)
 */
function displayExtractedPatterns(patterns) {
    const section = document.getElementById('patterns-section');
    const container = document.getElementById('patterns-container');

    if (!patterns || (!patterns.type && !patterns.mechanisms?.length && !patterns.red_flags?.length)) {
        section.classList.add('hidden');
        return;
    }

    section.classList.remove('hidden');

    let html = '<div class="pattern-groups">';

    // Type
    if (patterns.type) {
        html += `
            <div class="pattern-group">
                <h4>Scam Type</h4>
                <span class="tag type" title="${patterns.type.id}">${patterns.type.name}</span>
            </div>
        `;
    }

    // Mechanisms
    if (patterns.mechanisms?.length) {
        html += `
            <div class="pattern-group">
                <h4>Mechanisms Detected</h4>
                <div class="tag-list">
                    ${patterns.mechanisms.map(m => `
                        <span class="tag mechanism" title="${escapeHtml(m.description || m.id)}">
                            ${escapeHtml(m.name)}
                        </span>
                    `).join('')}
                </div>
            </div>
        `;
    }

    // Red Flags
    if (patterns.red_flags?.length) {
        html += `
            <div class="pattern-group">
                <h4>Red Flags Detected</h4>
                <div class="tag-list">
                    ${patterns.red_flags.map(rf => `
                        <span class="tag red-flag" title="${escapeHtml(rf.description || rf.id)}">
                            ${escapeHtml(rf.name)}
                        </span>
                    `).join('')}
                </div>
            </div>
        `;
    }

    html += '</div>';
    container.innerHTML = html;
}

/**
 * Display the analysis results
 */
function displayResults(data) {
    const resultsSection = document.getElementById('results-section');
    const casesContainer = document.getElementById('cases-container');
    const analysisContainer = document.getElementById('analysis-container');

    // Clear previous results
    casesContainer.innerHTML = '';
    analysisContainer.innerHTML = '';

    // Display extracted patterns first
    if (data.extracted_patterns) {
        displayExtractedPatterns(data.extracted_patterns);
    }

    // Adapt multi-signal results to case format
    let cases = [];
    if (data.results && data.results.length > 0) {
        // New multi-signal format
        cases = data.results.map((r, i) => ({
            rank: i + 1,
            similarity: r.score,
            similarity_pct: `${Math.round(r.score * 100)}%`,
            fraud_type: r.scenario_type || [],
            content_preview: r.preview || r.summary || '',
            full_content: r.preview || '',
            breakdown: r.breakdown,
            scenario_id: r.scenario_id
        }));
    } else if (data.retrieved_cases && data.retrieved_cases.length > 0) {
        // Original format fallback
        cases = data.retrieved_cases;
    }

    // Display retrieved cases
    if (cases.length > 0) {
        cases.forEach((caseData, index) => {
            const caseCard = createCaseCard(caseData, index);
            casesContainer.appendChild(caseCard);
        });

        // Create similarity chart
        createSimilarityChart(cases);
    } else {
        casesContainer.innerHTML = '<p class="no-results">No similar cases found.</p>';
    }

    // Display analysis
    const analysisDiv = document.createElement('div');
    analysisDiv.className = 'analysis-content';
    analysisDiv.innerHTML = formatAnalysis(data.analysis);
    analysisContainer.appendChild(analysisDiv);

    // Show results section
    resultsSection.classList.remove('hidden');

    // Scroll to patterns section first if visible, then results
    const patternsSection = document.getElementById('patterns-section');
    if (!patternsSection.classList.contains('hidden')) {
        patternsSection.scrollIntoView({ behavior: 'smooth' });
    } else {
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }
}

/**
 * Create a case card element
 */
function createCaseCard(caseData, index) {
    const card = document.createElement('div');
    card.className = 'case-card';
    card.id = `case-${index}`;

    const similarity = caseData.similarity;
    const similarityClass = getSimilarityClass(similarity);

    // Build breakdown HTML if available
    let breakdownHtml = '';
    if (caseData.breakdown) {
        const b = caseData.breakdown;
        breakdownHtml = `
            <div class="score-breakdown-container">
                <div class="score-breakdown">
                    <div class="bar canonical" style="width: ${b.canonical * 100}%"
                         title="Text: ${Math.round(b.canonical * 100)}%"></div>
                    <div class="bar type" style="width: ${b.type * 100}%"
                         title="Type: ${Math.round(b.type * 100)}%"></div>
                    <div class="bar mechanism" style="width: ${b.mechanism * 100}%"
                         title="Mechanism: ${Math.round(b.mechanism * 100)}%"></div>
                    <div class="bar red-flag" style="width: ${b.red_flag * 100}%"
                         title="Red Flag: ${Math.round(b.red_flag * 100)}%"></div>
                </div>
                <div class="breakdown-legend">
                    <span class="legend-item"><span class="dot canonical"></span>Text ${Math.round(b.canonical * 100)}%</span>
                    <span class="legend-item"><span class="dot type"></span>Type ${Math.round(b.type * 100)}%</span>
                    <span class="legend-item"><span class="dot mechanism"></span>Mech ${Math.round(b.mechanism * 100)}%</span>
                    <span class="legend-item"><span class="dot red-flag"></span>RF ${Math.round(b.red_flag * 100)}%</span>
                </div>
            </div>
        `;
    }

    card.innerHTML = `
        <div class="case-header" onclick="toggleCase(${index})">
            <div>
                <span class="case-rank">Case #${caseData.rank}</span>
                <span class="case-type">${formatFraudType(caseData.fraud_type)}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 1rem;">
                <span class="case-similarity ${similarityClass}">${caseData.similarity_pct}</span>
                <span class="case-expand-icon">&#9660;</span>
            </div>
        </div>
        ${breakdownHtml}
        <div class="case-content">
            <p>${escapeHtml(caseData.full_content)}</p>
        </div>
    `;

    return card;
}

/**
 * Toggle case card expansion
 */
function toggleCase(index) {
    const card = document.getElementById(`case-${index}`);
    card.classList.toggle('expanded');
}

/**
 * Get CSS class based on similarity score
 */
function getSimilarityClass(similarity) {
    if (similarity >= 0.6) return 'similarity-high';
    if (similarity >= 0.4) return 'similarity-medium';
    return 'similarity-low';
}

/**
 * Format fraud type array to string
 */
function formatFraudType(fraudType) {
    if (Array.isArray(fraudType)) {
        return fraudType.map(t => t.replace(/_/g, ' ')).join(', ');
    }
    return String(fraudType).replace(/_/g, ' ');
}

/**
 * Format analysis text with markdown-like formatting
 */
function formatAnalysis(analysis) {
    // Convert markdown bold to HTML
    let formatted = escapeHtml(analysis);
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Convert bullet points
    formatted = formatted.replace(/^- /gm, '&bull; ');
    formatted = formatted.replace(/^\* /gm, '&bull; ');

    // Convert numbered lists
    formatted = formatted.replace(/^(\d+)\. /gm, '<strong>$1.</strong> ');

    // Add line breaks
    formatted = formatted.replace(/\n/g, '<br>');

    return formatted;
}

/**
 * Create similarity bar chart
 */
function createSimilarityChart(cases) {
    const ctx = document.getElementById('similarity-chart').getContext('2d');

    // Destroy existing chart
    if (similarityChart) {
        similarityChart.destroy();
    }

    const labels = cases.map(c => `Case ${c.rank}`);
    const similarities = cases.map(c => (c.similarity * 100).toFixed(1));

    const backgroundColors = cases.map(c => {
        if (c.similarity >= 0.6) return 'rgba(34, 197, 94, 0.7)';
        if (c.similarity >= 0.4) return 'rgba(245, 158, 11, 0.7)';
        return 'rgba(239, 68, 68, 0.7)';
    });

    const borderColors = cases.map(c => {
        if (c.similarity >= 0.6) return 'rgb(34, 197, 94)';
        if (c.similarity >= 0.4) return 'rgb(245, 158, 11)';
        return 'rgb(239, 68, 68)';
    });

    similarityChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Similarity (%)',
                data: similarities,
                backgroundColor: backgroundColors,
                borderColor: borderColors,
                borderWidth: 2,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Similarity: ${context.raw}%`;
                        },
                        afterLabel: function(context) {
                            const caseData = cases[context.dataIndex];
                            return `Type: ${formatFraudType(caseData.fraud_type)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    },
                    title: {
                        display: true,
                        text: 'Similarity Score'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Retrieved Cases'
                    }
                }
            }
        }
    });
}

/**
 * Show error message
 */
function showError(message) {
    const errorSection = document.getElementById('error-section');
    const errorText = document.getElementById('error-text');
    const resultsSection = document.getElementById('results-section');
    const patternsSection = document.getElementById('patterns-section');

    errorText.textContent = message;
    errorSection.classList.remove('hidden');
    resultsSection.classList.add('hidden');
    patternsSection.classList.add('hidden');
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Allow pressing Enter in textarea to submit (with Ctrl/Cmd)
document.addEventListener('DOMContentLoaded', function() {
    const queryInput = document.getElementById('query-input');
    queryInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            analyzeQuery();
        }
    });
});
