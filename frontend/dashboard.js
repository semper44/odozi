// Fetch metrics from your Django endpoint: /api/dashboard/results/?run_id=123
const response = await fetch(`/api/dashboard/results/?run_id=${run_id}`);
const scan = await response.json();

// 1. Draw your high-level Traffic Light KPI Metrics Cards instantly
document.getElementById("status-badge").innerText = scan.status.toUpperCase();
document.getElementById("status-badge").style.color = scan.status === 'passed' ? 'green' : 'red';
document.getElementById("loc-counter").innerText = `Lines Analyzed: ${scan.lines_of_code}`;
document.getElementById("issue-counter").innerText = `Issues Found: ${scan.total_issues}`;

// 2. Clear out any old spinner views
const container = document.getElementById("findings-list-holder");
container.innerHTML = "";

if (scan.structured_findings.length === 0) {
    container.innerHTML = `<div class="empty-shield">🟢 Clean Scan! No issues found.</div>`;
} else {
    // 3. Render clean, uniform issue cards for any tool findings
    scan.structured_findings.forEach(issue => {
        container.innerHTML += `
            <div class="issue-card ${issue.severity.toLowerCase()}">
                <div class="issue-header">
                    <strong>[${issue.severity}] ${issue.name}</strong> 
                    <span>Line ${issue.line}</span>
                </div>
                <p>File: ${issue.file}</p>
                <p class="msg">${issue.message}</p>
            </div>
        `;
    });
}
