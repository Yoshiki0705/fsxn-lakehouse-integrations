🌐 **English** | [日本語](./netapp-ja.md)

# Feedback: NetApp

Scope: ONTAP behaviour observed through Amazon FSx for NetApp ONTAP, where the
behaviour originates in ONTAP itself rather than in the AWS service layer. Compiled
2026-08-06.

## Framing

Most of the constraints this project found sit in the AWS managed-service layer or in
analytics engine implementations, and those are recorded on
[the AWS page](./aws.md) and the per-engine pages. This page covers the three
findings where ONTAP itself is the relevant layer.

One of these is a real design consideration that is not documented anywhere obvious
and cost this project a full misdirected debugging session. The other two are cases
where ONTAP capability and FSx exposure diverge, which is useful for NetApp to know
even though the exposure decision is not NetApp's.

| # | Finding | Layer | Severity |
|:---:|---|---|---|
| 1 | [Name-service stack sits in the S3 data path](#1-the-name-service-stack-sits-in-the-s3-data-path) | ONTAP | High — an AD outage presents as a storage outage |
| 2 | [One object-store server per SVM blocks coexistence](#2-one-object-store-server-per-svm-blocks-coexistence-with-access-points) | ONTAP | Medium — structural, needs to be designed around |
| 3 | [SnapMirror S3 exists in ONTAP but is unreachable via FSx](#3-snapmirror-s3-exists-in-ontap-but-is-not-reachable-through-fsx-for-ontap) | ONTAP capability, FSx exposure | Medium — affects migration planning |

---

## 1. The name-service stack sits in the S3 data path

**The most useful finding on this page, and the least documented.**

If an SVM has DNS servers configured for Active Directory membership and those DNS
servers become unreachable, **every S3 Access Point on that SVM times out.** This
happens even when:

- the Access Point volumes use UNIX security style
- NFS export policies permit all access
- user-configured FPolicy is disabled
- the Access Point lifecycle state is `AVAILABLE`

### Mechanism as understood

The S3 request path traverses the SVM's name-service stack. When CIFS or AD is
configured, ONTAP attempts UNIX ↔ Windows user-mapping resolution, and that
resolution requires DNS communication with domain controllers. An S3 request that
never touches a Windows identity still pays for the SVM being AD-joined.

```
S3 API request
  → Access Point backend
    → SVM file system access
      → ONTAP name-service stack (ns-switch: files, dns)
        → DNS query to unreachable domain controller
          → timeout
```

### Why this is worth documenting prominently

The failure signature points away from the cause. `HeadBucket` returns 200, because
it does not traverse the file system. The Access Point reports `AVAILABLE`. IAM
policies validate. Volume permissions are permissive. Every check an engineer runs
first comes back clean, and the actual cause is an AD dependency in a code path that
nothing in the S3 documentation mentions.

This cost this project a debugging session that started in the IAM and Access Point
policy layers and stayed there for a while.

**Suggested documentation**: state that an AD-joined SVM introduces a DNS dependency
into the S3 data path, and that this dependency applies to all Access Points on the
SVM regardless of volume security style. A one-paragraph note would prevent the
misdirection entirely.

**Diagnostic that works**: probe with `ListObjectsV2 --max-keys 1` rather than
`HeadBucket`, and check discovered domain controllers:

```
GET /api/protocols/cifs/domains?svm.name=<svm>&fields=discovered_servers
```

An empty `discovered_servers` on an AD-joined SVM is the signal.

**Design implication worth stating**: if a volume is only ever accessed through S3
and NFS, keeping its SVM out of AD removes this dependency. That is a real
architectural choice with a real trade-off, and it deserves to be a documented one
rather than something discovered during an incident.

---

## 2. One object-store server per SVM blocks coexistence with Access Points

**Measured** 2026-05-26.
[Evidence](../../verification-pack/snapmirror-s3/evidence/2026-05-26/evidence-record.yaml)

Creating a native ONTAP S3 object-store server on an SVM that already has S3 Access
Points fails:

```
vserver object-store-server create -vserver verification-svm \
  -object-store-server snapmirror-s3-test -is-http-enabled true

→ Only one object store server is supported per Vserver
```

Access Points install an internal object-store server that `vserver
object-store-server show` does not display. So from the operator's view the SVM has
no object-store server, and the create still fails.

The reverse direction fails too, reported from the AWS side as:

> Amazon FSx is unable to create an S3 access point because of an existing ONTAP
> object storage server on SVM...

### Why this matters

This is a structural conflict, not a timing or ordering issue. Retrying does not
help. The design consequence is that an SVM is either an Access Point SVM or a native
ONTAP S3 SVM, and choosing wrong means creating a new SVM and moving volumes.

**Suggested change**: have `vserver object-store-server show` display the internal
server that Access Points install, even if read-only and clearly marked as
system-managed. The current behaviour is that an operator checks for a conflicting
resource, sees none, and then hits a conflict on the create. Making the resource
visible would turn a confusing failure into an obvious one.

---

## 3. SnapMirror S3 exists in ONTAP but is not reachable through FSx for ONTAP

**Measured** 2026-05-26 on ONTAP 9.17.1P6.
[Evidence](../../verification-pack/snapmirror-s3/evidence/2026-05-26/evidence-record.yaml) ·
[ADR-002](../adr/ADR-002-snapmirror-s3-unavailability.md)

The exposure decision here belongs to AWS, and it is recorded on
[the AWS page](./aws.md) as such. It appears here because the divergence between
ONTAP documentation and FSx reality affects how NetApp documentation is read.

| Probe | Result |
|---|---|
| `snapmirror object-store show` | `"object-store" is not a recognized command`, at admin, advanced and diagnostic privilege |
| `GET /api/cloud/targets` | `not authorized for that command` |
| `snapmirror policy show -type continuous` | The `Continuous` policy exists with comment "Policy for S3 bucket mirroring" — present, unusable |
| `storage aggregate object-store config show` | Empty; no FabricPool cloud tier configured |

The S3 protocol layer works: `vserver object-store-server create` and `bucket create`
both succeeded on a fresh SVM (minimum bucket size around 100 GB, a volume
constraint). So the restriction is specifically on the SnapMirror S3 control plane.

### The documentation divergence

NetApp documentation states, accurately for ONTAP:

> Beginning with ONTAP 9.10.1, you can protect buckets in ONTAP S3 object stores
> using SnapMirror mirroring and backup functionality. Unlike standard SnapMirror,
> SnapMirror S3 enables mirroring and backups to non-NetApp destinations like AWS S3.

Read while planning an FSx for ONTAP deployment, that sentence implies a capability
that is not reachable. A reader has no way to know from NetApp's documentation that
the FSx variant blocks the control plane, and no way to know from AWS documentation
either — the FSx SnapMirror S3 doc URL redirects to the product landing page.

**Suggested change**: a platform-availability note on the SnapMirror S3 pages
indicating that FSx for ONTAP does not expose this feature. NetApp already
distinguishes platform support elsewhere in the ONTAP docs, so this would be
consistent with existing practice rather than a new convention.

**Practical impact**: migration plans written against on-premises ONTAP capability
assume SnapMirror S3 is available after moving to FSx for ONTAP. It is not. AWS
DataSync (NFS → S3) is the only verified sync mechanism, and it does not carry
ONTAP-native replication efficiency — no block-level incremental transfer, no
deduplication awareness.

---

## What is working well, recorded for balance

These are not requests. They are results that should be visible alongside the gaps.

| Area | Result |
|---|---|
| ListObjectsV2 latency | Re-measured 2026-08-05 at **0.9–1.4x** native S3 for 10 to 5,000 objects, flat and nested layouts alike. This repository previously published 30–80x; that figure did not reproduce and has been withdrawn. The correction is recorded because the original claim was published and read. Above 5,000 objects in a single directory remains unmeasured (UNV-025). [Evidence](../../verification-pack/s3ap-list-latency/evidence/2026-08-05/benchmark-result.yaml) |
| Read consistency | Consistent list-after-write held throughout. Every table format that failed did so on a missing write primitive, never on a consistency anomaly |
| ONTAP caching under concurrent load | 25 concurrent Athena queries moved roughly 389 MB/s aggregate against a file system provisioned at 128 MBps, with 25/25 succeeding. Caching is doing substantial work. Stated as a caveat on the throughput reading, but it is also a real result. [Evidence](../../verification-pack/athena-concurrency/evidence/2026-08-06/evidence-record.yaml) |
| Multiprotocol access | NFS and S3 against the same volume worked without interference in every test where both were exercised |

## Where ONTAP-side knowledge is thin in this project

Stated so this feedback is not read as more complete than it is.

| Gap | Note |
|---|---|
| FlexCache with Access Points | Documented as a consideration, not measured. See [FlexCache/SnapMirror considerations](../en/s3ap-flexcache-snapmirror-considerations.md) |
| Behaviour on ONTAP 9.18.1 and later | Unverifiable today (UNV-024) |
| Listing above 5,000 objects per directory | Unmeasured (UNV-025). ONTAP sorts directory entries in memory, so this is the case most likely to show a real penalty |
| Multi-AZ deployments | All measurements were `SINGLE_AZ_1` at 128 MBps |
