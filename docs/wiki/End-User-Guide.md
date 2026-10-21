# PartCode end-user guide

PartCode is your company's part-numbering service. It applies the approved
coding rules for parts, assemblies, drawings, and other documents, and gives
each one a unique code.

PartCode does **not** store CAD files, manage revisions, or replace your PDM or
ERP. SOLIDWORKS PDM remains the source of truth for files and data cards; the
ERP remains the source of truth for released items and BOMs. PartCode is the
single authority for **how a code is built** and **which progressive numbers
have already been used**.

This guide is for everyone who uses the web application and, where installed,
the SOLIDWORKS PDM add-in.

---

## 1. Roles and permissions

Your administrator assigns one of these roles:

| Role | What you can do |
|---|---|
| **Viewer** | View rules, generate codes, search the code registry, and view the dashboard. |
| **Editor** | Everything a viewer can do, plus create/edit/archive rules, edit code links and metadata, void codes, and read the audit log. |
| **Admin** | Everything an editor can do, plus manage users and API keys. |

If a menu item is missing, your role does not include that function.

---

## 2. Signing in

1. Open the PartCode address provided by your administrator. That may be a
   public URL such as `https://partcode.example.com/app/` or a LAN address such
   as `http://192.168.1.249:7000/app/`.
2. Enter your company email address and password.
3. Select **Sign in**.

Your browser keeps the session for the lifetime of the access token (12 hours
by default). When it expires, sign in again. Use the sign-out button at the
bottom-left of the navigation panel when you finish, especially on a shared
computer.

There is no public registration and no self-service password reset in this
version. Ask your administrator if you need an account or a password change.

> **Demo accounts:** if the login page shows demo email addresses, they only
> work when the server was started with demo data. In a normal production
> deployment those shortcuts are not valid; use your own credentials.

---

## 3. The main screens

| Screen | Purpose |
|---|---|
| **Dashboard** | Recent activity, number of active rules, codes generated, and codes by source. |
| **Generate code** | The guided form that previews and reserves a new code. |
| **Coding rules** | The list of numbering rules. Editors and admins can open the rule editor here. |
| **Code registry** | Every code ever reserved, with its rule version, status, source, and external reference. |
| **Audit log** | Who did what and when. Visible to editors and admins. |
| **Users & API keys** | Account and machine-credential management. Visible to admins only. |
| **API docs** | Technical reference for integrations. You do not need it for normal web use. |

---

## 4. Key concepts

### 4.1 Coding rules

A **rule** describes how one kind of code is assembled. For example:

```text
PRT-MEC-00001
```

could be produced by a rule with this meaning:

```text
PRT  -  MEC  -  00001
 |      |         |
fixed  family    progressive number
```

Each rule has:

- A **name**, such as "Mechanical part".
- A stable **key**, such as `mechanical-part`. Integrations use this key.
- A **document type**, such as part, assembly, or drawing.
- A **version**, which increases every time the rule is saved.
- A **status**: `active`, `draft`, or `archived`.

Only **active** rules appear in the Generate code screen.

### 4.2 Rule versions

Rule changes are never applied retroactively:

- Saving an edited active rule creates a **new version** and archives the
  previous active version.
- Codes already generated keep the version they were created with.
- A **draft** rule can be prepared without becoming available for generation.
- An **archived** rule can no longer generate new codes, but its existing codes
  remain valid and searchable.

This makes historical codes reproducible: the registry records the exact rule
version used.

### 4.3 Segments

A rule is an ordered list of **segments**, read from left to right:

| Segment | What it adds | Example |
|---|---|---|
| **Literal** | Fixed text. | `PRT` |
| **Separator** | Fixed punctuation between parts. | `-` |
| **List** | One value chosen from a controlled list. | `MEC` (Mechanical) |
| **Text** | Free text with optional length and format checks. | `BRACKET` |
| **Date** | A date formatted when the code is generated. PartCode uses UTC. | `26` for the year 2026 with `%y` |
| **Counter** | A progressive number, zero-padded to the configured width. | `00001` |
| **Checksum** | A calculated verification number. | `mod97` or Luhn |

### 4.4 Preview, reserve, and the counter

The Generate code screen has two different actions:

- **Preview** shows what the next code would be. It does **not** consume a
  number and does not change the registry.
- **Generate & reserve** commits the code. It increments the counter, saves the
  code in the registry, and records who generated it and from which rule
  version.

Because the preview does not reserve anything, the final code can differ if a
colleague generates a code first. Always use the code shown after you press
**Generate & reserve**, not an earlier preview.

Numbers are never reused. If a generation attempt fails after the counter has
advanced, that number can be skipped. This is intentional: a gap is safer than
two items sharing a code.

### 4.5 Counter scope

The counter can work in two ways:

- **One counter for the whole rule** — every code from that rule shares one
  sequence: `PRT-MEC-00001`, `PRT-ELE-00002`, `PRT-MEC-00003`.
- **A separate counter per combination of fields** — each family has its own
  sequence: `PRT-MEC-00001`, `PRT-ELE-00001`, `PRT-MEC-00002`.

The rule editor shows which fields key the counter when the second option is
used.

### 4.6 Code status

| Status | Meaning |
|---|---|
| **Reserved** | The number has been allocated to an item and is saved in the registry. This is the status produced by the web application and the PDM add-in. |
| **Void** | The code is kept for history and audit but must not be used. An editor or admin can void a reserved code. |
| **Committed** | A status reserved for ERP reconciliation. The current web application does not set it automatically. |

---

## 5. Generate a code

This is the normal workflow for an engineer creating a new item.

1. Open **Generate code**.
2. Choose the rule that matches the document you are creating. The screen
   shows the rule description and its format.
3. Fill in the fields:
   - **List fields** are shown as option buttons. Select exactly one.
   - **Text fields** are typed. The hint shows the allowed length or, for
     patterned fields, the required format.
   - Optional fields can be left empty.
4. Optionally fill **Link and metadata**:
   - **External reference** links the code to a PDM file or ERP object. Leave
     it empty for a standalone code. An active reference can belong to only one
     item.
   - **Notes** stores a short internal note with the item.
   - **Metadata (JSON)** adds attributes such as material, description, or
     supplier. It must be a JSON object.
5. Watch the **Preview** panel. It updates automatically when all required
   fields are valid. Each piece of the proposed code is shown as a separate
   chip.
6. Check that the proposed code is correct, then select
   **Generate & reserve**.
7. The success panel shows the final code. Use **Copy** for the code, **Open
   registry** to see the saved record, or **New code** to start another.

Important:

- The preview is not a reservation.
- Use the final code from the success panel, not a copied preview.
- If the preview says a rule is unavailable, the rule may be draft or archived.
  Ask an editor or administrator to activate it.
- If a field is rejected, correct it using the message shown below the field.
  Validation happens again on the server when you generate.
- If the generated code would exceed the rule's maximum length, shorten the
  text field or ask an administrator to review the rule.
- If the external reference is already used by an active item, the server
  returns a duplicate-reference error showing the existing code. Void the old
  item first only if you really intend to move the link.
- Rule fields take precedence over metadata with the same key.

---

## 6. Find and inspect a code

Open **Code registry**.

- Type in the search box to search by code or by external reference. The search
  is case-insensitive for lookup.
- Use the status filter to show reserved, committed, or void codes.
- Select a row to open its details.

The detail panel shows:

- The code and its status.
- The rule key and the exact rule version used.
- The source (`web`, `pdm`, or another integration label).
- The creation date, external reference, and notes.
- The metadata stored with the code, such as family, description, or material.

Use **Copy code** to put the code on the clipboard.

### What "item" means

A generated code is already an item. PartCode does not create a separate part
record afterwards; the **Code registry** is the list of items. The `source`
column shows where the code came from (`web` for the browser, `pdm` for the
add-in), and the **external reference** column is the link to a PDM file or ERP
object.

You can set the external reference while generating a code, or edit it later in
the registry. The PDM add-in fills it automatically as
`PDM:<vault>:<file-id>` and writes the code back to the data card. Web linking
does not write anything to PDM; it only records the association in PartCode.

### Edit a link or metadata

Editors and admins can change the link after generation.

1. Open the code in **Code registry**.
2. Select **Edit link**.
3. Change the external reference, notes, or metadata.
4. Select **Save changes**.

The code and rule version stay immutable. Leaving the external reference empty
removes the link. A duplicate active reference is rejected with a `409` error.
To move a reference to another item, void the old item first, then save the new
one.

**Metadata (JSON)** replaces the item's metadata payload, including attributes
captured from the rule. Review the JSON before saving. Every edit is recorded in
the audit log as **Code updated**.

### Voiding a code

Editors and admins can void a code that was generated by mistake.

1. Open the code in the registry.
2. Select **Void code**.
3. Read the warning and confirm.

Voiding is permanent. The code stays in the registry for audit and is marked
**void**; it cannot be used again and the number is not returned to the counter.
Do not use void to retire an obsolete physical part: manage that in PDM/ERP.
Use it only when the code itself was created incorrectly.

---

## 7. Create and edit coding rules

Only editors and admins can change rules. The rule editor is under
**Coding rules**.

### 7.1 Create a rule

1. Select **New rule**.
2. Enter a clear **name** and a **description**.
3. Set the **document type** (for example `part`, `assembly`, `drawing`).
4. Optionally enter a **rule key**. If you leave it empty, PartCode derives one
   from the name.
5. Set the maximum code length and choose whether output is uppercase or
   preserves the typed case.
6. Add segments with the **Add** button and order them with the arrow buttons.
7. Choose **Active** or **Draft** under **Publish as**.
8. Review the **Format preview**, then select **Create rule**.

The rule key is permanent once the rule exists. Choose a short, stable key
because PDM and ERP integrations use it.

### 7.2 Configure each segment

| Segment | Fields to fill |
|---|---|
| **Literal** | The fixed value, such as `PRT`. |
| **Separator** | The punctuation, such as `-` or `/`. |
| **List** | Key, label, options, and whether the field is required. Enter one option per line as `CODE` or `CODE|Label`. |
| **Text** | Key, label, minimum and maximum length, optional regular expression, and whether it is required. |
| **Date** | A `strftime` pattern. `%y` gives a two-digit year, `%Y%m` gives year and month, and so on. The date is evaluated in UTC. |
| **Counter** | Key, padding, start, step, and scope. For a per-value counter, choose one or more earlier list/text fields. |
| **Checksum** | `mod97` (two digits) or `luhn` (one digit), calculated over everything before it. |

Rules are validated before they are saved. Two list/text segments cannot share
a key, counter keys must be unique, and a per-value counter can only use fields
that appear before it.

### 7.3 Save a new version

Editing an active rule and selecting **Save new version** does the following:

- Creates the next version.
- Makes the new version active.
- Archives the previously active version.
- Leaves every existing code unchanged.

The editor shows a notice with the new version number before you save, and the
version history appears in the side panel.

Saving a draft creates another version; it stays unavailable for generation
until it is published as active. Archiving a rule from the
**Coding rules** list stops new generations immediately; existing codes remain
available.

### 7.4 Rule-editing checklist

- Test the format with real examples before activating a rule.
- Keep the key stable and descriptive.
- Remember that the maximum length applies to the complete rendered code.
- Avoid changing the meaning of a field in a new version; add a new field or
  rule instead when possible.
- Communicate rule changes to the people who generate codes. New versions only
  affect codes generated after the change.
- A rule cannot be deleted. It can be archived.

---

## 8. Audit log

Editors and admins can open **Audit log**.

- Filter by action or entity type.
- Select an event to see the actor, entity, IP address, timestamp, and details.
- Sign-ins, code generation, code link/metadata updates, rule changes, user
  changes, API-key changes, and voiding are recorded.

Use the audit log to answer questions such as "who created this code?" or "when
did this rule change?". Viewers do not have access to the audit log.

---

## 9. Users and API keys

This screen is available to admins only.

### 9.1 Users

- **New user** creates an account with an email, temporary password, and role.
- Passwords must be at least eight characters.
- You can change a user's role or deactivate/reactivate the account.
- You cannot deactivate or demote your own admin account.

Inactive users cannot sign in. There is no self-service password reset in this
version; account recovery is handled by an administrator with server access.

### 9.2 API keys

API keys are credentials for machines, not people. They are used by the
SOLIDWORKS PDM connector and ERP adapters.

1. Open the **API keys** tab.
2. Select **Create API key** and give it a recognizable name, such as
   "PDM production".
3. Copy the secret immediately. It is shown only once.
4. Store it in the connector's protected configuration or secret manager.

The list shows only the key prefix, creation date, last use, and status. To
rotate a key, create a new one, update the connector, then revoke the old key.
Revocation takes effect immediately: connectors using the old key receive
`401 Unauthorized`.

Never send an API key by email, paste it into source control, or use it as a
user password.

---

## 10. Assigning codes from SOLIDWORKS PDM

The PDM add-in is the normal way to give a number to a file that already lives
in a vault. It reads selected data-card values, asks PartCode for a code, and
writes the result back to the file's data card.

After a successful assignment there are two halves of the link:

- The PDM file stores the code in a data-card variable, normally `PartNumber`.
- PartCode stores the item with `source=pdm`, the code, the values read from
  PDM, and `external_ref=PDM:<vault>:<file-id>`.

The file ID makes the link stable when a file is renamed or moved. A copied
file, however, gets a new file ID and must be assigned its own code.

PartCode does not scan or import the vault. The link is created only when a user
runs the add-in successfully on a file. Part numbers created manually in PDM
are not added to the PartCode registry automatically.

### 10.1 Before you start

Ask your administrator to confirm:

- The PartCode add-in is installed and enabled for the vault.
- The connector points at the correct PartCode server and has a valid API key.
- `documentType` matches the kind of file being coded (default `part`).
- The target variable exists on the data card, is writable, and is not also
  controlled by a PDM serial-number generator.
- The values PartCode should read are listed in `sourceVariables` (by default
  `Description`, `Material`, and `Family`).

Use the PDM vault view or search to find the part or drawing. You do not need
to open it in SOLIDWORKS; select exactly one file in PDM. The command is
disabled for folders and multiple selections. If your vault requires a check-out
before data-card values can change, check the file out first.

### 10.2 Assign and link a code

1. Right-click the file and choose **PartCode: assign code...**.
2. The add-in resolves the file in the vault and reads the configured variables
   from the file-level (`@`) data-card tab. It also records the vault name, file
   ID, file name, and path.
3. The dialog loads the active PartCode rules for the configured document type.
4. Choose the rule that applies to this file.
5. When a rule field has the same key or label as a value read from PDM, the
   field is prefilled. List and text fields can be changed; constant, date,
   counter, and checksum segments are calculated by the rule.
6. Optionally select **Preview**. Preview does not consume a number and does not
   write to PDM.
7. Select **Reserve and write to PDM**.
8. PartCode checks that the PDM file is not already linked to an active code,
   allocates a number atomically, and creates the item.
9. The add-in writes the code to the configured target variable and flushes the
   data card. A confirmation shows the code and the variable name.
10. Complete the normal check-in or commit step required by your vault. The
    add-in does not check the file in or run a workflow transition.
11. Verify that the code is present on the data card. In PartCode, open **Code
    registry** and search for the code; the detail panel should show `source=pdm`
    and the `PDM:<vault>:<file-id>` external reference.

Example: a bracket has `Family=MEC`, `Material=AISI 304`, and
`Description=Mounting bracket`. The user selects the mechanical-part rule,
accepts the prefilled values, previews `MEC-00042`, and reserves it. The add-in
writes `MEC-00042` to `PartNumber`; the registry now contains that code linked
to the bracket's PDM file ID.

### 10.3 What the add-in does not do

- It does not scan, import, or bulk-update a vault.
- It does not adopt a part number that already exists on the data card. If the
  file already has a number, do not run the command again.
- It does not create data-card variables; the target must already exist.
- It does not rename files, create BOMs, or change workflow state.
- It does not check files in or out automatically.
- It does not edit or re-link an already-numbered file. Use the web **Code
  registry** to change the external reference or metadata.

### 10.4 What PartCode reads and writes

| Item | Direction | Default | Notes |
|---|---|---|---|
| `sourceVariables` | Read from PDM | `Description`, `Material`, `Family` | Only the mapped variables are read, not the whole data card. A missing or blank value leaves the field empty. |
| `targetVariable` | Write to PDM | `PartNumber` | Must exist and be writable. PartCode writes only this variable back to PDM. |
| `documentType` | Rule filter | `part` | Only active rules for this document type are listed. It is a connector setting, not inferred from the file extension. |
| PDM context | Read from PDM | n/a | `pdm_path`, `pdm_file_id`, `pdm_file_name`, and `pdm_vault` are stored as item metadata. |
| `external_ref` | Derived link | `PDM:<vault>:<file-id>` | Unique per active item. A second assignment for the same file is rejected. |

The add-in reads and writes the **file-level `@` tab** of the data card, not a
named configuration tab. If a variable exists only on a configuration tab,
PartCode will not see it and cannot update it. Use a file-level variable, or
have the vault copy the configuration value to the `@` tab.

PartCode writes only `targetVariable`. If that PDM variable is mapped to a
SOLIDWORKS custom property, PDM may propagate the value to the file through that
mapping; the add-in does not edit SOLIDWORKS custom properties directly. The
`external_ref` value is stored in PartCode, not written to the data card.

### 10.5 Typical data-card variables

SOLIDWORKS PDM does not impose one universal data-card schema. The names below
are common examples; your vault may use different names, capitalization, or
spacing. The names that matter are the exact ones configured in PDM
Administration and in the PartCode connector settings.

| Typical variable | Represents | Notes |
|---|---|---|
| `PartNumber`, `Part Number`, `PartNo` | Company part or item number | Most common `targetVariable`; often mapped to the SOLIDWORKS custom property `PartNumber`. |
| `Description` | Short description or name | Default PartCode source; often mapped to the SOLIDWORKS `Description` property. |
| `Title` | Drawing or document title | Often a SOLIDWORKS summary property; may be read-only. |
| `Family`, `ProductFamily`, `Category` | Product family or classification | Default PartCode source uses `Family`; useful for a list segment. |
| `Material` | Material name | Default source; often mapped from the computed `SW-Material` property and therefore read-only. |
| `Finish`, `SurfaceTreatment` | Finish, coating, or treatment | Usually a custom property. |
| `Revision` | PDM revision | Workflow-managed and usually read-only. Do not encode the revision in the part number. |
| `Version` | PDM version number | System-managed and read-only. |
| `State`, `Workflow` | Lifecycle state and workflow name | System-managed and read-only. |
| `Designer`, `Engineer`, `ApprovedBy` | Ownership and approval | Custom properties; useful for search and audit. |
| `Vendor`, `Supplier`, `Manufacturer`, `ManufacturerPartNumber` | Supply-chain information | Common on purchased-part cards. |
| `Cost`, `Weight`, `Mass`, `Volume`, `SurfaceArea` | Cost or physical properties | Often computed or read-only. SOLIDWORKS mass is a number without a unit. |
| `Project`, `ProjectNumber`, `Customer`, `CustomerPartNumber` | Project or customer reference | Custom properties used for classification and reporting. |
| `DrawingNumber`, `Drawing No` | Drawing or document number | Used on drawing cards; may intentionally equal the model part number. |
| `Comments`, `Keywords`, `Subject` | Search and descriptive text | Usually summary or custom properties. |
| `OldPartNumber`, `LegacyPartNumber` | Previous or migration number | Keep for traceability; do not use as the active code. |

SOLIDWORKS custom properties are stored inside the CAD file. A PDM data-card
variable is a vault field that can be mapped to one of those properties, to a
computed SOLIDWORKS value such as `SW-Material`, or to a PDM-managed value such
as `Revision`. PartCode sees the PDM data card, not the SOLIDWORKS file
directly.

### 10.6 Rules and failure cases

- **Duplicate file link:** If the file ID already has an active PartCode item,
  PartCode rejects the request and reports the existing code. The add-in does
  not write that code to the card. Search the registry, or ask an administrator;
  do not create a second code for the same file.
- **Write failed after reserve:** The code remains in the registry even if the
  PDM write fails. Record the error and contact an administrator. Do not invent
  a replacement code.
- **Read-only target:** A computed variable such as `SW-Material` or a
  workflow-managed `Revision` cannot hold the assigned code. Choose a writable
  custom variable.
- **Variable only on a configuration tab:** Move the value to a file-level
  variable or map it to `@`; the add-in cannot write a configuration tab.
- **PDM serial numbers:** If the vault's own serial-number control writes the
  same `PartNumber` variable, disable one of the two mechanisms. Otherwise the
  value can be overwritten.
- **Manual edits:** Do not type over the assigned code on the data card. If the
  code is wrong, ask an editor to void it and assign a new one.
- **Copied files:** A copied file has a new file ID, so it needs a new code.
  Renaming or moving the original file does not change its file ID or link.

## 11. Common questions

**Why did the preview code change while I was working?**
Someone else generated a code from the same counter. The preview is not a
reservation. The code shown after **Generate & reserve** is final.

**Why is there a gap in the numbering?**
A failed generation attempt can consume a counter value. Numbers are never
reused by design. A gap is preferable to a duplicate.

**I generated the wrong code. What should I do?**
Ask an editor or admin to void it, then generate the correct one. Do not edit
the code string or reuse a voided code.

**The rule I need is not in the list.**
Only active rules are available. Ask an editor or administrator to check its
status. Draft and archived rules cannot generate codes.

**The code contains the wrong year or date.**
Date segments use UTC, not your local timezone. Near midnight, the UTC date can
differ from your local date. Contact an administrator if the rule's date format
is not what your company expects.

**A code is not found.**
The registry only contains codes generated by PartCode. Check the spelling or
search by external reference. Codes created manually in PDM or ERP are not
automatically imported.

**Can I edit or delete a code?**
No. Codes are immutable. A code can be voided, which keeps it for audit but
marks it unusable. Rules can be archived, not deleted.

**Why does the source say `pdm` or `web`?**
It shows where the code came from. `web` means the browser application; `pdm`
means an integration through an API key.

**How do I link a generated code to a PDM file?**
There are two ways:

- Select exactly one file in the vault and run **PartCode: assign code...**.
  The first successful reserve writes the code to the data card and records
  `PDM:<vault>:<file-id>` as the external reference.
- Generate or edit the code in the web app and enter the same
  `PDM:<vault>:<file-id>` value under **External reference**.

See sections 5, 6, and 10. Web linking records the association in PartCode; it
does not write the code into the PDM data card.

**The data card already has a PartNumber. Can I link it to an existing item?**
The add-in does not adopt an existing number. If the code already exists in
PartCode, search the registry and use **Edit link** to attach the PDM file ID.
PartCode rejects a second active code for the same file ID, so do not create a
duplicate.

**Can I assign codes to several files at once?**
No. The add-in accepts one selected file per run and does not scan folders or
import existing vault contents.

**Who can see my codes?**
Users in your company's PartCode tenant can search the registry. All records
are scoped to the tenant. Ask your administrator if access needs to be
restricted further.

---

## 12. Glossary

| Term | Meaning |
|---|---|
| **Code** | The unique part, assembly, drawing, or document number. |
| **Rule** | The definition of how codes of one type are assembled. |
| **Rule key** | The stable identifier an integration uses to select a rule. |
| **Version** | An immutable snapshot of a rule. Saving a rule creates a new version. |
| **Segment** | One building block of a code, such as a literal, list, date, or counter. |
| **Preview** | A proposed code that does not consume a number. |
| **Reserve** | Commit a code and increment its counter. |
| **Counter scope** | Whether a counter is shared by the whole rule or separated per field combination. |
| **Void** | Mark a reserved code unusable while keeping it for audit. |
| **External reference** | An identifier from PDM or ERP, such as `PDM:Vault:12345`, used to correlate records. |
| **Data card** | The PDM form that holds a file's metadata. Its fields are PDM variables. |
| **PDM variable** | A named field on a PDM data card, such as `Description` or `PartNumber`. |
| **SOLIDWORKS custom property** | Metadata stored inside a CAD file. It can be mapped to a PDM variable. |
| **File-level (`@`) tab** | The data-card tab that applies to the file itself, rather than to one configuration. The add-in reads and writes this tab. |
| **API key** | A secret credential used by a machine integration instead of a user login. |
| **Tenant** | The isolated company workspace that owns its users, rules, and codes. |
