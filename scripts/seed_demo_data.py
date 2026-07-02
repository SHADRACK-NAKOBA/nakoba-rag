"""
scripts/seed_demo_data.py
Seeds the vector store with realistic IT Operations demo data
so you can test RAG queries without live source systems.

Run: python scripts/seed_demo_data.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rag.vectorstore.store import Document
from rag.retrieval.retriever import get_retriever


DEMO_DOCS = [
    # ── ServiceNow Incidents ──────────────────────────────────────────────────
    Document(
        content=(
            "Incident INC0041823\n"
            "Summary: SSO login failures affecting Corporate Applications Production\n"
            "Description: Users unable to authenticate via Azure AD SSO. Error: SAML assertion validation failed. "
            "Affecting approximately 400 users in Corp Apps Production GCP. Root cause: Certificate expired on IdP. "
            "Resolution: Renewed IdP certificate and restarted SSO service. Duration: 2h 15m.\n"
            "Priority: 1 | State: Resolved | CI: sso-service-prod | Opened: 2026-03-12"
        ),
        source_system="servicenow", doc_type="incident",
        source_url="https://servicenow.example.com/incident/INC0041823",
        timestamp="2026-03-12T09:00:00Z",
        rbac_tags=["l1_support", "l2_support", "l3_support", "it_admin"],
        entity_refs=["sso-service-prod", "azure-ad", "corp-apps-prod"],
    ),
    Document(
        content=(
            "Incident INC0039215\n"
            "Summary: SSO outage — Okta SAML token misconfiguration after change\n"
            "Description: Post-change SSO failure affecting all Okta-integrated apps. "
            "Change CHG0018734 introduced incorrect ACS URL. 600 users affected. "
            "Resolved by rolling back CHG0018734. Duration: 45 minutes.\n"
            "Priority: 1 | State: Resolved | CI: okta-prod | Opened: 2025-11-04"
        ),
        source_system="servicenow", doc_type="incident",
        source_url="https://servicenow.example.com/incident/INC0039215",
        timestamp="2025-11-04T14:00:00Z",
        rbac_tags=["l1_support", "l2_support", "l3_support", "it_admin"],
        entity_refs=["okta-prod", "sso-service-prod"],
    ),
    Document(
        content=(
            "Incident INC0037890\n"
            "Summary: SSO intermittent failures — network latency to IdP endpoints\n"
            "Description: Intermittent SSO authentication failures due to network latency spikes "
            "between Corp Apps GCP and on-prem IdP. Affecting 15% of login attempts. "
            "Resolution: Added Cloud Interconnect redundancy path.\n"
            "Priority: 2 | State: Resolved | CI: network-interconnect | Opened: 2025-09-18"
        ),
        source_system="servicenow", doc_type="incident",
        source_url="https://servicenow.example.com/incident/INC0037890",
        timestamp="2025-09-18T11:00:00Z",
        rbac_tags=["l1_support", "l2_support", "l3_support", "it_admin"],
        entity_refs=["sso-service-prod", "network-interconnect"],
    ),
    Document(
        content=(
            "Incident INC0035100\n"
            "Summary: Complete SSO outage — DNS resolution failure\n"
            "Description: All SSO authentication failed due to DNS resolution failure for IdP domain. "
            "Internal DNS servers lost forwarder configuration after maintenance window. "
            "Duration: 3h 40m. 1200+ users affected.\n"
            "Priority: 1 | State: Resolved | CI: dns-prod | Opened: 2025-07-22"
        ),
        source_system="servicenow", doc_type="incident",
        source_url="https://servicenow.example.com/incident/INC0035100",
        timestamp="2025-07-22T08:00:00Z",
        rbac_tags=["l1_support", "l2_support", "l3_support", "it_admin"],
        entity_refs=["sso-service-prod", "dns-prod"],
    ),

    # ── CMDB ─────────────────────────────────────────────────────────────────
    Document(
        content=(
            "CRM Systems in Enterprise:\n"
            "1. Salesforce CRM — Primary enterprise CRM. Serves: Patient Services, Revenue Cycle, "
            "Sales Operations, Marketing. Environment: Production SaaS. Owner: Business Applications team.\n"
            "2. Salesforce Health Cloud — Clinical relationship management. Serves: Clinical Operations, "
            "Care Coordination. Integrated with: Epic EMR, ServiceNow.\n"
            "3. Microsoft Dynamics 365 — Secondary CRM for Supply Chain and Vendor Management. "
            "Serves: Procurement, Vendor Relations. On-prem deployment on vmware-cluster-02.\n"
            "LeanIX Application Registry — last updated 2026-05-01."
        ),
        source_system="leanix", doc_type="cmdb",
        source_url="https://leanix.example.com/apps/crm-systems",
        timestamp="2026-05-01T00:00:00Z",
        rbac_tags=["l1_support", "l2_support", "l3_support", "it_admin", "finance"],
        entity_refs=["salesforce-crm", "dynamics-365", "health-cloud"],
    ),
    Document(
        content=(
            "CI: sso-service-prod\n"
            "Class: Application Service | Environment: Production\n"
            "IP: 10.20.5.100 | Cluster: gke-corp-apps-prod\n"
            "Owner: Platform Engineering | Support Group: IAM Operations\n"
            "Description: Central SSO service (Okta + Azure AD) for all Corporate Applications. "
            "Integrates with 47 downstream applications. SLA: 99.99%\n"
            "Dependencies: okta-prod, azure-ad-tenant, dns-prod, network-interconnect\n"
            "Applications served: Salesforce, ServiceNow, Jira, Confluence, GitLab, 42 others."
        ),
        source_system="servicenow", doc_type="cmdb",
        source_url="https://servicenow.example.com/cmdb/sso-service-prod",
        timestamp="2026-06-01T00:00:00Z",
        rbac_tags=["l1_support", "l2_support", "l3_support", "it_admin"],
        entity_refs=["sso-service-prod", "okta-prod", "azure-ad"],
    ),
    Document(
        content=(
            "Operating Systems deployed in Production (as of 2026-06-01):\n"
            "RHEL 8.6: 847 servers (38%) — Primary server OS, Enterprise Support until 2029\n"
            "RHEL 9.2: 312 servers (14%) — Migration target for new deployments\n"
            "Ubuntu 22.04 LTS: 623 servers (28%) — GKE node pools, Kubernetes workloads\n"
            "Windows Server 2019: 284 servers (13%) — Legacy .NET apps, Active Directory\n"
            "Windows Server 2022: 89 servers (4%) — New Windows deployments\n"
            "RHEL 7.9: 67 servers (3%) — EOL — tracked in tech debt register\n"
            "Total managed nodes: 2,222 | Source: Puppet Enterprise inventory"
        ),
        source_system="puppet", doc_type="config",
        source_url="https://puppet.example.com/nodes/inventory",
        timestamp="2026-06-01T00:00:00Z",
        rbac_tags=["l1_support", "l2_support", "l3_support", "it_admin"],
        entity_refs=["puppet-prod", "rhel-nodes"],
    ),

    # ── Confluence KB ─────────────────────────────────────────────────────────
    Document(
        content=(
            "How to Submit a Vulnerability Exception Request\n\n"
            "Process Overview:\n"
            "Vulnerability exceptions are required when a known vulnerability cannot be remediated "
            "within the standard SLA (Critical: 7 days, High: 30 days, Medium: 90 days).\n\n"
            "Step 1: Log into PolicyHub at https://policyhub.example.com\n"
            "Step 2: Navigate to Risk Management → Exception Requests → New Request\n"
            "Step 3: Select vulnerability from Tenable or Wiz scan (paste CVE ID or scan finding ID)\n"
            "Step 4: Complete the Business Justification field — explain why remediation is delayed\n"
            "Step 5: Specify a compensating control (e.g., WAF rule, network segmentation)\n"
            "Step 6: Select exception duration (max 90 days; extensions require CISO approval)\n"
            "Step 7: Submit — your manager and the Security team will be notified for approval\n\n"
            "Approval Chain: Manager → Security Operations → CISO (for exceptions > 30 days)\n"
            "SLA: Approvals within 5 business days.\n"
            "Contact: security-exceptions@example.com or #security-help Slack channel."
        ),
        source_system="confluence", doc_type="kb_article",
        source_url="https://confluence.example.com/pages/vulnerability-exception-process",
        timestamp="2026-04-15T00:00:00Z",
        rbac_tags=["l1_support", "l2_support", "l3_support", "developer", "it_admin"],
        entity_refs=["policyhub", "tenable", "wiz"],
    ),
    Document(
        content=(
            "Reggie Production System — Architecture Overview\n\n"
            "Reggie is the dialysis center operations management platform.\n"
            "GCP Project: prod-reggie-operations | Region: us-central1\n\n"
            "Current System Variabilities and Known Issues (as of 2026-06-01):\n"
            "1. Memory leak in reggie-scheduler pod — occurs every 72h, requires restart. "
            "Tracked: JIRA OPS-4821. ETA for fix: 2026-07-15.\n"
            "2. Database connection pool exhaustion during peak hours (6-8am). "
            "Tracked: JIRA OPS-4756. Mitigation: PgBouncer tuning applied 2026-05-20.\n"
            "3. Batch job latency spikes on month-end billing runs. "
            "Root cause: shared cloud SQL instance. Tracked: JIRA OPS-4612.\n"
            "4. Occasional 502 errors from ingress controller during deployments — 0.3% error rate.\n\n"
            "Support Group: Reggie Platform Team | On-call: #reggie-oncall Slack"
        ),
        source_system="confluence", doc_type="kb_article",
        source_url="https://confluence.example.com/pages/reggie-production-overview",
        timestamp="2026-06-01T00:00:00Z",
        rbac_tags=["l1_support", "l2_support", "l3_support", "it_admin"],
        entity_refs=["reggie-prod", "reggie-scheduler", "prod-reggie-operations"],
    ),
    Document(
        content=(
            "Legacy MCP Authorization Dependencies\n\n"
            "Legacy MCP (Model Context Protocol v1, internal auth middleware) is deprecated "
            "as of 2025-01-01. Migration deadline: 2026-12-31.\n\n"
            "Applications still directly depending on Legacy MCP for Authorization:\n"
            "1. LabResults Portal (lab-portal-prod) — Migration: Q3 2026\n"
            "2. Pharmacy Integration Gateway (pharmacy-gw) — Migration: Q4 2026\n"
            "3. Patient Check-in Kiosk (kiosk-app) — Migration: Q3 2026\n"
            "4. Legacy Billing Export Service (billing-export-v1) — Migration: Q4 2026\n"
            "5. HR Benefits Portal (hr-benefits) — Migration: Q2 2026 (in progress)\n"
            "6. Vendor Portal (vendor-portal) — Migration: Q3 2026\n"
            "7. Compliance Reporting Tool (compliance-report) — Migration: Q1 2027 (exception approved)\n\n"
            "Total: 7 applications | Source: LeanIX Application Registry | Last updated: 2026-05-15"
        ),
        source_system="leanix", doc_type="cmdb",
        source_url="https://leanix.example.com/capabilities/legacy-mcp-dependencies",
        timestamp="2026-05-15T00:00:00Z",
        rbac_tags=["l1_support", "l2_support", "l3_support", "developer", "it_admin"],
        entity_refs=["legacy-mcp", "lab-portal-prod", "pharmacy-gw", "kiosk-app"],
    ),
]


async def main():
    print("🌱 Seeding demo data into vector store...")
    retriever = get_retriever()
    retriever.ingest(DEMO_DOCS)
    store = retriever._store
    count = store.count() if hasattr(store, "count") else len(DEMO_DOCS)
    print(f"✅ Seeded {len(DEMO_DOCS)} documents → {count} total in store")
    print("\nYou can now ask questions like:")
    print("  • How many SSO outages were there in the last year?")
    print("  • What CRM systems exist and what do they serve?")
    print("  • How many apps depend on Legacy MCP?")
    print("  • Where do I submit a vulnerability exception?")
    print("  • What OS versions are deployed in production?")
    print("  • What are the current variabilities of Reggie Production?")


if __name__ == "__main__":
    asyncio.run(main())