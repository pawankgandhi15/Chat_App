# Baatchit architecture image edits

Date: 2026-10-27. Tool: built-in imagegen. Use case: `text-localization`.

These are project-name edits of the existing images, not architecture redesigns. The two single-host images remain historical Docker Compose designs; the README uses the K3s diagram.

| Edit target / saved asset | Replacement text |
| --- | --- |
| `aws-k3s-architecture.png` | Title: `Baatchit \| AWS + Kubernetes`; namespace label: `Namespace: baatchit` |
| `aws-single-host-architecture-v2.png` | Title: `Baatchit \| AWS Architecture` |
| `aws-single-host-architecture.png` | Title: `Baatchit — AWS Single-Host Architecture` |

Prompt applied separately to each image:

> Use case: text-localization. Edit target: the supplied existing technical architecture diagram. Project rename only. Replace the existing project title with the exact replacement title listed above; for the K3s diagram also use `Namespace: baatchit`. Spell Baatchit exactly B-a-a-t-c-h-i-t. Preserve all other text, service names, numbers, icons, connections, topology, historical architecture, colors, whitespace, aspect ratio and layout. Preserve DESIGN ONLY badge where present. No redesign or new content. Keep text crisp at original resolution.

Each edit was visually inspected and copied into this directory. The original generated outputs remain in the image tool's output directory.
