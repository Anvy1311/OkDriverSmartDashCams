# Cost-Benefit Note

## Planning assumptions

These are indicative Indian-cloud planning estimates in INR, not vendor quotations. They assume a 100-camera pilot and a statewide target of 80,000 cameras, existing department-owned camera networks, metadata-first central processing, 30 days of hot event media, 90 days of warm metadata/clip retention, and no continuous central ingest of every raw video stream. Prices must be re-quoted before procurement.

## Monthly operating estimate

| Cost area | 100-camera pilot | 80,000-camera statewide planning band | Basis |
| --- | ---: | ---: | --- |
| Application/API nodes | ₹16,000 | ₹4,80,000–₹9,60,000 | Two small nodes for the pilot; 12–24 regional and central nodes |
| Edge gateways and protocol adapters | ₹25,000 | ₹20,00,000–₹40,00,000 | Ten pilot gateways; 400–800 regional gateways with redundancy |
| PostgreSQL/PostGIS replicas and backups | ₹24,000 | ₹12,00,000–₹30,00,000 | Managed primary/replica storage, indexing, and recovery |
| Queue, cache, and realtime fan-out | ₹8,000 | ₹6,00,000–₹18,00,000 | Redis plus managed event-bus capacity and WebSocket fan-out |
| GPU inference workers | ₹30,000 | ₹18,00,000–₹60,00,000 | One pilot worker; 6–20 workers sized to peak events |
| Object storage and lifecycle | ₹6,000 | ₹8,00,000–₹24,00,000 | Event clips, snapshots, and short retention media |
| WAN, egress, and transcoding | ₹15,000 | ₹12,00,000–₹36,00,000 | Adaptive viewing sessions rather than full-time central video |
| Observability and security tooling | ₹8,000 | ₹6,00,000–₹18,00,000 | Logs, metrics, SIEM, vulnerability and certificate operations |
| On-call and operations staffing | ₹1,80,000 | ₹72,00,000–₹1,44,00,000 | Pilot support team; regional and central operating model |
| **Estimated total** | **₹3,12,000/month** | **₹1,58,80,000–₹3,79,60,000/month** | Annualized planning range: approximately ₹1.91 crore–₹4.55 crore |

The statewide band excludes government-owned network leases, field camera replacement, vehicle or mobile hardware, taxes, and any mandated local data-residency premium. A low-cost deployment keeps raw retention at the department VMS and centralizes only metadata, thumbnails, and event-triggered clips.

## Cost controls

- Keep raw video at the department or regional VMS unless a use case requires central retention.
- Use event-triggered clips and thumbnails for the command center.
- Apply adaptive bitrate, motion-aware streaming, and per-department session limits.
- Schedule GPU workers for peak hours and use CPU workers for metadata/alert tasks.
- Use hot/warm/cold lifecycle policies and delete data according to approved retention.
- Cache camera metadata and watchlist lookups, but never cache authorization decisions longer than policy permits.
- Measure cost per camera, active viewing hour, event, and alert response rather than relying only on server count.

## Benefit model

The operational benefits are faster cross-camera search, reduced manual VMS switching, earlier watchlist response, better asset visibility, auditable decisions, and a repeatable integration pattern for new departments and vendors. A pilot should measure mean time to detect, acknowledge, resolve, and trace an entity before extrapolating statewide savings. A useful pilot decision rule is to continue expansion when the measured operator time saved exceeds the incremental platform and support cost per covered camera.
