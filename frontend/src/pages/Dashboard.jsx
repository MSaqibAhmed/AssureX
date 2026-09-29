import { useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { useResource, ResourceState } from '../api/hooks';
import { Badge, Button, Card, PageHeader } from '../components/ui';
import { claimLink } from './Claims';
export default function Dashboard() {
  const { role, user } = useSelector((s) => s.app.session);
  const resource = useResource('/dashboard');
  const recent = useResource('/reports?limit=5&sort=newest');
  const notices = useResource('/notifications?limit=4');
  const queue =
    role === 'customer'
      ? '/claims'
      : role === 'service'
        ? '/service/queue'
        : role === 'reviewer'
          ? '/review'
          : '/reports';
  const counts = resource.data?.claim_counts || {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const open = total - (counts.Approved || 0) - (counts.Rejected || 0) - (counts.Closed || 0);
  return (
    <>
      <PageHeader
        eyebrow="ASSUREX / CLAIM OPERATIONS"
        title={`Welcome back, ${user.name.split(' ')[0]}`}
        description="Your evidence, analysis and decisions. One clear workspace."
      >
        {role === 'customer' && (
          <Button to="/products/new" variant="secondary">
            Register product
          </Button>
        )}
        <Button
          to={
            role === 'customer' ? '/claims/new' : role === 'service' ? '/service/claims/new' : queue
          }
        >
          {['customer', 'service'].includes(role) ? 'New claim' : 'Open claim queue'}
        </Button>
      </PageHeader>
      <ResourceState resource={resource}>
        <div className="bento-grid">
          <Card className="bento-wide workspace-intro">
            <div>
              <span className="eyebrow">EVIDENCE-LED CLAIM MANAGEMENT</span>
              <h2>
                A clear path from claim
                <br />
                to decision.
              </h2>
              <p>
                Submit the facts. Verify the evidence. Compare independent analysis and track the
                authorized decision.
              </p>
            </div>
            <Link to={queue}>Explore your claims →</Link>
          </Card>
          <Card title="Open claims">
            <div className="metric-number">{open}</div>
            <p className="metric-caption">Drafts, processing and awaiting review</p>
            <Link to={queue}>View workspace →</Link>
          </Card>
          <Card title="Pending information">
            <div className="metric-number">{counts['Additional Information Required'] || 0}</div>
            <p className="metric-caption">Claims needing additional details</p>
            <Link to={`${queue}?status=Additional%20Information%20Required`}>
              Review next steps →
            </Link>
          </Card>
          <Card title="Product coverage">
            <div className="metric-number">{resource.data?.registered_products ?? 0}</div>
            <p>Registered products</p>
            <div className="list-row">
              <span>Active warranties</span>
              <strong>{resource.data?.active_warranties ?? 0}</strong>
            </div>
            <div className="list-row">
              <span>Approaching expiry</span>
              <strong>{resource.data?.expiring_warranties ?? 0}</strong>
            </div>
            <p className="metric-caption">Provider coverage recorded in AssureX</p>
          </Card>
          <Card
            title="Claim activity"
            subtitle={`${total} claims · current status distribution`}
            className="bento-wide"
          >
            {total ? (
              Object.entries(counts).map(([status, count]) => (
                <div className="distribution-row" key={status}>
                  <span>{status}</span>
                  <div className="distribution-track">
                    <span style={{ width: `${(count / total) * 100}%` }} />
                  </div>
                  <strong>{count}</strong>
                </div>
              ))
            ) : (
              <p>No claims yet. Activity will appear after your first draft.</p>
            )}
          </Card>
          <Card title="Human decisions">
            <div className="metric-number">{(counts.Approved || 0) + (counts.Rejected || 0)}</div>
            <div className="list-row">
              <Badge status="Approved" />
              <strong>{counts.Approved || 0}</strong>
            </div>
            <div className="list-row">
              <Badge status="Rejected" />
              <strong>{counts.Rejected || 0}</strong>
            </div>
            <p className="metric-caption">AI recommendations are advisory, not approvals.</p>
          </Card>
          <Card
            title="Recent claims"
            className="bento-wide"
            action={<Link to={queue}>View all →</Link>}
          >
            <ResourceState resource={recent}>
              {recent.data?.items.map((c) => (
                <div className="list-row" key={c.id}>
                  <div>
                    <Link to={claimLink(c.id, role)}>{c.public_claim_id}</Link>
                    <small>
                      {new Date(c.created_at).toLocaleDateString()} ·{' '}
                      {c.facts?.fault_category || 'Draft details'}
                    </small>
                  </div>
                  <Badge status={c.status} />
                </div>
              ))}
              {recent.data?.total === 0 && <p>No claims in your workspace yet.</p>}
            </ResourceState>
          </Card>
          <Card
            title="Updates & next actions"
            className="bento-wide"
            action={<Link to="/notifications">View updates →</Link>}
          >
            <ResourceState resource={notices}>
              {notices.data?.items.map((n) => (
                <div className="list-row" key={n.id}>
                  <Link to={`/reports/claims/${n.claim_id}`}>
                    {n.event_type.replaceAll('_', ' ')}
                  </Link>
                  <small>{n.read ? 'Read' : 'Unread'}</small>
                </div>
              ))}
              {notices.data?.total === 0 && (
                <p>You’re up to date. Claim updates will appear here.</p>
              )}
            </ResourceState>
            <p className="metric-caption">
              {resource.data?.saved_documents ?? 0} supporting documents securely stored.
            </p>
          </Card>
        </div>
      </ResourceState>
    </>
  );
}
