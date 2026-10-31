<div align="center">

# FIELDROOK

### DIAGNOSE. VERIFY. RESOLVE.

**LESS GUESSING. MORE EVIDENCE.**

**A native Windows diagnostic workstation for technicians who want evidence, not guesswork.**

Built by **[ROOKWELD](https://rookweld.com)** · Open source · Designed for real investigations

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-725070?style=flat-square)](LICENSE)
![Platform: Windows](https://img.shields.io/badge/Platform-Windows%2010%2F11-ef725e?style=flat-square)
![Release candidate: v0.5.0](https://img.shields.io/badge/Release%20candidate-v0.5.0-ccf46a?style=flat-square)
![Local-first](https://img.shields.io/badge/Approach-Local--first-75465d?style=flat-square)

[**See the workstation**](#the-workstation) · [**How it works**](#from-symptom-to-evidence) · [**Get started**](#get-started) · [**Safety**](#safety-is-part-of-the-product) · [**What comes next**](#whats-next-the-field-kit)

![FieldRook 0.5.0 native Windows Launchpad](docs/assets/m026/launchpad-native.png)

**An actual WPF + WebView2 Windows application. Not a browser tab.**

</div>

---

## Built for the moment when "it's not working" is all you have

FieldRook turns an unfamiliar Windows problem into a structured investigation. It helps a technician capture observations, run bounded diagnostics, examine traceable evidence, test competing explanations, and record whether a resolution was *actually verified*.

The AI is an assistant to the technician—not an unrestricted shell, a source of invented facts, or an authority that can silently declare a machine fixed.

<table>
<tr><th>Investigate</th><th>Understand</th><th>Verify</th></tr>
<tr>
<td>Describe the issue and select the affected computer.</td>
<td>Inspect observations, provenance, hypotheses, and the next useful question.</td>
<td>Record what changed, distinguish claims from measurements, and export the case.</td>
</tr>
</table>

## The workstation

### A real desktop app, with a distinct identity

FieldRook 0.5.0 introduces **SIGNALFORGE**: a retro-futuristic instrument-inspired interface, with deep plum surfaces, coral highlights, selective acid-lime signals, and restrained circuit-trace motion.

Its new **native WPF shell** embeds the existing React workstation through WebView2 and manages the packaged local FastAPI server. The usual experience is one Windows window, not a manually launched backend plus a browser tab.

![FieldRook active investigation workbench](docs/assets/m026/workbench-case.png)

*The SIGNALFORGE Workbench — actual FieldRook 0.5.0 UI capture, not concept art.*

<details>
<summary><strong>More real application screenshots — evidence, import, and motion settings</strong></summary>

#### Examine evidence

![FieldRook evidence interface](docs/assets/m026/evidence.png)

#### Import a Collector package

![FieldRook Collector import](docs/assets/m026/import.png)

#### Tune the living interface

![FieldRook motion preferences](docs/assets/m026/settings-motion.png)

</details>

### Watch the investigation flow

**[Watch the FieldRook 0.5.0 UI journey (WebM)](docs/assets/m026/demo-journey.webm)**

> **Capture note:** This video records the production React UI in Chromium, using the same frontend build hosted by the native shell. It is not footage of the sealed WPF/WebView2 window. The screenshots above include actual application captures.

The background motion is deliberately subtle. The interface offers **Alive**, **Quiet**, and **Off** preferences and supports reduced-motion behavior. Decorative activity is not presented as a real hardware measurement.

## From symptom to evidence

```text
Technician describes an issue
          │
          ▼
Choose target: this PC / another PC / not yet known
          │
          ▼
Run approved local diagnostics or import a Collector package
          │
          ▼
Timestamped evidence + provenance + visible uncertainty
          │
          ▼
Review hypotheses and the next useful check
          │
          ▼
Technician observes, confirms, or supplies new evidence
          │
          ▼
Document outcomes and export a case report
```

### What works today

| Capability | What it does |
| :--- | :--- |
| **Native Windows workstation** | Opens in its own WPF/WebView2 window with the SIGNALFORGE interface. |
| **Guided investigations** | Keeps the problem, current questions, evidence, and investigation history together. |
| **Windows diagnostics** | Uses registered, bounded diagnostics with explicit target and tool boundaries. |
| **Portable Collector** | Gathers read-only evidence on a Windows computer and exports a versioned, hash-verified ZIP for import. |
| **Evidence and provenance** | Shows where observations came from and distinguishes collected measurements from user reports and model interpretations. |
| **Knowledge support** | Retrieves relevant technical references as quoted context with citations; irrelevant matches are filtered conservatively. |
| **AI provider choice** | Supports optional local-model inference and configured cloud inference; simulated operation remains labeled. |
| **Technician-controlled actions** | Keeps proposals, approvals, execution, and verification separate. The only implemented corrective execution targets FieldRook's own demo worker. |
| **Case persistence and export** | Reopen investigations and produce technician-readable case reports. |
| **Motion preferences** | Tune the ambient UI between Alive, Quiet, and Off. |

**Important:** An imported Collector package does *not* give FieldRook remote command execution. Host-local measurements cannot be silently substituted for a different machine, and a remote reading cannot be rechecked against the operator's own PC.

## The portable Collector

The Collector is a separate Windows executable. It is designed to run on an affected computer without requiring a Python installation, gather selected read-only diagnostics with consent, and create a package that FieldRook can validate and import.

```text
Affected Windows PC                           Technician's FieldRook
┌─────────────────────┐                        ┌─────────────────────┐
│ FieldRook Collector │─── evidence ZIP ────▶ │  Import + validate  │
│  read-only capture  │                        │  investigate        │
└─────────────────────┘                        └─────────────────────┘
```

Collection is not silently uploaded. Some elevated collection categories have not yet been validated in the release candidate; permissions and unavailable measurements must be reported honestly.

## Get started

### Windows desktop pre-release - v0.5.0

The native Desktop and portable Collector have been packaged and validated on the development machine and are published as a [pre-release on GitHub](https://github.com/Rookweld/FieldRook/releases/tag/v0.5.0) (binaries are unsigned - verify checksums before running):

- [FieldRook-0.5.0.zip](https://github.com/Rookweld/FieldRook/releases/download/v0.5.0/FieldRook-0.5.0.zip) - portable app: unzip, run `FieldRook.exe`, keep the folder together.
- [FieldRook-Collector-0.5.0.zip](https://github.com/Rookweld/FieldRook/releases/download/v0.5.0/FieldRook-Collector-0.5.0.zip) - portable collector: USB-friendly, runs from its own folder.
- [SHA256SUMS-v0.5.0.txt](https://github.com/Rookweld/FieldRook/releases/download/v0.5.0/SHA256SUMS-v0.5.0.txt) - hashes of both ZIPs plus the executables inside.

To install:

1. Extract the complete `FieldRook-0.5.0` distribution. Keep its bundled files together.
2. Run `FieldRook.exe` to open the native Windows application.
3. Complete the first-run setup and select the desired inference mode.
4. Start an investigation or import an existing Collector package.

**Runtime notes:** Windows and a suitable WebView2 Runtime are required. Builds are currently unsigned, so Windows may display an unverified-publisher warning. No model is bundled by default. Offline investigation and evidence workflows do not depend on a paid cloud model.

For build provenance, validation details, and current limitations, see [M026 delivery notes](docs/M026_DELIVERY.md). For inference setup, see [Provider configuration](docs/PROVIDERS.md).

### Building from source

This repository contains the Python/FastAPI backend, React/TypeScript frontend, native Windows shell, and packaging scripts. Development requires the corresponding build tools; **end users of the packaged Desktop do not need Python or Node.js installed separately**.

From a Windows development checkout with Python, Node.js/pnpm, and .NET 10 SDK, follow [the desktop build documentation](packaging/desktop/README-SHELL.md) and [the M026 delivery manifest](docs/M026_DELIVERY.md). The native shell and backend are packaged separately, then assembled into the complete distribution. Do not confuse the older browser-based development launcher with the native 0.5.0 application.

## Safety is part of the product

FieldRook deliberately makes certain operations harder to do by accident.

- **Read-only by default.** Windows diagnostics use registered capabilities and bounded inputs, not arbitrary model-authored PowerShell.
- **Target-aware evidence.** Collector imports are tied to the affected computer; mismatched identities are not silently mixed.
- **Human control.** An AI suggestion is not permission to execute it. Corrective actions require explicit approval and a registered execution path.
- **Measured verification.** An intervention being attempted or reported does not mean the problem was resolved.
- **Local-first processing.** The packaged service binds to loopback and uses application-owned local storage. Cloud-provider use requires deliberate configuration and consent.
- **Provenance and privacy.** Collector archives are integrity-checked, and diagnostic data is not automatically transmitted elsewhere.
- **Separation of fact and inference.** Model explanations and confidence language never replace measured evidence.

Security documentation: [FORGE privacy](docs/FORGE_PRIVACY.md) · [Tool boundaries](docs/TOOLS.md) · [Technical highlights](docs/demo/TECHNICAL_HIGHLIGHTS.md)

## Inside FieldRook

| Layer | Implementation |
| :--- | :--- |
| Desktop host | .NET WPF + Microsoft Edge WebView2 |
| Frontend | React + TypeScript + Vite, SIGNALFORGE design system |
| Local API and investigation engine | Python + FastAPI |
| Case persistence | SQLite in per-user application data |
| Windows evidence | Allowlisted diagnostic toolpacks and portable Collector |
| Inference | Optional configured local or cloud providers; no unrestricted shell authority |
| Validation | Pytest, Playwright, .NET tests, diagnostic gauntlet, frozen-app smoke tests |

FieldRook was developed as part of the **[Meta Global AI Developer Hackathon 2026](https://dev.meta.ai/events/global-hackathon)**. This project is independent; participation is not an endorsement by Meta.

## Validation and known limits

For the M026 local release-candidate gate, the delivery report records:

| Gate | Reported result |
| :--- | :--- |
| Backend | 684 passed, 4 environment-dependent skips |
| Playwright end-to-end | 47 / 47 passed |
| .NET tests | 66 / 66 passed |
| Diagnostic gauntlet | 37 / 37 passed |
| Native packaged journey | Investigation, Collector import, export, and persistence exercised |
| Security probes | 11 / 11 passed |

These are **local release-candidate validation results**, not a claim that every user environment, Windows machine, AI provider, or troubleshooting problem has been certified.

**Still to validate:** unsigned-binary reputation and antivirus behavior across vendors; Windows machines without WebView2; multi-machine field trials; upgrade-over-existing installation; selected elevated Collector categories; lower-end CPU-only local-model responsiveness; some performance combinations on other GPUs.

## What's next: The Field Kit

The next major **prototype direction** is a modular, context-aware technician toolbox integrated into the right-hand dock:

**Network Lab · Process Watch · Event Decoder · Evidence Lens · Command Deck · Field Notes**

The separate **Field Kit Lab** is currently an **interactive design prototype**. These six modules are **NOT shipped 0.5.0 features**. The plan is to turn useful concepts into evidence-backed instruments, with bounded diagnostics and clear local-versus-remote behavior.

The most promising concept: **Evidence Lens** — compare two Collector snapshots, highlight meaningful differences, and show which hypotheses deserve another look.

## Project and development history

- [M026 native desktop delivery](docs/M026_DELIVERY.md)
- [Hackathon build log](HACKATHON.md)
- [Provider documentation](docs/PROVIDERS.md)
- [Diagnostic tool reference](docs/TOOLS.md)
- [Security and privacy](docs/FORGE_PRIVACY.md)
- [License](LICENSE)

---

<div align="center">

### LESS GUESSING. MORE EVIDENCE.

**FIELDROOK** · **DIAGNOSE. VERIFY. RESOLVE.**

Made at **ROOKWELD** — *FORGE. BUILD. IMAGINE.*

</div>
