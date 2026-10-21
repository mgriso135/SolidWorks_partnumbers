# Requirements — RIC (Regole in Cloud) as a Coding Layer between SolidWorks PDM and ERP

**Status:** Draft for review
**Source of truth:** Public Nuovamacut documentation (product page, blog article, webinar page) + assumptions explicitly marked as such
**Last updated:** 2026-10-20

---

## 0. Important clarification about the product

The customer describes RIC as "a middleware that lives between SolidWorks PDM (Vault) and the ERP". The public documentation does **not** describe it that way.

Nuovamacut positions **RIC — Regole in Cloud** as a **cloud-based assisted-coding (codifica assistita) product**. It centralizes a company's item/document coding rules and exposes them inside the tools people already use (CAD, PDM, PLM, Office, etc.), so that codes and document attributes are generated consistently with company standards.

In practice, for this customer, RIC can be understood as a **coding and metadata-consistency layer** sitting alongside the PDM ↔ ERP integration. It is not documented as a general-purpose bidirectional ERP synchronization middleware. Requirements below distinguish:

- **[DOC]** — stated by Nuovamacut public documentation.
- **[INF]** — inferred/assumed for the customer's PDM + ERP scenario; must be confirmed with the customer and vendor.
- **[OPEN]** — unknown, to be clarified.

---

## 1. Purpose and scope

### 1.1 Purpose
Define the functional and non-functional requirements for using RIC to ensure that item/document codes and attributes created in SolidWorks PDM are coherent with company coding standards and with the ERP item master, avoiding duplicates and manual re-keying.

### 1.2 In scope
- Central definition and management of coding rules.
- Assisted generation and validation of codes for CAD/PDM/ERP-bound items.
- Population/validation of document metadata (e.g., PDM data-card variables) from the same rules.
- Integration with SolidWorks PDM and the ERP item master.
- Multi-user, multi-department, distributed collaboration.
- Administration, auditing, and change management of rules.

### 1.3 Out of scope
- Replacing SolidWorks PDM as the CAD data vault.
- Replacing the ERP as the item/BOM master.
- Full BOM synchronization, routing, or manufacturing-order management.
- CAD geometry creation or editing.
- Supplier portal / procurement workflows beyond code generation and lookup.

---

## 2. System context

| Actor / system | Role |
|---|---|
| Design engineer | Creates parts/assemblies/drawings; needs a valid code and metadata before check-in. |
| PDM administrator | Configures PDM data cards, variables, workflows, and the RIC integration. |
| ERP/master-data owner | Owns item master conventions; must approve coding rules. |
| RIC administrator | Defines and maintains coding rules in the cloud. |
| SolidWorks PDM (Vault) | Source of truth for CAD files and document metadata; triggers code requests. |
| ERP | Source of truth for released item codes, descriptions, and item attributes. |
| RIC cloud service | Rule engine, code generator, metadata provider, integration endpoints. |
| RIC desktop app / web portal | User-facing interfaces for rule management and assisted coding. |
| Other CAD/PLM/Office tools | Optional consumers of the same coding rules. |

### 2.1 Logical flow

```
Engineer
   │  (1) create new part / document
   ▼
SolidWorks PDM ──(2) request code + attributes──▶ RIC cloud (rules) ◀──(3) rule management── RIC admin
   │                                                    │
   │                                                    └──(4) duplicate / validity check──▶ ERP item master
   │◀────────(5) code + validated attributes───────────┘
   │
   └──(6) check-in with code and metadata ──▶ ERP integration / item creation
```

---

## 3. Functional requirements

### 3.1 Coding rule management

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-01 | The system MUST provide a central repository of company coding rules, accessible in the cloud. | Must | [DOC] |
| FR-02 | Authorized users MUST be able to create, edit, version, activate/deactivate, and retire coding rules autonomously, without vendor intervention. | Must | [DOC] "create e gestite in completa autonomia" |
| FR-03 | Rules MUST support multi-segment / "speaking" codes (e.g., type + material + size + progressive number) composed from controlled values and free values. | Must | [DOC] "codici parlanti", examples |
| FR-04 | Rules MUST support fixed literals, separators, date/time components, and progressive counters. | Must | [INF] |
| FR-05 | Rules MUST support conditional logic (e.g., different patterns per document type, department, customer, or project). | Must | [INF] |
| FR-06 | The system SHOULD support validation rules (allowed characters, length, regex, mandatory fields, cross-field constraints). | Must | [INF] |
| FR-07 | Rule changes MUST be traceable (who, when, before/after) and SHOULD support rollback. | Should | [INF] |
| FR-08 | The system SHOULD allow rules to be tested/previewed against sample inputs before activation. | Should | [INF] |
| FR-09 | Rule sets MUST be scoped by company/tenant and MAY be scoped by department, document type, or PDM vault. | Must | [INF] |

### 3.2 Assisted code generation

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-10 | The system MUST generate codes consistent with the applicable company standard. | Must | [DOC] |
| FR-11 | The system MUST guarantee uniqueness of generated codes within the configured scope. | Must | [DOC] "codici univoci" |
| FR-12 | Code generation MUST be available from inside the user's working application, without switching context or re-keying data. | Must | [DOC] "in simbiosi", "trasparente" |
| FR-13 | The system SHOULD present guided choices (pick-lists, suggestions) derived from rule definitions. | Must | [DOC] "suggerirti codici" |
| FR-14 | The system MUST validate user-entered codes against the active rules and reject/flag non-conforming codes. | Must | [INF] |
| FR-15 | The system SHOULD detect near-duplicates and existing codes before assignment, including codes already present in PDM and ERP. | Must | [INF] for the customer's goal |
| FR-16 | The system SHOULD support "make vs. buy" logic: generate a new code for a new manufactured item, but reuse/look up an existing ERP code for standard purchased components. | Should | [OPEN] |
| FR-17 | The system MUST return deterministic results for the same inputs and rule version (reproducibility). | Should | [INF] |

### 3.3 Metadata / attribute population

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-18 | The system MUST assist in populating document attributes according to company standards, independently of the PDM used. | Must | [DOC] |
| FR-19 | For SolidWorks PDM, the system MUST be able to populate/validate data-card variables (e.g., code, description, material, type, revision) before check-in. | Must | [INF] |
| FR-20 | Attributes MUST be derived from the same rule definitions used for code generation, so code and metadata cannot diverge. | Must | [DOC]/[INF] |
| FR-21 | The system MUST be able to suggest a file name consistent with the coding rules. | Must | [DOC] |
| FR-22 | The system SHOULD carry a stable correlation key (RIC code / external ID) to link the PDM document to the ERP item. | Must | [INF] |
| FR-23 | The system MUST NOT overwrite existing released metadata without explicit user/admin confirmation. | Must | [INF] |

### 3.4 Integrations

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-24 | The system MUST integrate with SolidWorks PDM, including data-card/variable population and code assignment. | Must | [DOC] |
| FR-25 | The system MUST expose an integration mechanism usable by the ERP or by the PDM↔ERP integration layer (API or equivalent). | Must | [INF] |
| FR-26 | The system SHOULD provide connectors/plug-ins for the CAD/PDM/PLM tools listed by the vendor (SolidWorks, CATIA, Inventor, Solid Edge, Creo, SpaceClaim, Onshape, Rhino, SketchUp, SolidWorks PDM, Vault, Windchill, Teamcenter, 3DEXPERIENCE, etc.). | Should | [DOC] |
| FR-27 | The system SHOULD integrate with Office applications (Excel, Word, PowerPoint) for consistent naming. | Could | [DOC] |
| FR-28 | Integration MUST degrade gracefully (clear error, no partial/invalid write) when PDM, ERP, or cloud connectivity is unavailable. | Must | [INF] |
| FR-29 | The system MUST support a desktop app in addition to the web interface, so it can interact with locally installed CAD/PDM clients. | Must | [DOC] "esiste anche l'App desktop" |
| FR-30 | ERP integration MUST distinguish read-only lookup (existing item) from write (new item proposal) and respect ERP ownership of the item master. | Must | [INF] |

### 3.5 Collaboration and access

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-31 | The system MUST be usable by geographically distributed teams over an internet connection. | Must | [DOC] |
| FR-32 | The system MUST support multiple departments using the same centralized rules. | Must | [DOC] |
| FR-33 | The system SHOULD allow controlled use by external collaborators/suppliers. | Should | [DOC] |
| FR-34 | The system MUST provide authentication and role-based authorization (admin, rule editor, standard user, read-only). | Must | [DOC] login exists; roles [INF] |
| FR-35 | The system SHOULD support SSO/identity-provider integration. | Could | [OPEN] |
| FR-36 | Concurrent users MUST not be able to obtain the same progressive code (atomic counter). | Must | [INF] |

### 3.6 Traceability and audit

| ID | Requirement | Priority | Source |
|---|---|---|---|
| FR-37 | The system MUST log code generation events (user, timestamp, rule version, inputs, result). | Should | [INF] |
| FR-38 | The system SHOULD expose an audit/history view for administrators. | Should | [INF] |
| FR-39 | Generated codes and metadata MUST be traceable through the item lifecycle (design → release → ERP). | Should | [DOC] "tracciare il flusso", [INF] |

---

## 4. Non-functional requirements

| ID | Requirement | Priority |
|---|---|---|
| NFR-01 | Cloud service reachable over HTTPS; no inbound VPN required for distributed users. | Must |
| NFR-02 | Authentication with encrypted transport; credentials never stored in plain text. | Must |
| NFR-03 | Role-based access control and tenant isolation. | Must |
| NFR-04 | Audit logs retained per company policy. | Should |
| NFR-05 | GDPR-compliant handling of user data; data-processing agreement with vendor. | Must |
| NFR-06 | Availability target agreed with vendor (e.g., 99.5% monthly) and documented maintenance windows. | Must [OPEN] |
| NFR-07 | Code generation response time acceptable for interactive CAD/PDM use (target < 2 s, p95). | Must [INF] |
| NFR-08 | Graceful offline behavior: clear message and no data corruption; queueing optional. | Must |
| NFR-09 | Scalability to the customer's user count, item volume, and rule complexity. | Must [OPEN] |
| NFR-10 | Backup and restore of rule definitions and generation history. | Must [INF] |
| NFR-11 | Localization: Italian UI at minimum; English desirable. | Should [OPEN] |
| NFR-12 | Compatibility with the customer's SolidWorks PDM version and Windows clients; version matrix documented. | Must [OPEN] |
| NFR-13 | Upgrade path that does not break active PDM data cards or rule sets. | Must [INF] |
| NFR-14 | Vendor support/SLA and escalation process defined. | Must [OPEN] |

---

## 5. SolidWorks PDM–specific requirements

| ID | Requirement | Priority |
|---|---|---|
| PDM-01 | Code request and attribute population must work at file creation and at check-in. | Must |
| PDM-02 | Integration must respect PDM workflows/transitions (e.g., only request a code in the "New" state). | Must |
| PDM-03 | Data-card variables must be mapped explicitly to RIC outputs (field mapping documented and configurable). | Must |
| PDM-04 | The integration must not break PDM's own uniqueness/serial-number features; responsibilities must be documented. | Must |
| PDM-05 | The solution must handle configurations, derived documents (drawings, PDFs, STEP) and non-CAD documents according to rules. | Should |
| PDM-06 | Test environment (vault copy) must be available before production rollout. | Must |

---

## 6. Assumptions and open questions

### 6.1 Assumptions
1. RIC remains the system of record for **coding rules**, not for item master data.
2. SolidWorks PDM remains the system of record for CAD documents and their metadata.
3. The ERP remains the system of record for released items, descriptions, and BOMs.
4. The customer already has (or will build) a PDM↔ERP integration; RIC supplies consistent codes/attributes to it.
5. Internet connectivity is available to all users who need RIC.

### 6.2 Open questions
1. **[OPEN]** Does RIC expose a documented public API/webhook, or is integration only through vendor-supplied plug-ins?
2. **[OPEN]** Which exact SolidWorks PDM version and edition (Standard/Professional) is in use?
3. **[OPEN]** Which ERP is used, and does it accept item creation via API/file/queue?
4. **[OPEN]** Is bidirectional synchronization required, or only code/metadata generation at creation time?
5. **[OPEN]** How are existing/legacy codes migrated and validated against the new rules?
6. **[OPEN]** Is offline operation required (e.g., remote plant, supplier)?
7. **[OPEN]** What are the licensing model, trial terms, data residency, and exit/export options?
8. **[OPEN]** Who is authoritative when PDM and ERP disagree on an item's attributes?

---

## 7. Acceptance criteria (high level)

1. A designer can create a new part in SolidWorks PDM and receive a rule-compliant, unique code without leaving the PDM client.
2. The PDM data card is populated consistently with the code, and non-conforming manual edits are blocked or flagged.
3. A duplicate code present in PDM or ERP is detected before assignment.
4. A rule change by the administrator is reflected in code generation without a software release, and is audited.
5. Concurrent users never receive the same progressive code.
6. A distributed user can use the service over the internet with the assigned role.
7. Failure of RIC, PDM, or ERP connectivity produces a clear error and no partial/invalid data.
8. The complete flow (code generation → PDM check-in → ERP item) is demonstrable end-to-end in a test environment.

---

## 8. Sources

- Nuovamacut — Regole in Cloud product page: https://www.nuovamacut.it/prodotto/ric-regole-in-cloud/
- Nuovamacut blog — "Problemi di codifica? Risolvili con RIC – Regole in Cloud" (13 July 2022): https://www.nuovamacut.it/blog/come-risolvere-problemi-codifica/
- Nuovamacut — Webinar "Codifica assistita con Regole in Cloud (RIC)": https://www.nuovamacut.it/formazione/webinar-codifica-assistita-con-regole-in-cloud-ric-elimina-gli-errori-e-risparmia-tempo-prezioso/
- RIC login portal: https://regoleincloud.nuovamacut.it/#/login

> Public documentation is marketing-level; no technical/API documentation was found. Vendor clarification is required for all **[OPEN]** items.
