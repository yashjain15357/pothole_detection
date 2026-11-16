import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Download, 
  Mail, 
  Eye, 
  Filter, 
  Search, 
  RefreshCw, 
  Calendar,
  AlertTriangle,
  X,
  Send,
  Settings,
  CheckCircle2
} from 'lucide-react';
import { apiUrl, safeFetchJson } from '../apiConfig';

export default function ReportsTab({ selectedReportId, onClearSelectedReportId, onToast }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [minPotholes, setMinPotholes] = useState('');

  // Modals
  const [viewingReport, setViewingReport] = useState(null);
  const [viewingReportContent, setViewingReportContent] = useState('');
  const [contentLoading, setContentLoading] = useState(false);

  // Email modal
  const [emailModalReport, setEmailModalReport] = useState(null);
  const [recipientEmail, setRecipientEmail] = useState('');
  const [emailMessage, setEmailMessage] = useState('');
  const [sendingEmail, setSendingEmail] = useState(false);
  const [smtpStatus, setSmtpStatus] = useState({ configured: false, smtp_email: '' });
  const [showSmtpConfig, setShowSmtpConfig] = useState(false);
  const [smtpEmailInput, setSmtpEmailInput] = useState('');
  const [smtpPassInput, setSmtpPassInput] = useState('');
  const [savingSmtp, setSavingSmtp] = useState(false);

  const fetchSmtpStatus = async () => {
    try {
      const { response: res, data } = await safeFetchJson(apiUrl('/api/smtp-config'), { credentials: 'include' });
      if (res.ok && data.success) {
        setSmtpStatus(data);
        if (data.smtp_email) setSmtpEmailInput(data.smtp_email);
      }
    } catch (e) {
      console.error('Failed to load SMTP status:', e);
    }
  };

  const handleSaveSmtp = async (e) => {
    e.preventDefault();
    if (!smtpEmailInput || !smtpPassInput) {
      onToast('Email and Google App Password are required', 'error');
      return;
    }
    setSavingSmtp(true);
    try {
      const { response: res, data } = await safeFetchJson(apiUrl('/api/smtp-config'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          smtp_email: smtpEmailInput,
          smtp_app_password: smtpPassInput,
        }),
      });
      if (res.ok && data.success) {
        onToast('SMTP credentials saved successfully!', 'success');
        setSmtpStatus({ configured: true, smtp_email: smtpEmailInput });
        setShowSmtpConfig(false);
        setSmtpPassInput('');
      } else {
        onToast(data.error || 'Failed to save SMTP config', 'error');
      }
    } catch (err) {
      onToast('Failed to save SMTP config: ' + err.message, 'error');
    } finally {
      setSavingSmtp(false);
    }
  };

  const openEmailModal = (rep) => {
    setEmailModalReport(rep);
    setRecipientEmail('');
    setEmailMessage('');
    setShowSmtpConfig(false);
    fetchSmtpStatus();
  };

  const handleSendEmail = async (e) => {
    e.preventDefault();
    if (!emailModalReport || !recipientEmail) return;

    setSendingEmail(true);
    try {
      const { response: res, data } = await safeFetchJson(apiUrl('/send-report-email'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          report_id: emailModalReport.id,
          report_path: emailModalReport.path || '',
          report_name: emailModalReport.filename || `Report_${emailModalReport.id}`,
          recipient_email: recipientEmail,
          message: emailMessage,
        }),
      });

      if (res.ok && data.success) {
        onToast(`Report emailed to ${recipientEmail}!`, 'success');
        setEmailModalReport(null);
        setRecipientEmail('');
        setEmailMessage('');
      } else {
        onToast(data.error || 'Failed to send email. Check SMTP settings.', 'error');
      }
    } catch (err) {
      onToast('Error sending email: ' + err.message, 'error');
    } finally {
      setSendingEmail(false);
    }
  };

  const fetchReports = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterType) params.append('type', filterType);
      if (minPotholes) params.append('min_potholes', minPotholes);

      const url = `/api/dashboard/reports-filtered?${params.toString()}`;
      const { response: res, data } = await safeFetchJson(apiUrl(url), {
        headers: { 'Accept': 'application/json' },
        credentials: 'include',
      });
      if (res.ok && data.success) {
        setReports(data.reports || []);
      }
    } catch (err) {
      console.error('Failed to fetch reports:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [filterType, minPotholes]);

  // If opened from Dashboard
  useEffect(() => {
    if (selectedReportId) {
      openReportDetails({ id: selectedReportId });
      onClearSelectedReportId();
    }
  }, [selectedReportId]);

  const openReportDetails = async (rep) => {
    setViewingReport(rep);
    setContentLoading(true);
    setViewingReportContent('');

    try {
      const { response: res, data } = await safeFetchJson(apiUrl(`/report-by-id/${rep.id}`), {
        credentials: 'include'
      });
      if (res.ok && data.success) {
        setViewingReportContent(data.content || 'No content found.');
      } else {
        setViewingReportContent(data.error || 'Failed to read report content.');
      }
    } catch (err) {
      setViewingReportContent('Error loading report file: ' + err.message);
    } finally {
      setContentLoading(false);
    }
  };

  const filteredList = reports.filter((r) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    const nameMatch = (r.filename || '').toLowerCase().includes(q);
    const idMatch = String(r.id).includes(q);
    return nameMatch || idMatch;
  });

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a' }}>Inspection Reports Log</h2>
          <p style={{ color: '#64748b', fontSize: '0.9rem' }}>
            Browse historical detection reports, download PDFs, or dispatch to municipal teams
          </p>
        </div>

        <button onClick={fetchReports} className="btn btn-secondary">
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {/* Filter Bar */}
      <div className="card" style={{ marginBottom: '24px', padding: '16px 20px' }}>
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Search Box */}
          <div style={{ flex: '1 1 240px', position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '12px', color: '#94a3b8' }} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by report ID or filename..."
              style={{
                width: '100%',
                padding: '9px 12px 9px 36px',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                fontSize: '0.88rem',
              }}
            />
          </div>

          {/* Type Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Filter size={16} color="#64748b" />
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              style={{
                padding: '9px 14px',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                fontSize: '0.88rem',
                background: '#fff',
              }}
            >
              <option value="">All Source Types</option>
              <option value="image">Image Scans</option>
              <option value="video">Video Footage</option>
              <option value="camera">Live Camera</option>
            </select>
          </div>

          {/* Min Potholes */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={16} color="#64748b" />
            <input
              type="number"
              min="0"
              value={minPotholes}
              onChange={(e) => setMinPotholes(e.target.value)}
              placeholder="Min Potholes..."
              style={{
                width: '130px',
                padding: '9px 12px',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                fontSize: '0.88rem',
              }}
            />
          </div>
        </div>
      </div>

      {/* Reports Table */}
      <div className="card">
        <div className="table-responsive">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Filename / Name</th>
                <th>Potholes</th>
                <th>Unique Count</th>
                <th>Created At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '40px' }}>
                    <div className="spinner" style={{ margin: '0 auto', borderColor: '#cbd5e1', borderTopColor: '#4f46e5' }} />
                  </td>
                </tr>
              ) : filteredList.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', color: '#94a3b8', padding: '36px' }}>
                    No reports match the current criteria.
                  </td>
                </tr>
              ) : (
                filteredList.map((r) => (
                  <tr key={r.id}>
                    <td><strong>#{r.id}</strong></td>
                    <td>
                      <span className={`badge badge-${r.report_type}`}>
                        {r.report_type}
                      </span>
                    </td>
                    <td style={{ maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {r.filename || `Session_${r.id}`}
                    </td>
                    <td>
                      <span style={{ fontWeight: 700, color: (r.pothole_count || 0) > 0 ? '#ef4444' : '#10b981' }}>
                        {r.pothole_count ?? 0}
                      </span>
                    </td>
                    <td>{r.unique_potholes ?? '-'}</td>
                    <td>{r.created_at}</td>
                    <td>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button
                          onClick={() => openReportDetails(r)}
                          className="btn btn-secondary"
                          title="View Report Content"
                          style={{ padding: '6px 10px', fontSize: '0.78rem' }}
                        >
                          <Eye size={14} />
                        </button>

                        <a
                          href={apiUrl(`/download-report-pdf/${r.id}`)}
                          download
                          className="btn btn-secondary"
                          title="Download PDF"
                          style={{ padding: '6px 10px', fontSize: '0.78rem', textDecoration: 'none' }}
                        >
                          <Download size={14} /> PDF
                        </a>

                        <button
                          onClick={() => openEmailModal(r)}
                          className="btn btn-secondary"
                          title="Email Report"
                          style={{ padding: '6px 10px', fontSize: '0.78rem', color: '#4f46e5' }}
                        >
                          <Mail size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* View Report Modal */}
      {viewingReport && (
        <div className="modal-overlay">
          <div className="modal-dialog">
            <div className="modal-header">
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileText size={18} color="#4f46e5" />
                Report Details: #{viewingReport.id}
              </h3>
              <button
                onClick={() => setViewingReport(null)}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '1.2rem' }}
              >
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              {contentLoading ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
                  <div className="spinner" style={{ borderColor: '#cbd5e1', borderTopColor: '#4f46e5' }} />
                </div>
              ) : (
                <pre style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.85rem',
                  background: '#f8fafc',
                  padding: '16px',
                  borderRadius: '8px',
                  border: '1px solid #e2e8f0',
                  whiteSpace: 'pre-wrap',
                  maxHeight: '400px',
                  overflowY: 'auto',
                }}>
                  {viewingReportContent}
                </pre>
              )}
            </div>

            <div className="modal-footer">
              <a
                href={apiUrl(`/download-report-pdf/${viewingReport.id}`)}
                download
                className="btn btn-primary"
                style={{ textDecoration: 'none' }}
              >
                <Download size={16} /> Download PDF
              </a>
              <button onClick={() => setViewingReport(null)} className="btn btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Send Email Modal */}
      {emailModalReport && (
        <div className="modal-overlay">
          <div className="modal-dialog" style={{ maxWidth: '500px' }}>
            <div className="modal-header">
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Mail size={18} color="#4f46e5" />
                Email Report to Authorities
              </h3>
              <button
                onClick={() => setEmailModalReport(null)}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '1.2rem' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSendEmail}>
              <div className="modal-body">
                {/* SMTP Configuration Bar */}
                <div style={{
                  marginBottom: '16px',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  background: smtpStatus.configured ? '#f0fdf4' : '#fffbeb',
                  border: `1px solid ${smtpStatus.configured ? '#bbf7d0' : '#fde68a'}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '10px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem' }}>
                    {smtpStatus.configured ? (
                      <>
                        <CheckCircle2 size={16} color="#16a34a" />
                        <span><strong>Sender:</strong> {smtpStatus.smtp_email}</span>
                      </>
                    ) : (
                      <>
                        <AlertTriangle size={16} color="#d97706" />
                        <span style={{ color: '#b45309' }}>SMTP sender not yet configured</span>
                      </>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowSmtpConfig(!showSmtpConfig)}
                    className="btn btn-secondary"
                    style={{ padding: '4px 8px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    <Settings size={12} /> {showSmtpConfig ? 'Hide Settings' : 'Configure SMTP'}
                  </button>
                </div>

                {/* Collapsible SMTP Credentials Form */}
                {showSmtpConfig && (
                  <div style={{
                    marginBottom: '18px',
                    padding: '14px',
                    borderRadius: '8px',
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                  }}>
                    <h4 style={{ fontSize: '0.88rem', fontWeight: 700, marginBottom: '10px', color: '#1e293b' }}>
                      SMTP Sender Settings
                    </h4>
                    <div style={{ marginBottom: '10px' }}>
                      <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: '4px' }}>
                        Sender Gmail Address
                      </label>
                      <input
                        type="email"
                        value={smtpEmailInput}
                        onChange={(e) => setSmtpEmailInput(e.target.value)}
                        placeholder="yourname@gmail.com"
                        style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.85rem' }}
                      />
                    </div>
                    <div style={{ marginBottom: '10px' }}>
                      <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, marginBottom: '4px' }}>
                        Google App Password (16 characters)
                      </label>
                      <input
                        type="password"
                        value={smtpPassInput}
                        onChange={(e) => setSmtpPassInput(e.target.value)}
                        placeholder="abcd efgh ijkl mnop"
                        style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '0.85rem' }}
                      />
                      <small style={{ color: '#64748b', fontSize: '0.72rem', display: 'block', marginTop: '3px' }}>
                        Generate at: <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer" style={{ color: '#4f46e5' }}>myaccount.google.com/apppasswords</a>
                      </small>
                    </div>
                    <button
                      type="button"
                      disabled={savingSmtp}
                      onClick={handleSaveSmtp}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.8rem', padding: '6px 14px' }}
                    >
                      {savingSmtp ? 'Saving...' : 'Save Credentials'}
                    </button>
                  </div>
                )}

                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
                    Recipient Email Address *
                  </label>
                  <input
                    type="email"
                    required
                    value={recipientEmail}
                    onChange={(e) => setRecipientEmail(e.target.value)}
                    placeholder="e.g. municipal.works@city.gov"
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      border: '1px solid #cbd5e1',
                      fontSize: '0.9rem',
                    }}
                  />
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px' }}>
                    Custom Message (Optional)
                  </label>
                  <textarea
                    rows={4}
                    value={emailMessage}
                    onChange={(e) => setEmailMessage(e.target.value)}
                    placeholder="Urgent road repair required at this location..."
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      border: '1px solid #cbd5e1',
                      fontSize: '0.9rem',
                    }}
                  />
                </div>

                <div style={{ background: '#f8fafc', padding: '10px 12px', borderRadius: '8px', fontSize: '0.8rem', color: '#64748b' }}>
                  Report attached: <strong>#{emailModalReport.id} ({emailModalReport.report_type})</strong>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  onClick={() => setEmailModalReport(null)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={sendingEmail}
                  className="btn btn-primary"
                >
                  {sendingEmail ? <div className="spinner" /> : <><Send size={16} /> Send via SMTP</>}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
