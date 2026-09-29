import { useState } from 'react';
import { NavLink, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useResource, ResourceState, ErrorMessage, Pagination } from '../api/hooks';
import { DocumentLibrary, ServiceRecords, PolicyPicker } from './Records';
import { ArrowRight, Package, ShieldCheck, Pencil, Plus } from 'lucide-react';
import './products.css';
import { Badge, Button, Card, Empty, KeyValues, Input, PageHeader, Select } from '../components/ui';

function productTitle(product) {
  return product.name || `${product.brand} ${product.model}`;
}
function formatDate(value) {
  if (!value) return 'Not recorded';
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}
function formatAmount(value) {
  return value == null || value === ''
    ? 'Not recorded'
    : Number(value).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
export function ProductList() {
  const [page, setPage] = useState(1);
  const resource = useResource(`/products?page=${page}`);
  return (
    <>
      <PageHeader
        eyebrow="A HOME FOR YOUR PRODUCTS"
        title="The things you care about."
        description="Manage your products, warranties and service history."
      >
        <Button to="/products/new">Add product</Button>
      </PageHeader>
      <ResourceState resource={resource}>
        <div className="product-grid">
          {resource.data?.items.map((p) => (
            <Card key={p.id} className="product-card">
              <div className="product-card-top">
                <span className="product-symbol">
                  <Package size={22} aria-hidden="true" />
                </span>
                <Badge status={p.category} />
              </div>
              <div className="product-card-title">
                <p className="product-brand">{p.brand}</p>
                <h2>{productTitle(p)}</h2>
                <p>{p.model}</p>
              </div>
              <dl className="product-serial">
                <dt>Serial number</dt>
                <dd>{p.serial || 'Not recorded'}</dd>
              </dl>
              <div className="product-card-purchase">
                <span>Purchased</span>
                <strong>{formatDate(p.purchase_date)}</strong>
              </div>
              <Button
                to={`/products/${p.id}`}
                className="product-view"
                aria-label={`View product: ${productTitle(p)}`}
              >
                View product <ArrowRight size={17} aria-hidden="true" />
              </Button>
            </Card>
          ))}
        </div>
        {resource.data?.total === 0 && (
          <Card>
            <Empty
              title="Your products belong here"
              description="Add your first product to keep its warranty, documents and service history together."
              action={
                <Button to="/products/new" icon={Plus}>
                  Add product
                </Button>
              }
            />
          </Card>
        )}
        <Pagination page={page} total={resource.data?.total || 0} onChange={setPage} />
      </ResourceState>
    </>
  );
}
export function ProductForm() {
  const { id } = useParams();
  const resource = useResource(id ? `/products/${id}` : null);
  return (
    <>
      <PageHeader title={id ? 'Edit product' : 'Register your product'} back="/products" />
      <ResourceState resource={resource}>
        <ProductEditor key={resource.data?.id || 'new'} product={resource.data} />
      </ResourceState>
    </>
  );
}
function ProductEditor({ product }) {
  const navigate = useNavigate();
  const today = new Date().toISOString().slice(0, 10);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const p = product
        ? await api.patch(`/products/${product.id}`, values)
        : await api.post('/products', values);
      navigate(`/products/${p.id}`);
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title="Product details">
      <form onSubmit={save}>
        <div className="form-grid">
          {[
            ['Product name', 'name'],
            ['Retailer', 'retailer'],
            ['Brand', 'brand'],
            ['Model', 'model'],
            ['Serial number', 'serial'],
          ].map(([label, name]) => (
            <Input
              key={name}
              label={label}
              name={name}
              defaultValue={product?.[name]}
              required
              maxLength={100}
            />
          ))}
          <Select
            label="Category"
            name="category"
            options={['mobile', 'electronics', 'appliances']}
            defaultValue={product?.category || 'mobile'}
          />
          <Input
            label="Purchase date"
            name="purchase_date"
            type="date"
            max={today}
            defaultValue={product?.purchase_date}
            required
          />
          <Input
            label="Purchase amount"
            name="amount"
            type="number"
            min="0"
            step="0.01"
            defaultValue={product?.amount}
            required
          />
        </div>
        <ErrorMessage error={error} />
        <div className="form-actions">
          <Button type="submit" disabled={busy}>
            {busy ? 'Saving…' : 'Save product'}
          </Button>
        </div>
      </form>
    </Card>
  );
}
export function ProductDetail() {
  const { id, tab } = useParams();
  const resource = useResource(`/products/${id}`);
  const p = resource.data;
  const activeTab = tab || 'overview';
  return (
    <ResourceState resource={resource}>
      {p && (
        <div className="product-detail">
          <PageHeader
            eyebrow="YOUR PRODUCT"
            title={productTitle(p)}
            description="Your product details, coverage and records in one place."
            back="/products"
          >
            <Button to={`/products/${id}/edit`} variant="secondary" icon={Pencil}>
              Edit product
            </Button>
          </PageHeader>
          <div className="product-detail-layout">
            <div className="product-detail-main">
              <Card className="product-summary">
                <div className="product-card-top">
                  <span className="product-symbol">
                    <Package size={24} aria-hidden="true" />
                  </span>
                  <Badge status={p.category} />
                </div>
                <p className="product-brand">{p.brand}</p>
                <h2>{productTitle(p)}</h2>
                <p className="product-model">Model · {p.model}</p>
                <dl className="product-serial">
                  <dt>Serial number</dt>
                  <dd>{p.serial || 'Not recorded'}</dd>
                </dl>
                <div className="product-purchase-summary">
                  <div>
                    <span>Purchase amount</span>
                    <strong>{formatAmount(p.amount)}</strong>
                  </div>
                  <div>
                    <span>Purchase date</span>
                    <strong>{formatDate(p.purchase_date)}</strong>
                  </div>
                  <div>
                    <span>Retailer</span>
                    <strong>{p.retailer || 'Not recorded'}</strong>
                  </div>
                </div>
              </Card>
              <nav className="tabs product-tabs" aria-label="Product sections">
                {[
                  ['overview', 'Overview'],
                  ['warranty', 'Warranty'],
                  ['documents', 'Documents'],
                  ['history', 'Service history'],
                ].map(([value, label]) => (
                  <NavLink
                    key={value}
                    to={`/products/${id}/${value}`}
                    className={activeTab === value ? 'active' : ''}
                    aria-current={activeTab === value ? 'page' : undefined}
                  >
                    {label}
                  </NavLink>
                ))}
              </nav>
              <div className="product-tab-content">
                {activeTab === 'documents' ? (
                  <DocumentLibrary productId={id} />
                ) : activeTab === 'history' ? (
                  <ServiceRecords productId={id} />
                ) : activeTab === 'warranty' ? (
                  <Warranty id={id} />
                ) : (
                  <Card
                    title="Product information"
                    subtitle="The details saved when you registered this product."
                  >
                    <KeyValues
                      items={[
                        ['Product name', productTitle(p)],
                        ['Brand', p.brand],
                        ['Model', p.model],
                        ['Category', p.category],
                        ['Serial number', p.serial],
                        ['Retailer', p.retailer || 'Not recorded'],
                      ]}
                    />
                  </Card>
                )}
              </div>
            </div>
            <aside className="product-detail-aside" aria-label="Coverage and support">
              {activeTab !== 'warranty' && <Warranty id={id} />}
              <Card
                className="product-support"
                title="Need help with this product?"
                subtitle="Start a claim to add evidence and have your issue reviewed."
              >
                <Button to={`/claims/new?product=${id}`} className="product-view">
                  Start claim <ArrowRight size={17} aria-hidden="true" />
                </Button>
                <p>Keep your receipt and product serial number handy.</p>
              </Card>
            </aside>
          </div>
        </div>
      )}
    </ResourceState>
  );
}
function Warranty({ id }) {
  const resource = useResource(`/products/${id}/warranty`);
  const warranty = resource.data;
  const missing = resource.error?.status === 404;
  return (
    <Card
      className="product-warranty"
      title="Warranty coverage"
      subtitle="Your recorded manufacturer or provider warranty."
    >
      <span className="product-symbol">
        <ShieldCheck size={24} aria-hidden="true" />
      </span>
      {missing ? (
        <p>No warranty registered. Add your existing coverage to keep the details close at hand.</p>
      ) : (
        <ResourceState resource={resource}>
          {warranty && (
            <>
              <div className="product-warranty-provider">
                <h3>{warranty.provider}</h3>
                <Badge status={warranty.status} />
              </div>
              <KeyValues
                items={[
                  ['Coverage starts', formatDate(warranty.start_date)],
                  ['Coverage ends', formatDate(warranty.expiry_date)],
                  ['Policy reference', warranty.policy_version_id],
                ]}
              />
            </>
          )}
        </ResourceState>
      )}
      {(missing || warranty) && (
        <Button
          to={`/products/${id}/warranty/edit`}
          variant="secondary"
          className="product-view"
          icon={missing ? Plus : Pencil}
        >
          {missing ? 'Add warranty' : 'Edit warranty'}
        </Button>
      )}
    </Card>
  );
}
export function WarrantyForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const resource = useResource(`/products/${id}/warranty`);
  const product = useResource(`/products/${id}`);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await api.patch(`/products/${id}/warranty`, values);
      navigate(`/products/${id}/warranty`);
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  if (resource.loading) return <p role="status">Loading warranty…</p>;
  if (resource.error && resource.error.status !== 404) return <ResourceState resource={resource} />;
  return (
    <>
      <PageHeader
        title="Existing warranty coverage"
        description="Record the manufacturer's or provider's existing warranty. AssureX does not issue coverage."
        back={`/products/${id}`}
      />
      <Card>
        <form onSubmit={save}>
          <div className="form-grid">
            <Input
              label="Warranty provider"
              name="provider"
              defaultValue={resource.data?.provider}
              required
            />
            <PolicyPicker
              category={product.data?.category}
              initial={resource.data?.policy_version_id}
            />
            <Input
              label="Coverage start"
              name="start_date"
              type="date"
              defaultValue={resource.data?.start_date}
              required
            />
            <Input
              label="Coverage expiry"
              name="expiry_date"
              type="date"
              defaultValue={resource.data?.expiry_date}
              required
            />
          </div>
          <ErrorMessage error={error} />
          <Button disabled={busy}>{busy ? 'Saving…' : 'Save warranty'}</Button>
        </form>
      </Card>
    </>
  );
}
export function DocumentForm() {
  return <DocumentLibrary />;
}
export function Receipts() {
  return <DocumentForm />;
}
